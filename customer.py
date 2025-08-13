import heapq
import math
import requests
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Tuple, Set, Optional, Any
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 대전광역시 경계 상수
DAEJEON_BBOX = {
    'min_lat': 36.2,
    'max_lat': 36.5,
    'min_lon': 127.3,
    'max_lon': 127.5
}

@dataclass
class ScenicPoint:
    """경치 좋은 지점을 나타내는 클래스"""
    id: int
    name: str
    lat: float
    lon: float
    score: float  # 경치 점수 (0.0 ~ 10.0)
    type: str     # 유형 (공원, 강변, 산책로, 문화재 등)
    description: str = ""

@dataclass
class RouteNode:
    """경로 노드 클래스"""
    id: int
    lat: float
    lon: float
    elevation: float = 0.0
    scenic_score: float = 0.0
    traffic_level: int = 1  # 1(낮음) ~ 5(높음)
    
    def __lt__(self, other):
        """heapq를 위한 비교 연산자"""
        return self.id < other.id

@dataclass
class RouteEdge:
    """경로 간선 클래스"""
    source: RouteNode
    target: RouteNode
    distance: float
    elevation_gain: float = 0.0
    road_type: str = "normal"  # bike_path, park_road, riverside, normal
    scenic_score: float = 0.0
    
    def __lt__(self, other):
        """heapq를 위한 비교 연산자"""
        return self.distance < other.distance

@dataclass
class RoutePreference:
    """사용자 경로 선호도"""
    scenic_weight: float = 0.6     # 경치 가중치
    distance_weight: float = 0.3   # 거리 가중치  
    elevation_weight: float = 0.1  # 고도 변화 가중치
    max_detour_ratio: float = 1.5  # 최대 우회 비율

class ScenicRouteEngine:
    """
    경치 좋은 경로 및 여유로운 경로를 찾는 알고리즘
    CCH 알고리즘과는 완전히 다른 메커니즘을 사용
    """
    
    def __init__(self):
        """ScenicRouteEngine 초기화"""
        # 카카오 API 키 (여러 가능한 환경 변수명 확인)
        self.kakao_api_key = (
            os.getenv("KAKAO_RESTAPI_KEY") or 
            os.getenv("KAKAO_REST_API_KEY") or
            os.getenv("KAKAO_MAP_API_KEY")
        )
        
        # 대전시 공공 API 키
        self.daejeon_api_key = os.getenv("API_KEY")
        self.encoded_api_key = os.getenv("ENAPI_KEY")
        
        self.scenic_points: Dict[int, ScenicPoint] = {}
        self.route_graph: Dict[int, List[RouteEdge]] = {}
        self.node_cache: Dict[int, RouteNode] = {}
        
        # 경치 좋은 장소 카테고리 정의
        self.scenic_categories = {
            "공원": 8.0,
            "강변": 9.0, 
            "산책로": 7.5,
            "문화재": 8.5,
            "관광명소": 9.5,
            "자전거도로": 7.0,
            "호수": 9.0,
            "카페": 6.5,
            "맛집": 6.0,
            "박물관": 8.0,
            "전시관": 7.5
        }
        
        # API 키 상태 확인
        self._check_api_keys()
        
    def _is_within_daejeon(self, lat: float, lon: float) -> bool:
        """대전시 경계 내 좌표인지 확인"""
        return (DAEJEON_BBOX['min_lat'] <= lat <= DAEJEON_BBOX['max_lat'] and
                DAEJEON_BBOX['min_lon'] <= lon <= DAEJEON_BBOX['max_lon'])
        
    def _check_api_keys(self) -> None:
        """API 키 설정 상태 확인"""
        print("🔑 API 키 상태 확인:")
        
        if self.kakao_api_key:
            print(f"   ✅ 카카오 API 키: 설정됨 ({self.kakao_api_key[:10]}...)")
        else:
            print("   ❌ 카카오 API 키: 설정되지 않음")
            print("      .env 파일에 KAKAO_REST_API_KEY 또는 KAKAO_RESTAPI_KEY를 설정해주세요")
            
        if self.daejeon_api_key:
            print(f"   ✅ 대전시 API 키: 설정됨 ({self.daejeon_api_key[:10]}...)")
        else:
            print("   ❌ 대전시 API 키: 설정되지 않음")
            print("      .env 파일에 API_KEY를 설정해주세요")
        
    def load_scenic_points_from_api(self, center_lat: float, center_lon: float, radius: int = 5000) -> None:
        """
        카카오 API를 통해 경치 좋은 장소들을 로드
        
        Args:
            center_lat: 중심 위도
            center_lon: 중심 경도  
            radius: 검색 반경 (미터)
        """
        if not self.kakao_api_key:
            print("⚠️  카카오 API 키가 설정되지 않아 경치 좋은 장소를 로드할 수 없습니다.")
            return
            
        print(f"🔍 경치 좋은 장소 검색 중... (중심: {center_lat:.4f}, {center_lon:.4f}, 반경: {radius}m)")
        
        # 경치 좋은 장소 카테고리별 검색
        categories = ["공원", "관광명소", "문화재", "강변", "호수", "카페", "박물관"]
        total_found = 0
        
        for category in categories:
            try:
                places = self._search_places_by_category(center_lat, center_lon, category, radius)
                category_count = 0
                
                for place in places:
                    # 대전시 경계 내 좌표인지 확인
                    place_lat = float(place.get('y', 0))
                    place_lon = float(place.get('x', 0))
                    
                    if not self._is_within_daejeon(place_lat, place_lon):
                        continue  # 대전시 외부 장소는 제외
                    
                    # 중복 체크 (같은 이름과 비슷한 위치)
                    is_duplicate = False
                    for existing_point in self.scenic_points.values():
                        if (existing_point.name == place.get('place_name', '') and
                            abs(existing_point.lat - float(place.get('y', 0))) < 0.001 and
                            abs(existing_point.lon - float(place.get('x', 0))) < 0.001):
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        scenic_point = ScenicPoint(
                            id=len(self.scenic_points),
                            name=place.get('place_name', ''),
                            lat=float(place.get('y', 0)),
                            lon=float(place.get('x', 0)),
                            score=self.scenic_categories.get(category, 5.0),
                            type=category,
                            description=place.get('address_name', '')
                        )
                        self.scenic_points[scenic_point.id] = scenic_point
                        category_count += 1
                        total_found += 1
                
                if category_count > 0:
                    print(f"   📍 {category}: {category_count}개 발견")
                    
            except Exception as e:
                print(f"   ❌ {category} 검색 중 오류: {e}")
        
        print(f"✅ 총 {total_found}개의 경치 좋은 장소를 발견했습니다.")
                
    def _search_places_by_category(self, lat: float, lon: float, category: str, radius: int) -> List[Dict]:
        """
        카카오 API로 특정 카테고리의 장소 검색
        """
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {self.kakao_api_key}"}
        params = {
            "query": category,
            "x": lon,
            "y": lat,
            "radius": radius,
            "size": 15
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                documents = data.get('documents', [])
                return documents
            elif response.status_code == 401:
                print(f"   ⚠️  카카오 API 인증 오류 (401): API 키를 확인해주세요")
                return []
            elif response.status_code == 429:
                print(f"   ⚠️  카카오 API 요청 한도 초과 (429): 잠시 후 다시 시도해주세요")
                return []
            else:
                print(f"   ⚠️  카카오 API 오류 ({response.status_code}): {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            print(f"   ⚠️  {category} 검색 시간 초과")
            return []
        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  {category} 검색 네트워크 오류: {e}")
            return []
        except json.JSONDecodeError:
            print(f"   ⚠️  {category} 검색 응답 파싱 오류")
            return []
        
    def load_bike_paths_from_api(self, center_lat: float, center_lon: float) -> None:
        """
        대전시 자전거 도로 정보를 API에서 로드
        """
        if not self.daejeon_api_key:
            print("대전시 API 키가 설정되지 않았습니다.")
            return
            
        try:
            # 대전시 자전거 도로 API 호출
            bike_paths = self._get_daejeon_bike_paths(center_lat, center_lon)
            
            for path_data in bike_paths:
                # 자전거 도로를 RouteNode와 RouteEdge로 변환
                self._process_bike_path_data(path_data)
                
        except Exception as e:
            print(f"자전거 도로 정보 로드 중 오류: {e}")
            
    def _get_daejeon_bike_paths(self, lat: float, lon: float) -> List[Dict]:
        """
        대전시 자전거 도로 정보 API 호출
        """
        # 실제 대전시 자전거 도로 API 엔드포인트
        url = f"http://apis.data.go.kr/6300000/openapi2022/bikeroad/getbikeroad"
        params = {
            "serviceKey": self.daejeon_api_key,
            "pageNo": 1,
            "numOfRows": 100,
            "type": "json"
        }
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get('response', {}).get('body', {}).get('items', [])
        return []
        
    def _process_bike_path_data(self, path_data: Dict) -> None:
        """
        자전거 도로 데이터를 그래프 노드와 엣지로 변환
        """
        # 자전거 도로 정보를 바탕으로 RouteNode와 RouteEdge 생성
        # 실제 구현에서는 path_data의 구조에 맞게 파싱
        pass
        
    def find_scenic_route(self, start_lat: float, start_lon: float, 
                         end_lat: float, end_lon: float,
                         preference: RoutePreference) -> Optional[List[RouteEdge]]:
        """
        경치 좋은 경로 찾기 메인 함수
        
        Args:
            start_lat, start_lon: 출발지 좌표
            end_lat, end_lon: 도착지 좌표
            preference: 경로 선호도
            
        Returns:
            경치 좋은 경로 리스트
        """
        # 1. 주변 경치 좋은 장소 로드
        center_lat = (start_lat + end_lat) / 2
        center_lon = (start_lon + end_lon) / 2
        self.load_scenic_points_from_api(center_lat, center_lon)
        self.load_bike_paths_from_api(center_lat, center_lon)
        
        # 2. 출발지와 도착지 노드 생성
        start_node = RouteNode(
            id=0, lat=start_lat, lon=start_lon,
            scenic_score=self._calculate_scenic_score(start_lat, start_lon)
        )
        end_node = RouteNode(
            id=1, lat=end_lat, lon=end_lon,
            scenic_score=self._calculate_scenic_score(end_lat, end_lon)
        )
        
        # 3. 경치 우선 경로 탐색
        return self._scenic_pathfinding(start_node, end_node, preference)
        
    def _calculate_scenic_score(self, lat: float, lon: float) -> float:
        """
        특정 위치의 경치 점수 계산
        """
        total_score = 0.0
        weight_sum = 0.0
        
        for scenic_point in self.scenic_points.values():
            distance = self._haversine_distance(lat, lon, scenic_point.lat, scenic_point.lon)
            
            # 1km 이내의 경치 좋은 장소들만 고려
            if distance <= 1.0:
                # 거리에 반비례하는 가중치
                weight = 1.0 / (1.0 + distance)
                total_score += scenic_point.score * weight
                weight_sum += weight
                
        return total_score / max(weight_sum, 1.0)
        
    def _scenic_pathfinding(self, start: RouteNode, end: RouteNode, 
                           preference: RoutePreference) -> Optional[List[RouteEdge]]:
        """
        경치 우선 경로 탐색 알고리즘
        A* 알고리즘을 경치 점수로 개선한 버전
        """
        # 우선순위 큐: (f_score, unique_id, g_score, current_node, path)
        # unique_id를 추가하여 동일한 f_score일 때 비교 문제 해결
        open_set = [(0, 0, 0, start, [])]
        closed_set = set()
        unique_counter = 1
        
        # 직선 거리 계산
        straight_distance = self._haversine_distance(
            start.lat, start.lon, end.lat, end.lon
        )
        max_distance = straight_distance * preference.max_detour_ratio
        
        while open_set:
            f_score, _, g_score, current, path = heapq.heappop(open_set)
            
            # 목표 지점 도달 확인
            if self._haversine_distance(current.lat, current.lon, end.lat, end.lon) < 0.1:  # 100m 이내
                return path
                
            node_key = (round(current.lat, 4), round(current.lon, 4))
            if node_key in closed_set:
                continue
                
            closed_set.add(node_key)
            
            # 주변 노드 탐색 (실제로는 도로 네트워크 기반)
            neighbors = self._get_neighbor_nodes(current, end)
            
            for neighbor in neighbors:
                if g_score > max_distance:
                    continue
                    
                edge = RouteEdge(
                    source=current,
                    target=neighbor,
                    distance=self._haversine_distance(
                        current.lat, current.lon, neighbor.lat, neighbor.lon
                    ),
                    scenic_score=neighbor.scenic_score
                )
                
                new_g_score = g_score + edge.distance
                new_path = path + [edge]
                
                # 휴리스틱 함수 (경치 점수 고려)
                h_score = self._scenic_heuristic(neighbor, end, preference)
                new_f_score = new_g_score + h_score
                
                heapq.heappush(open_set, (new_f_score, unique_counter, new_g_score, neighbor, new_path))
                unique_counter += 1
                
        return None
        
    def _get_neighbor_nodes(self, current: RouteNode, target: RouteNode) -> List[RouteNode]:
        """
        현재 노드의 이웃 노드들을 반환
        실제로는 도로 네트워크 데이터를 기반으로 구현
        """
        neighbors = []
        
        # 간단한 그리드 기반 이웃 노드 생성 (실제로는 도로 데이터 사용)
        directions = [(0.001, 0), (-0.001, 0), (0, 0.001), (0, -0.001)]
        
        for dlat, dlon in directions:
            neighbor_lat = current.lat + dlat
            neighbor_lon = current.lon + dlon
            
            # 대전시 경계 내에 있는 노드만 추가
            if not self._is_within_daejeon(neighbor_lat, neighbor_lon):
                continue
            
            neighbor = RouteNode(
                id=len(self.node_cache),
                lat=neighbor_lat,
                lon=neighbor_lon,
                scenic_score=self._calculate_scenic_score(neighbor_lat, neighbor_lon)
            )
            neighbors.append(neighbor)
            
        return neighbors
        
    def _scenic_heuristic(self, node: RouteNode, target: RouteNode, 
                         preference: RoutePreference) -> float:
        """
        경치를 고려한 휴리스틱 함수
        """
        # 목표까지의 거리
        distance_to_target = self._haversine_distance(
            node.lat, node.lon, target.lat, target.lon
        )
        
        # 경치 점수 (높을수록 좋음, 비용은 낮아야 함)
        scenic_bonus = (10 - node.scenic_score) * preference.scenic_weight
        distance_cost = distance_to_target * preference.distance_weight
        
        return distance_cost + scenic_bonus
        
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        하버사인 공식으로 두 지점 간 거리 계산 (km)
        """
        R = 6371  # 지구 반지름 (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
        
    def get_route_summary(self, route: List[RouteEdge]) -> Dict[str, Any]:
        """
        경로 요약 정보 반환
        """
        if not route:
            return {}
            
        total_distance = sum(edge.distance for edge in route)
        avg_scenic_score = sum(edge.scenic_score for edge in route) / len(route)
        
        # 경유하는 경치 좋은 장소들
        scenic_places = []
        for edge in route:
            nearby_places = [
                point for point in self.scenic_points.values()
                if self._haversine_distance(
                    edge.target.lat, edge.target.lon, point.lat, point.lon
                ) < 0.5  # 500m 이내
            ]
            scenic_places.extend(nearby_places)
            
        # 중복 제거 (ID 기준)
        unique_places = {}
        for place in scenic_places:
            unique_places[place.id] = place
        unique_places_list = list(unique_places.values())
        
        return {
            "total_distance_km": round(total_distance, 2),
            "average_scenic_score": round(avg_scenic_score, 1),
            "estimated_time_minutes": round(total_distance * 4, 0),  # 15km/h 가정
            "scenic_places_count": len(unique_places_list),
            "scenic_places": [{
                "name": p.name,
                "type": p.type,
                "score": p.score
            } for p in unique_places_list]
        }
        
    def calculate_scenic_score(self, path: List[Any]) -> float:
        """
        주어진 경로의 경치 점수 계산
        
        Args:
            path: 평가할 경로
            
        Returns:
            경치 점수 (0.0 ~ 10.0)
        """
        # 구현 예정: 경로 주변의 경치 좋은 지점과의 근접성 등을 고려하여 점수 계산
        return 5.0  # 기본값
    
    def calculate_path_score(self, path: List[Any], preference: RoutePreference) -> float:
        """
        사용자 선호도에 따른 경로 점수 계산
        
        Args:
            path: 평가할 경로
            preference: 사용자 선호도
            
        Returns:
            경로 점수 (높을수록 선호도가 높음)
        """
        # 구현 예정: 거리, 경치, 고도 변화, 교통량 등을 고려한 종합 점수 계산
        return 0.0  # 기본값
    
    def find_relaxed_route(self, start_id: int, end_id: int, preference: RoutePreference) -> List[Any]:
        """
        여유로운 경로 찾기 (최단 경로보다 조금 더 긴 경로)
        
        Args:
            start_id: 시작 정점 ID
            end_id: 도착 정점 ID
            preference: 사용자 경로 선호도
            
        Returns:
            경로 (Arc 리스트)
        """
        # 구현 예정: 최단 경로를 기반으로 일부 우회하는 경로 탐색 알고리즘
        return []

# 사용 예제
def main():
    """
    ScenicRouteEngine 사용 예제
    """
    print("=== 경치 좋은 경로 찾기 시스템 ===")
    
    # ScenicRouteEngine 인스턴스 생성
    route_engine = ScenicRouteEngine()
    
    # 대전시 좌표 예시 (대전역 -> 엑스포공원)
    start_lat, start_lon = 36.3504, 127.3845  # 대전역
    end_lat, end_lon = 36.3726, 127.3896      # 엑스포공원
    
    # 경로 선호도 설정
    preference = RoutePreference(
        scenic_weight=0.7,      # 경치를 중요하게 고려
        distance_weight=0.2,    # 거리는 덜 중요하게
        elevation_weight=0.1,   # 고도 변화는 최소로
        max_detour_ratio=1.8    # 최단 경로의 1.8배까지 허용
    )
    
    print(f"출발지: 위도 {start_lat}, 경도 {start_lon}")
    print(f"도착지: 위도 {end_lat}, 경도 {end_lon}")
    print(f"선호도: 경치 {preference.scenic_weight}, 거리 {preference.distance_weight}")
    
    try:
        # 경치 좋은 경로 찾기
        print("\n경치 좋은 경로를 탐색 중...")
        scenic_route = route_engine.find_scenic_route(
            start_lat, start_lon, end_lat, end_lon, preference
        )
        
        if scenic_route:
            # 경로 요약 정보 출력
            summary = route_engine.get_route_summary(scenic_route)
            
            print("\n🌟 경치 좋은 경로 탐색 완료!")
            print(f"📏 총 거리: {summary.get('total_distance_km', 0)}km")
            print(f"⏱️  예상 시간: {summary.get('estimated_time_minutes', 0)}분")
            print(f"🎨 평균 경치 점수: {summary.get('average_scenic_score', 0)}/10")
            print(f"📍 경유 명소: {summary.get('scenic_places_count', 0)}개")
            
            # 경유하는 경치 좋은 장소들
            scenic_places = summary.get('scenic_places', [])
            if scenic_places:
                print("\n🏞️  경유하는 명소들:")
                for place in scenic_places[:5]:  # 상위 5개만 표시
                    print(f"   • {place['name']} ({place['type']}) - 점수: {place['score']}")
            
            print(f"\n🗺️  경로 상세:")
            for i, edge in enumerate(scenic_route[:10]):  # 상위 10개 구간만 표시
                print(f"   {i+1}. ({edge.source.lat:.4f}, {edge.source.lon:.4f}) → "
                      f"({edge.target.lat:.4f}, {edge.target.lon:.4f}) "
                      f"[{edge.distance:.2f}km, 경치점수: {edge.scenic_score:.1f}]")
                      
        else:
            print("❌ 경로를 찾을 수 없습니다.")
            print("   - API 키 설정을 확인해주세요")
            print("   - 출발지와 도착지 좌표를 확인해주세요")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print("   - .env 파일의 API 키 설정을 확인해주세요")
        print("   - 인터넷 연결을 확인해주세요")

if __name__ == "__main__":
    main()
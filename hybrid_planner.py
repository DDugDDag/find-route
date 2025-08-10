import os
import math
import heapq
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# 기존 모듈들 임포트
from cch import CustomizableContractionHierarchies, Graph, Vertex, Arc
from customer import ScenicRouteEngine, RoutePreference, RouteNode, RouteEdge
from daejeonBike import get_bike_route_data, get_bike_storage_data

# 환경 변수 로드
load_dotenv()

@dataclass
class RouteRequest:
    """경로 요청 정보"""
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    preferences: RoutePreference
    context: Optional[Dict[str, Any]] = None

@dataclass
class RouteResult:
    """경로 결과"""
    path: List[Any]  # Arc 또는 RouteEdge 리스트
    algorithm_used: str
    total_distance: float
    estimated_time: float
    scenic_score: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

class SmartRoutePlanner:
    """상황에 따른 최적 알고리즘 자동 선택"""
    
    def __init__(self):
        self.distance_threshold_long = 50.0  # km
        self.scenic_weight_threshold = 0.7
        
    def select_algorithm(self, request: RouteRequest) -> str:
        """최적 알고리즘 선택"""
        distance = self._calculate_straight_distance(
            request.start_lat, request.start_lon,
            request.end_lat, request.end_lon
        )
        
        print(f"알고리즘 선택 중... (직선거리: {distance:.2f}km)")
        
        if distance > self.distance_threshold_long:
            print("   → 장거리 경로: CCH 알고리즘 선택")
            return "CCH"
        elif request.preferences.scenic_weight > self.scenic_weight_threshold:
            print("   → 경치 우선: SCENIC 알고리즘 선택")
            return "SCENIC"
        elif request.context and request.context.get('real_time_traffic', False):
            print("   → 실시간 교통 고려: HYBRID 알고리즘 선택")
            return "HYBRID"
        else:
            print("   → 기본 경로: CCH 알고리즘 선택")
            return "CCH"
    
    def _calculate_straight_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """직선 거리 계산 (하버사인 공식)"""
        R = 6371  # 지구 반지름 (km)
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

class RoadNetworkProcessor:
    """실제 도로 네트워크 데이터 처리"""
    
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.encoded_api_key = os.getenv("ENAPI_KEY")
        self.road_graph_cache = {}
        
    def build_road_graph(self, bbox: Tuple[float, float, float, float]) -> Graph:
        """실제 대전시 자전거 도로 데이터로 그래프 구축"""
        print("실제 도로 네트워크 구축 중...")
        
        try:
            # 대전시 자전거 도로 데이터 가져오기
            bike_routes = get_bike_route_data(page_no=1, num_of_rows=100)
            bike_storages = get_bike_storage_data(page_no=1, num_of_rows=50)
            
            # API 데이터가 있으면 사용, 없으면 기본 그래프 생성
            if bike_routes or bike_storages:
                return self._create_graph_from_bike_data(bike_routes, bike_storages)
            else:
                print("API 데이터를 가져올 수 없어 기본 그래프를 생성합니다.")
                return self._create_fallback_graph(bbox)
                
        except Exception as e:
            print(f"API 호출 중 오류 발생: {e}")
            print(" 기본 그래프로 대체합니다.")
            return self._create_fallback_graph(bbox)
    
    def _create_graph_from_bike_data(self, bike_routes: List, bike_storages: List) -> Graph:
        """자전거 도로 데이터로 그래프 생성"""
        graph = Graph()
        vertex_map = {}
        
        # None 체크 및 기본값 설정
        bike_routes = bike_routes or []
        bike_storages = bike_storages or []
        
        print(f"   📍 자전거 도로 {len(bike_routes)}개, 보관소 {len(bike_storages)}개 처리 중...")
        
        # 유효한 데이터가 없으면 기본 그래프 생성
        if not bike_routes and not bike_storages:
            print("   ⚠️  API 데이터가 없어 기본 그래프를 생성합니다.")
            return self._create_fallback_graph((36.2, 127.3, 36.5, 127.5))
        
        # 자전거 보관소를 정점으로 추가
        vertex_count = 0
        for i, storage in enumerate(bike_storages):
            try:
                lat = float(storage.get('latitude', 0))
                lon = float(storage.get('longitude', 0))
                
                if lat != 0 and lon != 0:
                    vertex = Vertex(id=vertex_count, lat=lat, lon=lon)
                    graph.add_vertex(vertex)
                    vertex_map[(lat, lon)] = vertex
                    vertex_count += 1
                    
            except (ValueError, TypeError):
                continue
        
        # 정점이 없으면 기본 그래프 생성
        if vertex_count == 0:
            print("   ⚠️  유효한 보관소 데이터가 없어 기본 그래프를 생성합니다.")
            return self._create_fallback_graph((36.2, 127.3, 36.5, 127.5))
        
        # 자전거 도로 데이터로 간선 추가
        edge_count = 0
        vertices = list(graph.vertices)
        
        # 모든 정점을 서로 연결 (완전 그래프)
        for i in range(len(vertices)):
            for j in range(i + 1, len(vertices)):
                v1, v2 = vertices[i], vertices[j]
                distance = self._calculate_distance(v1.lat, v1.lon, v2.lat, v2.lon)
                
                if distance < 5.0:  # 5km 이내만 연결
                    arc1 = Arc(source=v1, target=v2, cost=distance)
                    arc2 = Arc(source=v2, target=v1, cost=distance)
                    graph.add_arc(arc1)
                    graph.add_arc(arc2)
                    edge_count += 2
        
        print(f"   ✅ 그래프 생성 완료: 정점 {len(graph.vertices)}개, 간선 {edge_count}개")
        return graph
    
    def _create_fallback_graph(self, bbox: Tuple[float, float, float, float]) -> Graph:
        """API 실패 시 기본 그래프 생성"""
        print("   🔄 기본 그래프 생성 중...")
        graph = Graph()
        
        # 대전시 주요 지점들을 기본 정점으로 사용
        major_points = [
            (36.3504, 127.3845, "대전역"),
            (36.3726, 127.3896, "엑스포공원"),
            (36.3219, 127.4086, "유성온천"),
            (36.3398, 127.3940, "대전시청"),
            (36.3665, 127.3448, "서대전역")
        ]
        
        vertices = []
        for i, (lat, lon, name) in enumerate(major_points):
            vertex = Vertex(id=i, lat=lat, lon=lon)
            graph.add_vertex(vertex)
            vertices.append(vertex)
        
        # 모든 정점을 서로 연결
        for i in range(len(vertices)):
            for j in range(i + 1, len(vertices)):
                v1, v2 = vertices[i], vertices[j]
                distance = self._calculate_distance(v1.lat, v1.lon, v2.lat, v2.lon)
                
                arc1 = Arc(source=v1, target=v2, cost=distance)
                arc2 = Arc(source=v2, target=v1, cost=distance)
                graph.add_arc(arc1)
                graph.add_arc(arc2)
        
        print(f"   ✅ 기본 그래프 생성 완료: 정점 {len(vertices)}개")
        return graph
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """두 지점 간 거리 계산"""
        R = 6371
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c



class HybridRoutePlanner:
    """CCH와 Scenic Route의 장점을 결합한 하이브리드 플래너"""
    
    def __init__(self):
        print("🔧 하이브리드 경로 플래너 초기화 중...")
        
        self.smart_planner = SmartRoutePlanner()
        self.network_processor = RoadNetworkProcessor()
        self.scenic_engine = ScenicRouteEngine()
        self.cch_engine = None  # 원본 CustomizableContractionHierarchies 사용
        self.graph = None
        self.initialized = False
        self.route_cache = {}
        
        print("✅ 하이브리드 플래너 초기화 완료")
    
    def initialize_network(self, bbox: Tuple[float, float, float, float] = None):
        """도로 네트워크 초기화"""
        if bbox is None:
            # 대전시 전체 영역
            bbox = (36.2, 127.3, 36.5, 127.5)
        
        print("🌐 도로 네트워크 초기화 중...")
        self.graph = self.network_processor.build_road_graph(bbox)
        
        if self.graph and len(self.graph.vertices) > 0:
            print("🔄 CCH 전처리 중...")
            # 원본 CustomizableContractionHierarchies 사용 (최적화됨)
            self.cch_engine = CustomizableContractionHierarchies(self.graph)
            # 메트릭 독립적 전처리 수행
            self.cch_engine.metric_independent_preprocessing(len(self.graph.vertices))
            # 커스터마이징 수행
            self.cch_engine.customize()
            print(f"   ✅ CCH 전처리 완료: {len(self.graph.vertices)}개 정점")
            print("✅ 네트워크 초기화 완료")
            self.initialized = True
        else:
            print("❌ 네트워크 초기화 실패")
    
    def plan_route(self, request: RouteRequest) -> RouteResult:
        """하이브리드 경로 계획"""
        print(f"\n  경로 계획 시작: ({request.start_lat:.4f}, {request.start_lon:.4f}) → ({request.end_lat:.4f}, {request.end_lon:.4f})")
        
        # 네트워크가 초기화되지 않았다면 초기화
        if not self.graph:
            self.initialize_network()
        
        # 알고리즘 선택
        algorithm = self.smart_planner.select_algorithm(request)
        
        # 선택된 알고리즘으로 경로 계획
        if algorithm == "SCENIC":
            return self._plan_scenic_route(request)
        elif algorithm == "HYBRID":
            return self._plan_hybrid_route(request)
        else:  # CCH
            return self._plan_cch_route(request)
    
    def _plan_cch_route(self, request: RouteRequest) -> RouteResult:
        """CCH 알고리즘으로 경로 계획"""
        print("🚀 CCH 알고리즘 실행 중...")
        
        if not self.cch_engine:
            return RouteResult(
                path=[], algorithm_used="CCH", total_distance=0, estimated_time=0,
                metadata={"error": "CCH 엔진이 초기화되지 않음"}
            )
        
        # 가장 가까운 정점 찾기
        start_vertex = self._find_nearest_vertex(request.start_lat, request.start_lon)
        end_vertex = self._find_nearest_vertex(request.end_lat, request.end_lon)
        
        if not start_vertex or not end_vertex:
            return RouteResult(
                path=[], algorithm_used="CCH", total_distance=0, estimated_time=0,
                metadata={"error": "시작점 또는 도착점을 찾을 수 없음"}
            )
        
        # 최적화된 원본 CCH로 경로 탐색
        path = self.cch_engine.find_path(self.graph, start_vertex.id, end_vertex.id)
        
        if path:
            total_distance = sum(arc.cost for arc in path)
            estimated_time = total_distance * 4  # 15km/h 가정
            
            return RouteResult(
                path=path,
                algorithm_used="CCH",
                total_distance=total_distance,
                estimated_time=estimated_time,
                metadata={"vertices_count": len(path) + 1}
            )
        else:
            return RouteResult(
                path=[], algorithm_used="CCH", total_distance=0, estimated_time=0,
                metadata={"error": "경로를 찾을 수 없음"}
            )
    
    def _plan_scenic_route(self, request: RouteRequest) -> RouteResult:
        """Scenic 알고리즘으로 경로 계획"""
        print("Scenic 알고리즘 실행 중...")
        
        scenic_path = self.scenic_engine.find_scenic_route(
            request.start_lat, request.start_lon,
            request.end_lat, request.end_lon,
            request.preferences
        )
        
        if scenic_path:
            total_distance = sum(edge.distance for edge in scenic_path)
            estimated_time = total_distance * 4
            avg_scenic_score = sum(edge.scenic_score for edge in scenic_path) / len(scenic_path)
            
            return RouteResult(
                path=scenic_path,
                algorithm_used="SCENIC",
                total_distance=total_distance,
                estimated_time=estimated_time,
                scenic_score=avg_scenic_score,
                metadata={"scenic_places": len(self.scenic_engine.scenic_points)}
            )
        else:
            return RouteResult(
                path=[], algorithm_used="SCENIC", total_distance=0, estimated_time=0,
                metadata={"error": "경치 좋은 경로를 찾을 수 없음"}
            )
    
    def _plan_hybrid_route(self, request: RouteRequest) -> RouteResult:
        """하이브리드 알고리즘으로 경로 계획"""
        print("🔄 하이브리드 알고리즘 실행 중...")
        
        # 1. CCH로 기본 경로 계산
        cch_result = self._plan_cch_route(request)
        
        # 2. Scenic으로 경치 좋은 경로 계산
        scenic_result = self._plan_scenic_route(request)
        
        # 3. 두 결과를 비교하여 최적 선택
        if cch_result.path and scenic_result.path:
            # 거리 차이가 30% 이내면 경치 좋은 경로 선택
            distance_ratio = scenic_result.total_distance / cch_result.total_distance
            
            if distance_ratio <= 1.3:  # 30% 이내
                print(f"   → 경치 좋은 경로 선택 (거리 비율: {distance_ratio:.2f})")
                scenic_result.algorithm_used = "HYBRID"
                return scenic_result
            else:
                print(f"   → 효율적인 경로 선택 (거리 비율: {distance_ratio:.2f})")
                cch_result.algorithm_used = "HYBRID"
                return cch_result
        elif cch_result.path:
            cch_result.algorithm_used = "HYBRID"
            return cch_result
        elif scenic_result.path:
            scenic_result.algorithm_used = "HYBRID"
            return scenic_result
        else:
            return RouteResult(
                path=[], algorithm_used="HYBRID", total_distance=0, estimated_time=0,
                metadata={"error": "모든 알고리즘에서 경로를 찾을 수 없음"}
            )
    
    def _find_nearest_vertex(self, lat: float, lon: float) -> Optional[Vertex]:
        """가장 가까운 정점 찾기"""
        if not self.graph or not self.graph.vertices:
            return None
        
        min_distance = float('inf')
        nearest_vertex = None
        
        # Graph.vertices는 Dict[int, Vertex]이므로 values()를 사용
        for vertex in self.graph.vertices.values():
            # vertex 객체에 lat, lon 속성이 있는지 확인
            if hasattr(vertex, 'lat') and hasattr(vertex, 'lon'):
                distance = self._calculate_distance(lat, lon, vertex.lat, vertex.lon)
                if distance < min_distance:
                    min_distance = distance
                    nearest_vertex = vertex
        
        return nearest_vertex
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """두 지점 간 거리 계산"""
        R = 6371
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

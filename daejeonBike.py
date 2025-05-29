import heapq
import requests
import json
from dataclasses import dataclass
from typing import List, Set, Dict, Optional, Tuple, Any
import warnings
import subprocess
from cch import Graph, Vertex, Arc


class DaejeonBikeAPI:
    """
    대전광역시 자전거 도로 정보 API 클래스
    데이터포맷: JSON, API형태: REST
    대전광역시 자전거 도로 정보 서비스 API 사용
    자전거 도로 정보 제공
    """
    def __init__(self):
        # API 키 설정
        self.api_key = ""
        
        # URL에 사용하기 위해 인코딩된 API 키
        self.encoded_api_key = ""
        
        # API 기본 URL
        self.base_url = "https://apis.data.go.kr/6300000/BicycleRoadService/"
        
        # API 엔드포인트
        self.bike_path_list_endpoint = "getBicycleRoadList"
    
    def get_bike_routes(self, page_no=1, num_of_rows=10):
        """
        대전광역시 자전거 도로 정보를 가져옵니다.
        GetBycpListService 엔드포인트를 사용하여 자전거 도로 정보를 가져옵니다.
        
        Args:
            page_no (int): 페이지 번호
            num_of_rows (int): 한 페이지 결과 수
            
        Returns:
            dict: API 응답 결과
        """
        try:
            print(f"\n대전광역시 자전거 도로 정보 요청 중...")
            
            # API URL 생성
            url = f"{self.base_url}{self.bike_path_list_endpoint}"
            params = {
                'serviceKey': self.encoded_api_key,
                'pageNo': page_no,
                'numOfRows': num_of_rows,
                'type': 'json'  # JSON 형식으로 응답 요청
            }
            
            # 요청 URL 출력
            request_url = f"{url}?serviceKey={self.encoded_api_key}&pageNo={page_no}&numOfRows={num_of_rows}&type=json"
            print(f"API 요청 URL: {request_url}")
            
            # SSL 경고 무시
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                # 1. requests를 사용한 요청
                try:
                    # SSL 경고 비활성화
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
                        'Accept': 'application/json',
                        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
                    }
                    response = requests.get(request_url, headers=headers, verify=False, timeout=10)
                    
                    if response.status_code == 200:
                        try:
                            # JSON 응답 파싱
                            result = response.json()
                            
                            # 자전거 도로 정보 출력
                            if 'response' in result and 'body' in result['response'] and 'items' in result['response']['body']:
                                items = result['response']['body']['items']
                                if 'item' in items:
                                    bike_items = items['item']
                                    if not isinstance(bike_items, list):
                                        bike_items = [bike_items]
                                    
                                    print(f"자전거 도로 정보 {len(bike_items)}개 발견")
                                    
                                    # 처음 5개만 출력
                                    for i, item in enumerate(bike_items[:5]):
                                        print(f"\n자전거도로 {i+1}: {item.get('CTPRVNNM', 'N/A')} {item.get('SIGNGU_NM', 'N/A')} {item.get('ROAD_ROUTE_NM', 'N/A')}")
                                        print(f"  - 시작점: 위도 {item.get('START_LATITUDE', 'N/A')}, 경도 {item.get('START_LONGITUDE', 'N/A')}")
                                        print(f"  - 종점: 위도 {item.get('END_LATITUDE', 'N/A')}, 경도 {item.get('END_LONGITUDE', 'N/A')}")
                                        print(f"  - 길이: {item.get('TOTAL_LENGTH', 'N/A')}km, 너비: {item.get('BIKE_ROAD_WIDTH', 'N/A')}m")
                                        print(f"  - 유형: {item.get('BIKE_ROAD_TYPE', 'N/A')}")
                                        print(f"  - 노선번호: {item.get('ROAD_ROUTE_NO', 'N/A')}")
                                        print(f"  - 주요 경유지: {item.get('MAJOR_STOPOVER', 'N/A')}")
                                        print(f"  - 시작지점: {item.get('ROAD_ST_POINT', 'N/A')}")
                                        print(f"  - 종료지점: {item.get('ROAD_ED_POINT', 'N/A')}")
                                        print(f"  - 고시 여부: {item.get('BIKE_ROAD_NOTI_CHK', 'N/A')}")
                                        print(f"  - 참조일자: {item.get('REFERENCEDATE', 'N/A')}")
                                        print(f"  - 일반도로 너비: {item.get('ROADBT', 'N/A')}m")
                                else:
                                    print("자전거 도로 정보가 없습니다.")
                            else:
                                print("자전거 도로 정보가 없습니다.")
                                
                            # API 응답을 대전광역시 자전거 도로 API 형식에 맞게 변환
                            response_data = {
                                'BicycleRoadService': {
                                    'header': result.get('response', {}).get('header', {}),
                                    'item': bike_items if 'response' in result and 'body' in result['response'] and 
                                            'items' in result['response']['body'] and 'item' in result['response']['body']['items'] else []
                                }
                            }
                            
                            return response_data
                            
                        except json.JSONDecodeError:
                            print("JSON 파싱 오류")
                    else:
                        print(f"API 요청 오류: 상태 코드 {response.status_code}")
                        
                except Exception as e:
                    print(f"requests 요청 오류: {e}")
                
                # 2. curl을 사용한 백업 요청
                try:
                    print("requests 요청 실패, curl을 사용하여 재시도합니다...")
                    curl_command = [
                        'curl',
                        '-s',  # 조용한 모드
                        '-k',  # SSL 인증서 검증 무시
                        '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
                        '-H', 'Accept: application/json',
                        '-H', 'Accept-Language: ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                        '--connect-timeout', '10',
                        request_url
                    ]
                    
                    result = subprocess.run(curl_command, capture_output=True, text=True)
                    
                    if result.returncode == 0 and result.stdout:
                        try:
                            # JSON 응답 파싱
                            data = json.loads(result.stdout)
                            print("curl을 통한 요청 성공")
                            
                            # 응답 데이터 구조 확인
                            if 'response' in data:
                                print("API 응답 구조 확인 성공")
                                
                                # API 응답을 대전광역시 자전거 도로 API 형식에 맞게 변환
                                response_data = {
                                    'BicycleRoadService': {
                                        'header': data.get('response', {}).get('header', {}),
                                        'item': data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                                    }
                                }
                                
                                # 응답 헤더 확인
                                header = response_data['GetBycpListService']['header']
                                if header:
                                    print(f"API 응답 코드: {header.get('resultCode', 'N/A')}, 메시지: {header.get('resultMsg', 'N/A')}")
                                
                                return response_data
                            else:
                                print("API 응답 구조가 예상과 다릅니다.")
                                print(f"API 응답 내용: {data}")
                        except json.JSONDecodeError as e:
                            print(f"JSON 파싱 오류: {e}")
                            print(f"API 응답 내용: {result.stdout[:200]}...")
                    else:
                        print(f"curl 요청 실패 (exit code: {result.returncode})")
                        if result.stderr:
                            print(f"curl 오류: {result.stderr}")
                        if result.stdout:
                            print(f"curl 출력: {result.stdout[:200]}...")
                except Exception as e:
                    print(f"curl 요청 오류: {e}")
            
            print("\n모든 API 요청 방법이 실패했습니다.")
            print("API 서비스가 일시적으로 중단되었거나 접근할 수 없습니다.")
            return None
            
        except Exception as e:
            print(f"API 요청 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def create_graph_from_api_data(self, bike_routes_data):
        """
        대전광역시 자전거도로조회서비스 API 데이터로부터 그래프를 생성합니다.
        
        Args:
            bike_routes_data (dict): API 응답 데이터
            
        Returns:
            Graph: 생성된 그래프 객체
        """
        import math
        graph = Graph()
        
        # API 데이터가 없는 경우 빈 그래프 반환
        if not bike_routes_data:
            print("유효한 API 데이터가 없습니다.")
            return graph
            
        # API 데이터 형식 확인
        if 'BicycleRoadService' not in bike_routes_data:
            print("올바른 API 데이터 형식이 아닙니다.")
            return graph
        
        try:
            # 자전거 도로 정보 추출
            items = bike_routes_data.get('BicycleRoadService', {}).get('item', [])
            
            # 리스트가 아닌 경우 리스트로 변환
            if isinstance(items, dict):
                items = [items]
            
            if not items:
                print("자전거 도로 정보가 없습니다.")
                return graph
                
            print(f"자전거 도로 정보 {len(items)}개 발견")
            
            # 정점 생성
            vertices = {}
            vertex_id = 0
            
            # 각 자전거 도로를 정점으로 처리
            for item in items:
                # 시작점과 종점의 위도/경도 정보 추출
                start_lat = item.get('START_LATITUDE')
                start_lon = item.get('START_LONGITUDE')
                end_lat = item.get('END_LATITUDE')
                end_lon = item.get('END_LONGITUDE')
                name = f"{item.get('CTPRVNNM', '')} {item.get('SIGNGU_NM', '')} {item.get('ROAD_ROUTE_NM', '이름 없음')}".strip()
                
                # 시작점과 종점 정보가 모두 있는지 확인
                if not start_lat or not start_lon or not end_lat or not end_lon:
                    print(f"[경고] 자전거 도로 '{name}'의 위치 정보가 없습니다.")
                    continue
                
                try:
                    # 문자열을 실수형으로 변환
                    start_lat = float(start_lat)
                    start_lon = float(start_lon)
                    end_lat = float(end_lat)
                    end_lon = float(end_lon)
                    
                    # 시작점 정점 생성
                    start_vertex = Vertex(vertex_id, start_lat, start_lon)
                    graph.add_vertex(start_vertex)
                    vertices[vertex_id] = start_vertex
                    start_vertex_id = vertex_id
                    vertex_id += 1
                    
                    # 종점 정점 생성
                    end_vertex = Vertex(vertex_id, end_lat, end_lon)
                    graph.add_vertex(end_vertex)
                    vertices[vertex_id] = end_vertex
                    end_vertex_id = vertex_id
                    vertex_id += 1
                    
                    # 시작점과 종점 사이의 거리 계산
                    distance = self._calculate_distance(start_lat, start_lon, end_lat, end_lon)
                    
                    # 시작점과 종점을 연결하는 간선 추가
                    arc1 = Arc(start_vertex, end_vertex, distance)
                    arc2 = Arc(end_vertex, start_vertex, distance)
                    graph.add_arc(arc1)
                    graph.add_arc(arc2)
                    
                    print(f"  간선 추가: {start_vertex_id} -> {end_vertex_id} (거리: {distance:.2f}km)")
                    
                except ValueError:
                    print(f"[경고] 자전거 도로 '{name}'의 위치 정보가 유효하지 않습니다.")
            
            # 정점이 없는 경우 빈 그래프 반환
            if len(vertices) < 2:
                print("그래프 생성을 위한 충분한 정점이 없습니다.")
                return graph
            
            # 각 정점의 좌표를 기반으로 가까운 정점들을 연결하여 네트워크 구성
            vertex_ids = list(vertices.keys())
            
            # 가까운 정점들을 연결하여 네트워크 구성
            print("\n가까운 정점들을 연결하여 네트워크 구성 중...")
            connection_count = 0
            
            for i in range(len(vertex_ids)):
                for j in range(i+1, len(vertex_ids)):
                    # 이미 연결된 정점인지 확인
                    v1_id = vertex_ids[i]
                    v2_id = vertex_ids[j]
                    
                    # 이미 간선이 있는지 확인
                    if (v1_id, v2_id) in graph.arcs:
                        continue
                        
                    v1 = vertices[v1_id]
                    v2 = vertices[v2_id]
                    
                    # 두 정점 간의 거리 계산
                    distance = self._calculate_distance(v1.lat, v1.lon, v2.lat, v2.lon)
                    
                    # 일정 거리 이내의 정점만 연결 (2km 이내)
                    if distance < 2.0:
                        # 간선 추가
                        arc1 = Arc(v1, v2, distance)
                        arc2 = Arc(v2, v1, distance)
                        graph.add_arc(arc1)
                        graph.add_arc(arc2)
                        connection_count += 1
                        
                        # 추가 연결 정보 출력 (처음 10개만)
                        if connection_count <= 10:
                            print(f"  추가 간선: {v1_id} -> {v2_id} (거리: {distance:.2f}km)")
            
            if connection_count > 10:
                print(f"  ... 추가 {connection_count - 10}개의 간선 연결이 생략되었습니다.")
            
            print(f"그래프 생성 완료: {len(graph.vertices)}개의 정점, {len(graph.arcs)}개의 간선")
            return graph
            
        except Exception as e:
            print(f"그래프 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            return graph
    
    # GPX 관련 메서드는 삭제하고 JSON을 사용하도록 변경
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        두 지점 간의 거리를 계산합니다 (Haversine 공식 사용).
        
        Args:
            lat1, lon1: 첫 번째 지점의 위도/경도
            lat2, lon2: 두 번째 지점의 위도/경도
            
        Returns:
            float: 두 지점 간의 거리 (km)
        """
        from math import radians, sin, cos, sqrt, atan2
        
        # 지구 반경 (km)
        R = 6371.0
        
        # 위도/경도를 라디안으로 변환
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # Haversine 공식
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance  # 거리(km)
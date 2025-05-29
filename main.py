import sys
from typing import Dict, List, Tuple, Optional

from daejeonBike import DaejeonBikeAPI
from cch import CustomizableContractionHierarchies, Graph, Vertex, Arc


def fetch_bike_routes(num_of_rows: int = 30) -> Optional[Dict]:
    """
    대전광역시 자전거 도로 데이터를 가져옵니다.
    
    Args:
        num_of_rows: 가져올 데이터 개수
        
    Returns:
        자전거 도로 데이터 또는 None (실패 시)
    """
    # 대전광역시 자전거 도로 API 인스턴스 생성
    daejeon_bike_api = DaejeonBikeAPI()
    
    # 대전광역시 자전거 도로 데이터 가져오기
    print("대전광역시 자전거 도로 데이터 요청 중...")
    bike_routes = daejeon_bike_api.get_bike_routes(page_no=1, num_of_rows=num_of_rows)
    print("API 요청 완료")
    
    # API 응답 디버깅
    if bike_routes:
        header = bike_routes.get('BicycleRoadService', {}).get('header', {})
        result_code = header.get('resultCode', '')
        result_msg = header.get('resultMsg', '')
        print(f"API 응답 코드: {result_code}, 메시지: {result_msg}")
        return bike_routes
    else:
        print("API 응답을 받지 못했습니다.")
        return None


def create_bike_route_graph(bike_routes: Dict) -> Graph:
    """
    자전거 도로 데이터로부터 그래프를 생성합니다.
    
    Args:
        bike_routes: 자전거 도로 API 응답 데이터
        
    Returns:
        생성된 그래프
    """
    daejeon_bike_api = DaejeonBikeAPI()
    return daejeon_bike_api.create_graph_from_api_data(bike_routes)


def preprocess_graph(graph: Graph) -> Optional[CustomizableContractionHierarchies]:
    """
    그래프에 대해 CCH 알고리즘의 전처리 단계를 수행합니다.
    
    Args:
        graph: 처리할 그래프
        
    Returns:
        CCH 인스턴스 또는 None (실패 시)
    """
    if len(graph.vertices) < 2:
        print("그래프 생성을 위한 충분한 정점이 없습니다.")
        return None
        
    # 1. 메트릭 독립적 전처리 단계 실행
    print("\n1. 메트릭 독립적 전처리 단계 실행...")
    cch = CustomizableContractionHierarchies(graph)
    cch.metric_independent_preprocessing(len(graph.vertices))
    
    # 2. 커스터마이징 단계 - 실제 간선 비용 적용
    print("\n2. 커스터마이징 단계 - 실제 간선 비용 적용...")
    cch.customize()
    
    return cch


def dijkstra(graph: Graph, start_id: int, end_id: int) -> List[Arc]:
    """
    다익스트라 알고리즘을 사용하여 최단 경로를 찾습니다.
    
    Args:
        graph: 그래프
        start_id: 시작 정점 ID
        end_id: 도착 정점 ID
        
    Returns:
        경로 (Arc 리스트)
    """
    import heapq
    
    # 시작 정점과 도착 정점이 존재하는지 확인
    if start_id not in graph.vertices or end_id not in graph.vertices:
        return []
    
    # 최단 거리 초기화
    distances = {vertex_id: float('infinity') for vertex_id in graph.vertices}
    distances[start_id] = 0
    
    # 이전 정점 추적을 위한 디셔너리
    previous = {}
    
    # 우선순위 큐 초기화
    priority_queue = [(0, start_id)]
    
    while priority_queue:
        current_distance, current_vertex_id = heapq.heappop(priority_queue)
        
        # 도착 정점에 도착했다면 중단
        if current_vertex_id == end_id:
            break
            
        # 현재 검토 중인 거리가 이미 알고 있는 최단 거리보다 크면 건너뛬
        if current_distance > distances[current_vertex_id]:
            continue
            
        # 인접 정점 탐색
        for (src, dst), arc in graph.arcs.items():
            if src == current_vertex_id:
                neighbor_id = dst
                distance = arc.cost
                
                # 새로운 거리 계산
                new_distance = current_distance + distance
                
                # 새 거리가 기존 거리보다 짧으면 갱신
                if new_distance < distances[neighbor_id]:
                    distances[neighbor_id] = new_distance
                    previous[neighbor_id] = (current_vertex_id, arc)
                    heapq.heappush(priority_queue, (new_distance, neighbor_id))
    
    # 경로가 없는 경우
    if end_id not in previous and start_id != end_id:
        return []
        
    # 경로 재구성
    path = []
    current_id = end_id
    
    while current_id != start_id:
        prev_id, arc = previous[current_id]
        path.append(arc)
        current_id = prev_id
        
    # 경로 순서 뒤집기
    path.reverse()
    
    return path


def find_shortest_path(graph: Graph, cch: CustomizableContractionHierarchies, start_id: int, end_id: int) -> List[Arc]:
    """
    두 정점 간의 최단 경로를 찾습니다.
    CCH 알고리즘을 사용하고, 실패하면 다익스트라 알고리즘을 사용합니다.
    
    Args:
        graph: 그래프
        cch: CCH 인스턴스
        start_id: 시작 정점 ID
        end_id: 도착 정점 ID
        
    Returns:
        경로 (Arc 리스트)
    """
    path = []
    
    # 직접 간선이 있는지 확인
    start_arc = graph.arcs.get((start_id, end_id))
    if start_arc:
        cch.unpack_path(start_arc, path)
        if path:
            return path
    
    # 직접 간선이 없거나 CCH로 경로를 찾지 못한 경우 다익스트라 알고리즘 사용
    print(f"  직접 간선이 없거나 CCH로 경로를 찾지 못했습니다: {start_id} -> {end_id}")
    print("  다익스트라 알고리즘을 사용하여 경로를 찾습니다...")
    
    # 다익스트라 알고리즘으로 경로 찾기
    path = dijkstra(graph, start_id, end_id)
    
    return path


def print_path_info(path: List[Arc]) -> None:
    """
    경로 정보를 출력합니다.
    
    Args:
        path: 경로 (Arc 리스트)
    """
    if not path:
        print("  경로를 찾을 수 없습니다.")
        return
        
    total_cost = 0
    print("\n경로 정보:")
    for arc in path:
        print(f"  {arc.source.id} -> {arc.target.id} (비용: {arc.cost:.2f}km)")
        total_cost += arc.cost
    print(f"\n총 거리: {total_cost:.2f}km")


def print_vertex_info(graph: Graph) -> None:
    """
    그래프의 정점 정보를 출력합니다.
    
    Args:
        graph: 그래프
    """
    print("\n정점 정보:")
    for vertex_id, vertex in graph.vertices.items():
        print(f"  정점 {vertex_id}: 위도 {vertex.lat}, 경도 {vertex.lon}")


def create_example_data() -> Dict:
    """
    API 요청이 실패할 경우를 대비한 예제 데이터를 생성합니다.
    
    Returns:
        자전거 도로 API 응답 형식의 예제 데이터
    """
    print("\n예제 데이터를 사용합니다.")
    
    # 대전의 주요 자전거 도로 좌표 (예시)
    example_items = [
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "서구",
            "ROAD_ROUTE_NM": "대전역 자전거도로",
            "ROAD_ST_POINT": "대전역",
            "ROAD_ED_POINT": "중앙로",
            "START_LATITUDE": "36.332583",
            "START_LONGITUDE": "127.434361",
            "END_LATITUDE": "36.327123",
            "END_LONGITUDE": "127.427891",
            "MAJOR_STOPOVER": "대전역, 중앙로",
            "TOTAL_LENGTH": "2.5",
            "ROADBT": "12.0",
            "BIKE_ROAD_WIDTH": "2.0",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "1"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "중구",
            "ROAD_ROUTE_NM": "중앙로 자전거도로",
            "ROAD_ST_POINT": "중앙로",
            "ROAD_ED_POINT": "대덕구",
            "START_LATITUDE": "36.327123",
            "START_LONGITUDE": "127.427891",
            "END_LATITUDE": "36.347234",
            "END_LONGITUDE": "127.419765",
            "MAJOR_STOPOVER": "중앙로, 대덕구",
            "TOTAL_LENGTH": "3.2",
            "ROADBT": "15.0",
            "BIKE_ROAD_WIDTH": "1.8",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "2"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "대덕구",
            "ROAD_ROUTE_NM": "대덕구 자전거도로",
            "ROAD_ST_POINT": "대덕구",
            "ROAD_ED_POINT": "서대전역",
            "START_LATITUDE": "36.347234",
            "START_LONGITUDE": "127.419765",
            "END_LATITUDE": "36.321567",
            "END_LONGITUDE": "127.408912",
            "MAJOR_STOPOVER": "대덕구, 서대전역",
            "TOTAL_LENGTH": "4.1",
            "ROADBT": "10.0",
            "BIKE_ROAD_WIDTH": "2.2",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "3"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "서구",
            "ROAD_ROUTE_NM": "서대전역 자전거도로",
            "ROAD_ST_POINT": "서대전역",
            "ROAD_ED_POINT": "유성구",
            "START_LATITUDE": "36.321567",
            "START_LONGITUDE": "127.408912",
            "END_LATITUDE": "36.362145",
            "END_LONGITUDE": "127.442378",
            "MAJOR_STOPOVER": "서대전역, 유성구",
            "TOTAL_LENGTH": "2.8",
            "ROADBT": "8.0",
            "BIKE_ROAD_WIDTH": "1.5",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "4"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "유성구",
            "ROAD_ROUTE_NM": "유성구 자전거도로",
            "ROAD_ST_POINT": "유성구",
            "ROAD_ED_POINT": "동구",
            "START_LATITUDE": "36.362145",
            "START_LONGITUDE": "127.442378",
            "END_LATITUDE": "36.338912",
            "END_LONGITUDE": "127.456789",
            "MAJOR_STOPOVER": "유성구, 동구",
            "TOTAL_LENGTH": "3.5",
            "ROADBT": "14.0",
            "BIKE_ROAD_WIDTH": "2.0",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "5"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "동구",
            "ROAD_ROUTE_NM": "동구 자전거도로",
            "ROAD_ST_POINT": "동구",
            "ROAD_ED_POINT": "대전공원",
            "START_LATITUDE": "36.338912",
            "START_LONGITUDE": "127.456789",
            "END_LATITUDE": "36.352678",
            "END_LONGITUDE": "127.431234",
            "MAJOR_STOPOVER": "동구, 대전공원",
            "TOTAL_LENGTH": "2.9",
            "ROADBT": "9.0",
            "BIKE_ROAD_WIDTH": "1.7",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "6"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "중구",
            "ROAD_ROUTE_NM": "대전공원 자전거도로",
            "ROAD_ST_POINT": "대전공원",
            "ROAD_ED_POINT": "유성로",
            "START_LATITUDE": "36.352678",
            "START_LONGITUDE": "127.431234",
            "END_LATITUDE": "36.358901",
            "END_LONGITUDE": "127.438765",
            "MAJOR_STOPOVER": "대전공원, 유성로",
            "TOTAL_LENGTH": "5.2",
            "ROADBT": "18.0",
            "BIKE_ROAD_WIDTH": "2.5",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "7"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "유성구",
            "ROAD_ROUTE_NM": "유성로 자전거도로",
            "ROAD_ST_POINT": "유성로",
            "ROAD_ED_POINT": "대전천",
            "START_LATITUDE": "36.358901",
            "START_LONGITUDE": "127.438765",
            "END_LATITUDE": "36.342345",
            "END_LONGITUDE": "127.423456",
            "MAJOR_STOPOVER": "유성로, 대전천",
            "TOTAL_LENGTH": "3.8",
            "ROADBT": "16.0",
            "BIKE_ROAD_WIDTH": "2.0",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "8"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "중구",
            "ROAD_ROUTE_NM": "대전천 자전거도로",
            "ROAD_ST_POINT": "대전천",
            "ROAD_ED_POINT": "서구",
            "START_LATITUDE": "36.342345",
            "START_LONGITUDE": "127.423456",
            "END_LATITUDE": "36.318765",
            "END_LONGITUDE": "127.401234",
            "MAJOR_STOPOVER": "대전천, 서구",
            "TOTAL_LENGTH": "6.5",
            "ROADBT": "20.0",
            "BIKE_ROAD_WIDTH": "3.0",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "9"
        },
        {
            "CTPRVNNM": "대전광역시",
            "SIGNGU_NM": "서구",
            "ROAD_ROUTE_NM": "서구 자전거도로",
            "ROAD_ST_POINT": "서구",
            "ROAD_ED_POINT": "대전역",
            "START_LATITUDE": "36.318765",
            "START_LONGITUDE": "127.401234",
            "END_LATITUDE": "36.332583",
            "END_LONGITUDE": "127.434361",
            "MAJOR_STOPOVER": "서구, 대전역",
            "TOTAL_LENGTH": "4.2",
            "ROADBT": "13.0",
            "BIKE_ROAD_WIDTH": "2.1",
            "BIKE_ROAD_TYPE": "자전거전용도로",
            "BIKE_ROAD_NOTI_CHK": "Y",
            "REFERENCEDATE": "2023-12-31",
            "ROAD_ROUTE_NO": "10"
        }
    ]
    
    # API 응답 형식에 맞게 데이터 구성
    example_data = {
        'BicycleRoadService': {
            'header': {
                'resultCode': '00',
                'resultMsg': 'NORMAL SERVICE.'
            },
            'item': example_items
        }
    }
    
    return example_data





def daejeon_bike_cch_example() -> Graph:
    """
    대전광역시 자전거 도로 API와 CCH 알고리즘을 결합한 예제
    
    Returns:
        생성된 그래프
    """
    # 1. 자전거 도로 데이터 가져오기
    bike_routes = fetch_bike_routes(num_of_rows=50)
    
    # API 요청이 실패한 경우
    if not bike_routes:
        print("자전거 도로 데이터를 가져오는데 실패했습니다.")
        print("예제 데이터를 사용하여 계속합니다.")
        bike_routes = create_example_data()
    
    # 2. 그래프 생성
    graph = create_bike_route_graph(bike_routes)
    if len(graph.vertices) < 2:
        print("그래프 생성을 위한 충분한 정점이 없습니다.")
        return graph
    
    # 3. 정점 정보 출력
    print_vertex_info(graph)
    
    # 4. 그래프 전처리
    cch = preprocess_graph(graph)
    if not cch:
        return graph
    
    # 5. 간선 비용 출력 (처음 5개 정점 간의 간선만)
    print("\n업데이트된 간선 비용:")
    for (source_id, target_id), arc in graph.arcs.items():
        if source_id < 5 and target_id < 5:
            print(f"  {source_id} -> {target_id}: {arc.cost:.2f}km")
    
    # 6. 사용자 입력으로 경로 계산
    try:
        print("\n경로 계산을 위한 정점 ID를 입력하세요.")
        print(f"사용 가능한 정점 ID: 0 ~ {len(graph.vertices)-1}")
        
        start_id = int(input("시작 정점 ID: "))
        end_id = int(input("도착 정점 ID: "))
        
        if start_id not in graph.vertices or end_id not in graph.vertices:
            print("유효하지 않은 정점 ID입니다.")
        else:
            # 경로 계산
            print(f"\n{start_id}->{end_id} 경로 계산 중...")
            path = find_shortest_path(graph, cch, start_id, end_id)
            print_path_info(path)
    except ValueError:
        print("숫자를 입력해주세요.")
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    
    print("\n대전광역시 자전거 도로 데이터를 이용한 CCH 알고리즘 예제 완료")
    return graph


def main():
    """
    메인 함수
    """
    print("대전광역시 자전거 도로 API와 CCH 알고리즘 예제 실행\n")
    daejeon_bike_cch_example()


# 프로그램 시작점
if __name__ == "__main__":
    main()


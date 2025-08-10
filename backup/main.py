import sys
import os
import certifi
import urllib3
from typing import Dict, List, Tuple, Optional

# SSL 경고 비활성화 (개발 환경에서만 사용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# daejeonBike.py에서 API 데이터 가져오는 함수 임포트
from daejeonBike import get_bike_route_data, get_bike_storage_data
# cch.py에서 알고리즘 관련 클래스 임포트
from cch import CustomizableContractionHierarchies, Graph, Vertex, Arc


def fetch_bike_routes(num_of_rows: int = 30) -> Optional[List]:
    """
    대전광역시 자전거 도로 데이터를 가져옵니다.
    
    Args:
        num_of_rows: 가져올 데이터 개수
        
    Returns:
        자전거 도로 데이터 목록 또는 None (실패 시)
    """
    # daejeonBike.py의 함수를 사용하여 데이터 가져오기
    print("대전광역시 자전거 도로 데이터 요청 중...")
    bike_routes = get_bike_route_data(page_no=1, num_of_rows=num_of_rows)
    print("API 요청 완료")
    
    # API 응답 확인
    if bike_routes:
        print(f"자전거 도로 데이터 {len(bike_routes)}개를 받았습니다.")
        return bike_routes
    else:
        print("API 응답을 받지 못했습니다.")
        return None


def fetch_bike_storage(num_of_rows: int = 30) -> Optional[List]:
    """
    대전광역시 자전거 보관소 데이터를 가져옵니다.
    
    Args:
        num_of_rows: 가져올 데이터 개수
        
    Returns:
        자전거 보관소 데이터 목록 또는 None (실패 시)
    """
    # daejeonBike.py의 함수를 사용하여 데이터 가져오기
    print("대전광역시 자전거 보관소 데이터 요청 중...")
    bike_storage = get_bike_storage_data(page_no=1, num_of_rows=num_of_rows)
    print("API 요청 완료")
    
    # API 응답 확인
    if bike_storage:
        print(f"자전거 보관소 데이터 {len(bike_storage)}개를 받았습니다.")
        return bike_storage
    else:
        print("API 응답을 받지 못했습니다.")
        return None


def create_bike_route_graph(bike_routes: List) -> Graph:
    """
    자전거 도로 데이터로부터 그래프를 생성합니다.
    
    Args:
        bike_routes: 자전거 도로 데이터 목록
        
    Returns:
        생성된 그래프
    """
    # 그래프 생성
    graph = Graph()
    
    # 정점 ID 카운터
    vertex_id = 0
    
    # 정점 좌표 매핑 (중복 방지)
    coord_to_vertex = {}
    
    # 각 자전거 도로에 대해 처리
    for route in bike_routes:
        # 시작점과 도착점 좌표 가져오기
        try:
            start_lat = float(route.get('START_LATITUDE', 0))
            start_lon = float(route.get('START_LONGITUDE', 0))
            end_lat = float(route.get('END_LATITUDE', 0))
            end_lon = float(route.get('END_LONGITUDE', 0))
            distance = float(route.get('TOTAL_LENGTH', 0))
            
            # 좌표가 유효한지 확인
            if start_lat == 0 or start_lon == 0 or end_lat == 0 or end_lon == 0:
                continue
                
            # 시작점 정점 추가
            start_coord = (start_lat, start_lon)
            if start_coord in coord_to_vertex:
                start_vertex = graph.vertices[coord_to_vertex[start_coord]]
            else:
                start_vertex = Vertex(id=vertex_id, lat=start_lat, lon=start_lon)
                graph.add_vertex(start_vertex)
                coord_to_vertex[start_coord] = vertex_id
                vertex_id += 1
                
            # 도착점 정점 추가
            end_coord = (end_lat, end_lon)
            if end_coord in coord_to_vertex:
                end_vertex = graph.vertices[coord_to_vertex[end_coord]]
            else:
                end_vertex = Vertex(id=vertex_id, lat=end_lat, lon=end_lon)
                graph.add_vertex(end_vertex)
                coord_to_vertex[end_coord] = vertex_id
                vertex_id += 1
                
            # 간선 추가 (양방향)
            graph.add_arc(Arc(source=start_vertex, target=end_vertex, cost=distance))
            graph.add_arc(Arc(source=end_vertex, target=start_vertex, cost=distance))
            
        except (ValueError, TypeError) as e:
            print(f"자전거 도로 데이터 처리 오류: {e}")
            continue
    
    print(f"그래프 생성 완료: {len(graph.vertices)}개의 정점, {len(graph.arcs)}개의 간선")
    return graph


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
    
    # 0. 정점에 고유한 랭크 할당 (중요: CCH 알고리즘이 제대로 작동하려면 필요)
    print("\n0. 정점 랭크 할당...")
    assign_vertex_ranks(graph)
        
    # 1. 메트릭 독립적 전처리 단계 실행
    print("\n1. 메트릭 독립적 전처리 단계 실행...")
    cch = CustomizableContractionHierarchies(graph)
    cch.metric_independent_preprocessing(len(graph.vertices))
    
    # 2. 커스터마이징 단계 - 실제 간선 비용 적용
    print("\n2. 커스터마이징 단계 - 실제 간선 비용 적용...")
    cch.customize()
    
    return cch


def assign_vertex_ranks(graph: Graph):
    """
    그래프의 정점에 랭크를 할당합니다.
    정점의 연결성(인접 간선 수)에 기반한 랭크를 부여합니다.
    연결성이 높을수록 더 높은 랭크가 부여됩니다.
    
    Args:
        graph: 랭크를 할당할 그래프
    """
    # 1. 각 정점의 연결성 계산 (인접 간선 수)
    vertex_importance = {}
    
    for vertex_id, vertex in graph.vertices.items():
        # 인접한 간선의 수 계산
        adjacent_arcs = 0
        
        for (src, dst), _ in graph.arcs.items():
            if src == vertex_id or dst == vertex_id:
                adjacent_arcs += 1
        
        # 정점의 중요도 저장 (간선 수 기반)
        vertex_importance[vertex_id] = adjacent_arcs
    
    # 2. 정점들을 연결성 기준으로 내림차순 정렬
    sorted_vertices = sorted(vertex_importance.items(), key=lambda x: x[1], reverse=True)
    
    # 3. 각 정점에 랭크 할당 (연결성이 높을수록 높은 랭크 할당)
    total_vertices = len(sorted_vertices)
    for rank, (vertex_id, importance) in enumerate(sorted_vertices):
        vertex = graph.vertices[vertex_id]
        # 랭크는 0부터 시작하며, 높은 값이 더 중요한 정점
        vertex.rank = total_vertices - rank - 1
    
    print(f"정점 {total_vertices}개에 연결성 기반 랭크 할당 완료 (0 ~ {total_vertices - 1})")
    
    # 디버깅을 위해 일부 정점의 랭크 출력
    sample_size = min(5, total_vertices)
    for i in range(sample_size):
        vertex_id = sorted_vertices[i][0]
        vertex = graph.vertices[vertex_id]
        print(f"  정점 {vertex_id}: 연결성 {sorted_vertices[i][1]}, 랭크 {vertex.rank}")
    
    return


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


def enhance_graph_connectivity(graph: Graph, distance_threshold: float = 0.1) -> int:
    """
    그래프의 연결성을 개선합니다.
    근접한 정점들을 연결하여 분리된 컴포넌트를 연결합니다.
    
    Args:
        graph: 그래프
        distance_threshold: 두 정점 간의 최대 거리 (km)
        
    Returns:
        추가된 간선의 수
    """
    import math
    
    # 하버사인 공식으로 두 정점 간의 거리 계산 (km 단위)
    def calculate_distance(v1: Vertex, v2: Vertex) -> float:
        lat1, lon1 = math.radians(v1.lat), math.radians(v1.lon)
        lat2, lon2 = math.radians(v2.lat), math.radians(v2.lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # 지구 반지름 (km)
        R = 6371.0
        distance = R * c
        
        return distance
    
    # 연결 요소 찾기 (DFS 사용)
    def find_connected_components(graph: Graph):
        visited = set()
        components = []
        
        def dfs(vertex_id, component):
            visited.add(vertex_id)
            component.append(vertex_id)
            
            # 인접한 정점 탐색
            for arc_key, arc in graph.arcs.items():
                if arc.source.id == vertex_id and arc.target.id not in visited:
                    dfs(arc.target.id, component)
                elif arc.target.id == vertex_id and arc.source.id not in visited:
                    dfs(arc.source.id, component)
        
        # 모든 정점에 대해 DFS 수행
        for vertex_id in graph.vertices:
            if vertex_id not in visited:
                component = []
                dfs(vertex_id, component)
                components.append(component)
        
        return components
    
    # 연결 요소 찾기
    components = find_connected_components(graph)
    print(f"\n그래프 연결성 분석: {len(components)}개의 분리된 컴포넌트 발견")
    
    # 각 컴포넌트의 크기 출력
    for i, component in enumerate(components):
        print(f"  컴포넌트 {i+1}: {len(component)}개 정점")
    
    # 컴포넌트 간 연결
    edges_added = 0
    
    # 각 컴포넌트의 대표 정점 (첫 번째 정점) 사용
    representatives = [comp[0] for comp in components if comp]
    
    # 근접한 정점들 찾아 연결
    for i, v1_id in enumerate(representatives[:-1]):
        v1 = graph.vertices.get(v1_id)
        if not v1:
            continue
            
        # 가장 가까운 다른 컴포넌트 찾기
        closest_distance = float('inf')
        closest_vertex = None
        
        for v2_id in representatives[i+1:]:
            v2 = graph.vertices.get(v2_id)
            if not v2:
                continue
                
            distance = calculate_distance(v1, v2)
            if distance < closest_distance:
                closest_distance = distance
                closest_vertex = v2
        
        # 가장 가까운 정점과 연결
        if closest_vertex and closest_distance < 10:  # 10km 이내 정점만 연결
            # 양방향 간선 추가
            arc1 = Arc(v1, closest_vertex, closest_distance)
            arc2 = Arc(closest_vertex, v1, closest_distance)
            
            graph.add_arc(arc1)
            graph.add_arc(arc2)
            
            edges_added += 2
            print(f"  연결 추가: {v1.id} <-> {closest_vertex.id} (거리: {closest_distance:.2f}km)")
    
    # 그래프 내에서 근접한 정점들 추가 연결
    vertices = list(graph.vertices.values())
    for i, v1 in enumerate(vertices):
        for j in range(i+1, min(i+10, len(vertices))):  # 근접 정점 10개만 확인 (성능 최적화)
            v2 = vertices[j]
            
            # 이미 연결되어 있는지 확인
            if (v1.id, v2.id) in graph.arcs or (v2.id, v1.id) in graph.arcs:
                continue
                
            # 거리 계산
            distance = calculate_distance(v1, v2)
            
            # 충분히 가까운 정점들 연결
            if distance <= distance_threshold:
                # 양방향 간선 추가
                arc1 = Arc(v1, v2, distance)
                arc2 = Arc(v2, v1, distance)
                
                graph.add_arc(arc1)
                graph.add_arc(arc2)
                
                edges_added += 2
    
    print(f"\n그래프 연결성 개선 완료: {edges_added}개 간선 추가됨")
    
    # 최종 연결 요소 확인
    final_components = find_connected_components(graph)
    print(f"최종 연결 컴포넌트 수: {len(final_components)}개")
    
    return edges_added


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
    # CCH 알고리즘을 사용하여 경로 찾기
    path = cch.find_path(graph, start_id, end_id)
    
    # CCH 알고리즘으로 경로를 찾았으면 반환
    if path:
        return path
        
    # CCH 알고리즘으로 경로를 찾지 못한 경우
    print(f"  CCH 알고리즘으로 경로를 찾지 못했습니다: {start_id} -> {end_id}")
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

def daejeon_bike_cch_example() -> Graph:
    """
    대전광역시 자전거 도로 API와 CCH 알고리즘을 결합한 예제
    
    Returns:
        생성된 그래프
    """
    # 1. 대전광역시 자전거 도로 데이터 가져오기
    bike_routes = fetch_bike_routes(num_of_rows=500)  # 더 많은 데이터 가져오기
    if not bike_routes:
        print("자전거 도로 데이터를 가져오지 못했습니다.")
        return None
    
    # 1-1. 자전거 보관소 데이터도 가져오기 (추가 기능)
    bike_storage = fetch_bike_storage(num_of_rows=50)
    if bike_storage:
        print(f"자전거 보관소 {len(bike_storage)}개 데이터를 받았습니다.")
    
    # 2. 그래프 생성
    print("\n그래프 생성 중...")
    graph = create_bike_route_graph(bike_routes)
    print(f"그래프 생성 완료: {len(graph.vertices)}개의 정점, {len(graph.arcs)}개의 간선")
    
    # 2-1. 그래프 연결성 개선
    enhance_graph_connectivity(graph, distance_threshold=0.1)
    
    # 정점 정보 출력
    print_vertex_info(graph)
    
    # 3. CCH 알고리즘 전처리
    print("\nCCH 알고리즘 전처리 중...")
    cch = preprocess_graph(graph)
    if not cch:
        print("CCH 알고리즘 전처리에 실패했습니다.")
        return graph
        
    # 4. 경로 찾기 예제
    print("\n경로 찾기 예제:")
    if len(graph.vertices) >= 2:
        # 첫 번째와 마지막 정점 사이의 경로 찾기
        start_id = list(graph.vertices.keys())[0]
        end_id = list(graph.vertices.keys())[-1]
        
        print(f"\n다익스트라 알고리즘으로 경로 찾기 (정점 {start_id}에서 정점 {end_id}까지)...")
        dijkstra_path = dijkstra(graph, start_id, end_id)
        print_path_info(dijkstra_path)
        
        print(f"\nCCH 알고리즘으로 경로 찾기 (정점 {start_id}에서 정점 {end_id}까지)...")
        cch_path = find_shortest_path(graph, cch, start_id, end_id)
        print_path_info(cch_path)
        
        # 경로 비교 및 분석
        if dijkstra_path and cch_path:
            dijkstra_cost = sum(arc.cost for arc in dijkstra_path)
            cch_cost = sum(arc.cost for arc in cch_path)
            print(f"\n경로 비교:\n다익스트라: {dijkstra_cost:.2f}km, CCH: {cch_cost:.2f}km")
            print(f"CCH 알고리즘 성능 향상: {(1 - cch_cost/dijkstra_cost)*100:.2f}%" if dijkstra_cost > cch_cost else "CCH와 다익스트라 결과 동일")
            
        # 여러 정점 쌍에 대한 추가 테스트
        print("\n추가 경로 찾기 테스트:")
        import random
        
        # 5개의 랜덤 정점 쌍에 대해 경로 찾기 테스트
        vertex_ids = list(graph.vertices.keys())
        num_tests = min(5, len(vertex_ids) // 2)
        
        for _ in range(num_tests):
            start_id = random.choice(vertex_ids)
            end_id = random.choice(vertex_ids)
            
            if start_id == end_id:
                continue
                
            print(f"\n정점 {start_id}에서 정점 {end_id}까지 경로 찾기...")
            cch_path = find_shortest_path(graph, cch, start_id, end_id)
            
            if cch_path:
                print(f"  경로 찾음: {len(cch_path)}개 간선, 총 거리: {sum(arc.cost for arc in cch_path):.2f}km")
            else:
                print("  경로를 찾을 수 없습니다.")
    else:
        print("경로 찾기를 위한 충분한 정점이 없습니다.")
    
    return graph


def main():
    """
    메인 함수
    """
    print("대전광역시 자전거 도로 경로 찾기 프로그램 시작")
    print("API 데이터와 CCH 알고리즘을 연동하여 최적 경로를 찾습니다.")
    print("-" * 50)
    
    # 대전 자전거 도로 CCH 예제 실행
    graph = daejeon_bike_cch_example()
    
    if graph:
        print("\n프로그램 실행 완료")
        print(f"생성된 그래프: {len(graph.vertices)}개 정점, {len(graph.arcs)}개 간선")
    else:
        print("\n프로그램 실행 중 오류가 발생했습니다.")
        
    print("-" * 50)

# 프로그램 시작점
if __name__ == "__main__":
    main()


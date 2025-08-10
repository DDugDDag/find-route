import heapq
from heapq import heappop, heappush
import requests
import json
from dataclasses import dataclass
from typing import List, Set, Dict, Optional, Tuple, Any
import warnings
import subprocess

@dataclass
class Vertex:
    id: int
    lat: float = 0.0
    lon: float = 0.0
    rank: int = 0
    
    def get_rank(self) -> int:
        return self.rank

@dataclass
class Arc:
    source: Vertex
    target: Vertex
    cost: int
    
    def get_cost(self) -> int:
        return self.cost
    
    def set_cost(self, cost: int) -> None:
        self.cost = cost

@dataclass
class Triangle:
    from_side_arc: Arc
    to_side_arc: Arc

class Graph:
    def __init__(self):
        self.vertices: Dict[int, Vertex] = {}
        self.arcs: Dict[Tuple[int, int], Arc] = {}
        self.lower_triangles: Dict[Tuple[int, int], List[Triangle]] = {}
        self.intermediate_triangles: List[Triangle] = []
        # 성능 최적화를 위한 인접 리스트
        self.outgoing_arcs: Dict[int, List[Arc]] = {}  # 정점 -> 나가는 간선들
        self.incoming_arcs: Dict[int, List[Arc]] = {}  # 정점 -> 들어오는 간선들
    
    def add_vertex(self, vertex: Vertex) -> None:
        self.vertices[vertex.id] = vertex
    
    def add_arc(self, arc: Arc) -> None:
        self.arcs[(arc.source.id, arc.target.id)] = arc
        
        # 인접 리스트 업데이트
        source_id = arc.source.id
        target_id = arc.target.id
        
        if source_id not in self.outgoing_arcs:
            self.outgoing_arcs[source_id] = []
        self.outgoing_arcs[source_id].append(arc)
        
        if target_id not in self.incoming_arcs:
            self.incoming_arcs[target_id] = []
        self.incoming_arcs[target_id].append(arc)
    
    def add_edge(self, v1: Vertex, v2: Vertex, cost: int = 0) -> None:
        arc = Arc(v1, v2, cost)
        self.add_arc(arc)
    
    def get_vertex_by_rank(self, rank: int) -> Optional[Vertex]:
        for vertex in self.vertices.values():
            if vertex.rank == rank:
                return vertex
        return None
    
    def get_upper_ranked_neighbors(self, vertex: Vertex) -> List[Vertex]:
        neighbors = []
        for arc_key, arc in self.arcs.items():
            if arc.source.id == vertex.id and arc.target.rank > vertex.rank:
                neighbors.append(arc.target)
        return neighbors
    
    def get_all_arcs_sorted_by_rank(self) -> List[Arc]:
        return sorted(self.arcs.values(), key=lambda arc: arc.source.rank)
    
    def get_lower_triangle(self, arc: Arc) -> List[Triangle]:
        key = (arc.source.id, arc.target.id)
        return self.lower_triangles.get(key, [])
    
    def add_lower_triangle(self, arc: Arc, triangle: Triangle) -> None:
        key = (arc.source.id, arc.target.id)
        if key not in self.lower_triangles:
            self.lower_triangles[key] = []
        self.lower_triangles[key].append(triangle)
    
    def get_intermediate_triangles(self) -> List[Triangle]:
        return self.intermediate_triangles
    
    def add_intermediate_triangle(self, triangle: Triangle) -> None:
        self.intermediate_triangles.append(triangle)

class CustomizableContractionHierarchies:
    def __init__(self, graph: Graph):
        self.graph = graph
        self.shortcuts = {}  # 지름길 정보 저장
    
    def metric_independent_preprocessing(self, n: int) -> None:
        """메트릭 독립적 전처리 단계 - 그래프 토폴로지만 고려하여 축약 순서와 지름길 결정"""
        # rank가 낮은 순으로 돌면서 contraction을 합니다.
        for rank in range(n):
            u = self.graph.get_vertex_by_rank(rank)
            if not u:
                continue
                
            upper_ranked_neighbors = self.graph.get_upper_ranked_neighbors(u)
            if not upper_ranked_neighbors:
                continue
                
            # 모든 상위 랭크 이웃 간에 지름길 추가 (CCH에서는 더 많은 지름길 생성)
            for v1 in upper_ranked_neighbors:
                for v2 in upper_ranked_neighbors:
                    if v1 != v2 and v1.rank < v2.rank:  # 중복 방지 및 방향성 유지
                        # 지름길 추가 (초기 비용은 무한대로 설정)
                        shortcut = Arc(v1, v2, float('inf'))
                        self.graph.add_arc(shortcut)
                        
                        # 이 지름길이 어떤 경로를 대체하는지 기록
                        key = (v1.id, v2.id)
                        if key not in self.shortcuts:
                            self.shortcuts[key] = []
                        
                        # u를 경유하는 경로 정보 저장
                        arc1 = self.graph.arcs.get((v1.id, u.id))
                        arc2 = self.graph.arcs.get((u.id, v2.id))
                        if arc1 and arc2:
                            triangle = Triangle(arc1, arc2)
                            self.graph.add_lower_triangle(shortcut, triangle)
    
    def customize(self, metric_function=None):
        """커스터마이징 단계 - 실제 비용을 적용하여 지름길 비용 계산"""
        # 기본 메트릭 함수는 단순히 두 비용의 합
        if metric_function is None:
            metric_function = lambda a, b: a + b
        
        # 모든 아크에 대해 비용 업데이트 (랭크 순서대로)
        for arc in self.graph.get_all_arcs_sorted_by_rank():
            lower_triangles = self.graph.get_lower_triangle(arc)
            if not lower_triangles:
                continue
                
            # 각 삼각형을 통한 경로 비용 계산
            costs = []
            for t in lower_triangles:
                cost1 = t.from_side_arc.cost
                cost2 = t.to_side_arc.cost
                if cost1 != float('inf') and cost2 != float('inf'):
                    costs.append(metric_function(cost1, cost2))
            
            # 최소 비용 경로가 있으면 업데이트
            if costs:
                min_cost = min(costs)
                if min_cost < arc.cost:
                    arc.set_cost(min_cost)
    
    def update_costs_with_priority_queue(self, to_be_updated_arcs: List[Arc], metric_function=None):
        """우선순위 큐를 사용한 비용 업데이트 (커스터마이징 단계의 최적화 버전)"""
        # 기본 메트릭 함수는 단순히 두 비용의 합
        if metric_function is None:
            metric_function = lambda a, b: a + b
            
        priority_queue = []
        for arc in to_be_updated_arcs:
            heapq.heappush(priority_queue, (arc.cost, arc))
        
        while priority_queue:
            _, arc = heapq.heappop(priority_queue)
            old_cost = arc.cost
            
            # 새 비용 계산
            lower_triangles = self.graph.get_lower_triangle(arc)
            costs = [arc.cost]  # 기존 비용도 포함
            
            for t in lower_triangles:
                cost1 = t.from_side_arc.cost
                cost2 = t.to_side_arc.cost
                if cost1 != float('inf') and cost2 != float('inf'):
                    costs.append(metric_function(cost1, cost2))
            
            new_cost = min(costs)
            
            if new_cost != old_cost:
                cost_reduced = new_cost < old_cost
                
                # 영향을 받는 다른 간선들 업데이트 큐에 추가
                affected_arcs = self._find_affected_arcs(arc, old_cost, cost_reduced)
                for affected_arc in affected_arcs:
                    heapq.heappush(priority_queue, (affected_arc.cost, affected_arc))
                
                arc.set_cost(new_cost)
    
    def _find_affected_arcs(self, changed_arc: Arc, old_cost: int, cost_reduced: bool) -> List[Arc]:
        """비용이 변경된 간선에 영향을 받는 다른 간선들을 찾음"""
        affected_arcs = []
        
        # 첫 번째 중간 삼각형 처리 (changed_arc가 삼각형의 한 변인 경우)
        for itm_triangle in self.graph.get_intermediate_triangles():
            from_side = itm_triangle.from_side_arc
            to_side = itm_triangle.to_side_arc
            
            # changed_arc가 삼각형의 한 변인지 확인
            if from_side == changed_arc:
                # 비용이 감소했거나, 이전에 최적 경로였던 경우
                if cost_reduced or to_side.cost == from_side.cost + old_cost:
                    affected_arcs.append(to_side)
            elif to_side == changed_arc:
                # 비용이 감소했거나, 이전에 최적 경로였던 경우
                if cost_reduced or from_side.cost == to_side.cost + old_cost:
                    affected_arcs.append(from_side)
        
        return affected_arcs
    
    def unpack_path(self, arc: Arc, result_path: List[Arc], metric_function=None) -> None:
        """압축된 경로를 원래 경로로 풀어냄"""
        # 기본 메트릭 함수는 단순히 두 비용의 합
        if metric_function is None:
            metric_function = lambda a, b: a + b
            
        # 지름길인지 확인
        lower_triangles = self.graph.get_lower_triangle(arc)
        if not lower_triangles:
            # 지름길이 아니면 원래 간선 추가
            result_path.append(arc)
            return
        
        # 최소 비용 경로 찾기
        min_cost = float('inf')
        best_triangle = None
        
        for triangle in lower_triangles:
            from_arc = triangle.from_side_arc
            to_arc = triangle.to_side_arc
            cost = metric_function(from_arc.cost, to_arc.cost)
            
            # 비용 비교 시 오차 허용 범위를 넓게 설정 (1e-3)
            if cost < min_cost and (abs(cost - arc.cost) < 1e-3 or cost < arc.cost):
                min_cost = cost
                best_triangle = triangle
        
        # 최적 경로가 없으면 원래 간선 사용
        if not best_triangle:
            result_path.append(arc)
            return
            
        # 최적 경로가 있으면 재귀적으로 경로 풀어내기
        self.unpack_path(best_triangle.from_side_arc, result_path, metric_function)
        self.unpack_path(best_triangle.to_side_arc, result_path, metric_function)
    
    def find_path(self, graph: Graph, source_id: int, target_id: int, metric_function=None) -> List[Arc]:
        """
        두 정점 간의 최단 경로를 찾습니다.
        최적화된 양방향 다익스트라 검색과 CCH 축약 계층 구조를 활용합니다.
        
        Args:
            graph: 그래프 객체
            source_id: 시작 정점 ID
            target_id: 도착 정점 ID
            
        Returns:
            최단 경로(Arc 리스트). 경로가 없으면 빈 리스트를 반환합니다.
        """
        # 시작 정점과 도착 정점이 같으면 빈 경로 반환
        if source_id == target_id:
            return []
            
        # 시작 정점과 도착 정점이 그래프에 존재하는지 확인
        source = graph.vertices.get(source_id)
        target = graph.vertices.get(target_id)
        if not source or not target:
            return []
            
        # 직접 간선이 있는지 확인
        direct_arc = graph.arcs.get((source_id, target_id))
        if direct_arc:
            result_path = []
            self.unpack_path(direct_arc, result_path, metric_function)
            return result_path
        
        # 양방향 다익스트라 검색 초기화
        forward_distances = {source_id: 0.0}
        backward_distances = {target_id: 0.0}
        
        forward_queue = [(0.0, source_id)]  # (distance, vertex_id)
        backward_queue = [(0.0, target_id)]
        
        forward_settled = set()
        backward_settled = set()
        
        forward_parents = {}
        backward_parents = {}
        
        meeting_point = None
        best_distance = float('inf')
        
        max_iterations = 500  # 최적화: 반복 횟수 제한 감소
        iteration = 0
        
        # 최적화된 양방향 탐색
        while forward_queue and backward_queue and best_distance == float('inf') and iteration < max_iterations:
            iteration += 1
            
            # 순방향 탐색 단계
            if forward_queue:
                _, current_id = heappop(forward_queue)
                
                if current_id in forward_settled:
                    continue
                    
                forward_settled.add(current_id)
                current_dist = forward_distances[current_id]
                
                # 만약 현재 정점이 backward_settled에 있다면 만남 정점 후보
                if current_id in backward_settled:
                    total_dist = current_dist + backward_distances[current_id]
                    if total_dist < best_distance:
                        best_distance = total_dist
                        meeting_point = current_id
                        print(f"[DEBUG] 만남 정점 발견: {meeting_point}, 거리: {best_distance}")
                
                # 현재 정점의 모든 이웃 정점 탐색
                current = graph.vertices.get(current_id)
                if not current:
                    continue
                
                # 최적화: 인접 리스트를 사용해서 O(1) 접근
                outgoing_arcs = graph.outgoing_arcs.get(current_id, [])
                
                for arc in outgoing_arcs:
                    neighbor_id = arc.target.id
                    neighbor = graph.vertices.get(neighbor_id)
                    
                    # CCH 랭크 조건 완화: 순방향 검색에서도 모든 이웃 정점을 고려
                    if neighbor:
                        new_dist = current_dist + arc.cost
                        if neighbor_id not in forward_distances or new_dist < forward_distances[neighbor_id]:
                            forward_distances[neighbor_id] = new_dist
                            heappush(forward_queue, (new_dist, neighbor_id))
                            forward_parents[neighbor_id] = (current_id, arc)
            
            # 역방향 탐색 단계
            if backward_queue:
                _, current_id = heappop(backward_queue)
                
                if current_id in backward_settled:
                    continue
                    
                backward_settled.add(current_id)
                current_dist = backward_distances[current_id]
                
                # 만남 지점 확인
                if current_id in forward_settled:
                    total_dist = forward_distances[current_id] + current_dist
                    if total_dist < best_distance:
                        best_distance = total_dist
                        meeting_point = current_id
                
                # 최적화: 인접 리스트를 사용해서 O(1) 접근
                incoming_arcs = graph.incoming_arcs.get(current_id, [])
                
                for arc in incoming_arcs:
                    neighbor_id = arc.source.id
                    neighbor = graph.vertices.get(neighbor_id)
                    
                    # CCH 랭크 조건 완화: 역방향 검색에서는 모든 이웃 정점을 고려
                    if neighbor:
                        new_dist = current_dist + arc.cost
                        if neighbor_id not in backward_distances or new_dist < backward_distances[neighbor_id]:
                            backward_distances[neighbor_id] = new_dist
                            heappush(backward_queue, (new_dist, neighbor_id))
                            backward_parents[neighbor_id] = (current_id, arc)
                

        
        # 경로가 없는 경우
        if best_distance == float('inf') or not meeting_point:
            print(f"[DEBUG] CCH find_path: 경로를 찾을 수 없음 (반복 {iteration})")
            if iteration >= max_iterations:
                print(f"[DEBUG] 최대 반복 횟수({max_iterations}) 도달")
            return []
        
        print(f"[DEBUG] 최종 만남 정점: {meeting_point}, 총 거리: {best_distance}")
        
        # 경로 재구성
        path = []
        
        # 순방향 경로 재구성
        print(f"[DEBUG] 순방향 경로 재구성 시작")
        current = meeting_point
        forward_arcs = []
        while current in forward_parents:
            parent_id, arc = forward_parents[current]
            print(f"[DEBUG] 순방향 경로: {parent_id} -> {current}")
            forward_arcs.append(arc)
            current = parent_id
            
        # 순방향 경로 역순으로 경로에 추가
        for arc in reversed(forward_arcs):
            sub_path = []
            self.unpack_path(arc, sub_path, metric_function)
            path.extend(sub_path)
        
        # 역방향 경로 재구성
        print(f"[DEBUG] 역방향 경로 재구성 시작")
        current = meeting_point
        backward_arcs = []
        while current in backward_parents:
            parent_id, arc = backward_parents[current]
            print(f"[DEBUG] 역방향 경로: {current} -> {parent_id}")
            backward_arcs.append(arc)
            current = parent_id
        
        # 역방향 경로 추가
        for arc in backward_arcs:
            sub_path = []
            self.unpack_path(arc, sub_path, metric_function)
            path.extend(sub_path)
        
        print(f"[DEBUG] 최종 경로 길이: {len(path)}개 간선")
        return path
        
# 메인 함수 실행 코드
if __name__ == "__main__":
    pass  # 현재는 사용하지 않음
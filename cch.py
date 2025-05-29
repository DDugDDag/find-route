import heapq
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
    
    def add_vertex(self, vertex: Vertex) -> None:
        self.vertices[vertex.id] = vertex
    
    def add_arc(self, arc: Arc) -> None:
        self.arcs[(arc.source.id, arc.target.id)] = arc
    
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
        
# 메인 함수 실행 코드
if __name__ == "__main__":
    pass  # 현재는 사용하지 않음
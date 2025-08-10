#!/usr/bin/env python3
"""
하이브리드 경로 플래너 메인 실행 파일
실제 .env 파일의 API 키를 사용하여 테스트
"""

import os
from dotenv import load_dotenv
from hybrid_planner import HybridRoutePlanner, RouteRequest, RoutePreference

# 환경 변수 로드
load_dotenv()

def print_route_result(result, request):
    """경로 결과 출력"""
    print(f"\n{'='*60}")
    print(f"🎯 경로 계획 결과")
    print(f"{'='*60}")
    
    print(f"📍 출발지: ({request.start_lat:.4f}, {request.start_lon:.4f})")
    print(f"📍 도착지: ({request.end_lat:.4f}, {request.end_lon:.4f})")
    print(f"🤖 사용된 알고리즘: {result.algorithm_used}")
    
    if result.path:
        print(f"📏 총 거리: {result.total_distance:.2f}km")
        print(f"⏱️  예상 시간: {result.estimated_time:.0f}분")
        
        if result.scenic_score > 0:
            print(f"🎨 경치 점수: {result.scenic_score:.1f}/10")
        
        if result.metadata:
            if 'scenic_places' in result.metadata:
                print(f"🏞️  경치 좋은 장소: {result.metadata['scenic_places']}개")
            if 'vertices_count' in result.metadata:
                print(f"🔗 경유 지점: {result.metadata['vertices_count']}개")
        
        # 경로 상세 정보 (처음 5개만 표시)
        print(f"\n🗺️  경로 상세 (처음 5개 구간):")
        for i, segment in enumerate(result.path[:5]):
            if hasattr(segment, 'cost'):
                # CCH Arc
                print(f"   {i+1}. ({segment.source.lat:.4f}, {segment.source.lon:.4f}) → "
                      f"({segment.target.lat:.4f}, {segment.target.lon:.4f}) "
                      f"[{segment.cost:.2f}km]")
            elif hasattr(segment, 'distance'):
                # Scenic RouteEdge
                print(f"   {i+1}. ({segment.source.lat:.4f}, {segment.source.lon:.4f}) → "
                      f"({segment.target.lat:.4f}, {segment.target.lon:.4f}) "
                      f"[{segment.distance:.2f}km, 경치: {segment.scenic_score:.1f}]")
            else:
                # 기타 형식
                print(f"   {i+1}. 경로 구간 {i+1}")
        
        if len(result.path) > 5:
            print(f"   ... 총 {len(result.path)}개 구간 중 5개만 표시")
    else:
        print("❌ 경로를 찾을 수 없습니다.")
        if result.metadata and 'error' in result.metadata:
            print(f"   오류: {result.metadata['error']}")

def test_hybrid_planner():
    """하이브리드 플래너 테스트"""
    print("🚀 하이브리드 경로 플래너 테스트 시작")
    print("=" * 60)
    
    # API 키 확인
    kakao_key = os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_RESTAPI_KEY")
    daejeon_key = os.getenv("API_KEY")
    
    print("🔑 API 키 상태:")
    if kakao_key:
        print(f"   ✅ 카카오 API: 설정됨 ({kakao_key[:10]}...)")
    else:
        print("   ❌ 카카오 API: 설정되지 않음")
    
    if daejeon_key:
        print(f"   ✅ 대전시 API: 설정됨 ({daejeon_key[:10]}...)")
    else:
        print("   ❌ 대전시 API: 설정되지 않음")
    
    # 하이브리드 플래너 초기화
    planner = HybridRoutePlanner()
    
    # 테스트 케이스들
    test_cases = [
        {
            "name": "🚴‍♂️ 단거리 효율성 우선 (대전역 → 대전시청)",
            "request": RouteRequest(
                start_lat=36.3504, start_lon=127.3845,  # 대전역
                end_lat=36.3398, end_lon=127.3940,      # 대전시청
                preferences=RoutePreference(
                    scenic_weight=0.3,
                    distance_weight=0.7,
                    elevation_weight=0.1,
                    max_detour_ratio=1.2
                )
            )
        },
        {
            "name": "🌸 단거리 경치 우선 (대전역 → 엑스포공원)",
            "request": RouteRequest(
                start_lat=36.3504, start_lon=127.3845,  # 대전역
                end_lat=36.3726, end_lon=127.3896,      # 엑스포공원
                preferences=RoutePreference(
                    scenic_weight=0.8,
                    distance_weight=0.2,
                    elevation_weight=0.1,
                    max_detour_ratio=1.5
                )
            )
        },
        {
            "name": "🛣️  장거리 경로 (대전역 → 유성온천)",
            "request": RouteRequest(
                start_lat=36.3504, start_lon=127.3845,  # 대전역
                end_lat=36.3219, end_lon=127.4086,      # 유성온천
                preferences=RoutePreference(
                    scenic_weight=0.5,
                    distance_weight=0.5,
                    elevation_weight=0.1,
                    max_detour_ratio=1.3
                ),
                context={"real_time_traffic": False}
            )
        },
        {
            "name": "🚦 실시간 교통 고려 (엑스포공원 → 서대전역)",
            "request": RouteRequest(
                start_lat=36.3726, start_lon=127.3896,  # 엑스포공원
                end_lat=36.3665, end_lon=127.3448,      # 서대전역
                preferences=RoutePreference(
                    scenic_weight=0.4,
                    distance_weight=0.6,
                    elevation_weight=0.1,
                    max_detour_ratio=1.4
                ),
                context={"real_time_traffic": True}
            )
        }
    ]
    
    # 각 테스트 케이스 실행
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 테스트 케이스 {i}: {test_case['name']}")
        print("-" * 60)
        
        try:
            result = planner.plan_route(test_case['request'])
            print_route_result(result, test_case['request'])
            
        except Exception as e:
            print(f"❌ 테스트 실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*60)
    
    print("\n🎉 모든 테스트 완료!")

def interactive_mode():
    """대화형 모드"""
    print("\n🎮 대화형 경로 계획 모드")
    print("=" * 60)
    
    planner = HybridRoutePlanner()
    
    while True:
        try:
            print("\n📍 경로 정보를 입력해주세요 (종료: 'q')")
            
            start_input = input("출발지 (위도,경도): ").strip()
            if start_input.lower() == 'q':
                break
            
            end_input = input("도착지 (위도,경도): ").strip()
            if end_input.lower() == 'q':
                break
            
            # 좌표 파싱
            start_lat, start_lon = map(float, start_input.split(','))
            end_lat, end_lon = map(float, end_input.split(','))
            
            # 선호도 입력
            print("\n🎯 경로 선호도 설정:")
            scenic_weight = float(input("경치 가중치 (0.0-1.0, 기본 0.5): ") or "0.5")
            distance_weight = float(input("거리 가중치 (0.0-1.0, 기본 0.5): ") or "0.5")
            
            # 요청 생성
            request = RouteRequest(
                start_lat=start_lat, start_lon=start_lon,
                end_lat=end_lat, end_lon=end_lon,
                preferences=RoutePreference(
                    scenic_weight=scenic_weight,
                    distance_weight=distance_weight,
                    elevation_weight=0.1,
                    max_detour_ratio=1.5
                )
            )
            
            # 경로 계획 실행
            result = planner.plan_route(request)
            print_route_result(result, request)
            
        except ValueError:
            print("❌ 잘못된 입력 형식입니다. 예: 36.3504,127.3845")
        except KeyboardInterrupt:
            print("\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

def main():
    """메인 함수"""
    print("🌟 하이브리드 경로 플래너")
    print("=" * 60)
    print("CCH 알고리즘과 Scenic Route 알고리즘을 결합한 지능형 경로 계획 시스템")
    print("실제 대전시 자전거 도로 데이터와 카카오 API를 활용합니다.")
    print("=" * 60)
    
    while True:
        print("\n📋 메뉴를 선택해주세요:")
        print("1. 자동 테스트 실행")
        print("2. 대화형 경로 계획")
        print("3. 종료")
        
        choice = input("\n선택 (1-3): ").strip()
        
        if choice == '1':
            test_hybrid_planner()
        elif choice == '2':
            interactive_mode()
        elif choice == '3':
            print("👋 프로그램을 종료합니다.")
            break
        else:
            print("❌ 잘못된 선택입니다. 1-3 중에서 선택해주세요.")

if __name__ == "__main__":
    main()

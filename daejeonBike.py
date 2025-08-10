import requests
import json
import subprocess
import warnings
import certifi
import ssl
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from dotenv import load_dotenv
import os
import urllib3

# SSL 경고 비활성화 (개발 환경에서만 사용)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 사용자 정의 SSL Context를 사용하는 어댑터 클래스
class CustomSSLAdapter(HTTPAdapter):
    def __init__(self, **kwargs):
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.ssl_context.options |= ssl.OP_NO_SSLv2
        self.ssl_context.options |= ssl.OP_NO_SSLv3
        self.ssl_context.set_ciphers('HIGH:!DH:!aNULL')
        super(CustomSSLAdapter, self).__init__(**kwargs)
    
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            ssl_context=self.ssl_context
        )

# 환경 변수 로드
load_dotenv()
api_key=os.getenv("API_KEY")
enapi_key=os.getenv("ENAPI_KEY")

# HTTP 다운그레이드 헬퍼 함수 (HTTPS가 실패할 경우 HTTP 시도)
def try_http_if_https_fails(url, headers, timeout=30):
    try:
        # 먼저 커스텀 SSL 컨텍스트로 시도
        session = requests.Session()
        adapter = CustomSSLAdapter()
        session.mount('https://', adapter)
        response = session.get(url, headers=headers, timeout=timeout)
        return response
    except Exception as e:
        print(f"HTTPS 요청 실패, HTTP로 시도: {e}")
        # HTTPS가 실패하면 HTTP로 시도
        http_url = url.replace('https://', 'http://')
        return requests.get(http_url, headers=headers, timeout=timeout)

class DaejeonBikeRouteAPI:
    def __init__(self):
        
        self.api_key = api_key
        self.encoded_api_key = enapi_key
        self.base_url = "https://apis.data.go.kr/6300000/"
        self.bike_path_list_endpoint = "GetBycpListService/getBycpList"

    def get_bike_routes(self, page_no=1, num_of_rows=10, retry_count=3):
        """
        대전광역시 자전거 도로 데이터를 가져옵니다.
        
        Args:
            page_no: 페이지 번호
            num_of_rows: 페이지당 가져올 데이터 개수
            retry_count: 재시도 횟수
            
        Returns:
            자전거 도로 데이터 리스트 또는 None (실패 시)
        """
        try:
            print(f"\n대전광역시 자전거 도로 정보 요청 중...")

            url = f"{self.base_url}{self.bike_path_list_endpoint}"
            request_url = f"{url}?serviceKey={self.encoded_api_key}&pageNo={page_no}&numOfRows={num_of_rows}&type=json"
            print(f"API 요청 URL: {request_url}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json'
                    }
                    
                    # 커스텀 SSL 컨텍스트를 통한 요청
                    response = try_http_if_https_fails(request_url, headers)
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            body = result.get("body", result.get("response", {}).get("body", {}))
                            items = body.get("items", {}).get("item", [])
                            if isinstance(items, dict):
                                items = [items]
                            return items  # 여기서 items 리스트만 반환
                        except json.JSONDecodeError:
                            print("JSON 파싱 오류")
                    else:
                        print(f"API 요청 오류: 상태 코드 {response.status_code}")
                except Exception as e:
                    print(f"requests 요청 오류: {e}")

            return None

        except Exception as e:
            print(f"API 요청 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None


class DaejeonBikeInfoAPI:
    def __init__(self):
        self.api_key = api_key
        self.encoded_api_key = enapi_key
        self.base_url = "https://apis.data.go.kr/6300000/"
        self.bike_path_list_endpoint = "GetBystListService/getBystList"

    def get_bike_info(self, page_no=1, num_of_rows=10, retry_count=3):
        """
        대전광역시 자전거 보관소 데이터를 가져옵니다.
        
        Args:
            page_no: 페이지 번호
            num_of_rows: 페이지당 가져올 데이터 개수
            retry_count: 재시도 횟수
            
        Returns:
            자전거 보관소 데이터 리스트 또는 None (실패 시)
        """
        try:
            print(f"\n대전광역시 자전거보관소정보 요청 중...")

            url = f"{self.base_url}{self.bike_path_list_endpoint}"
            request_url = f"{url}?serviceKey={self.encoded_api_key}&pageNo={page_no}&numOfRows={num_of_rows}&type=json"
            print(f"API 요청 URL: {request_url}")

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0',
                        'Accept': 'application/json'
                    }
                    
                    # 커스텀 SSL 컨텍스트를 통한 요청
                    response = try_http_if_https_fails(request_url, headers)
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            body = result.get("body", result.get("response", {}).get("body", {}))
                            items = body.get("items", {}).get("item", [])
                            if isinstance(items, dict):
                                items = [items]
                            return items  # 여기서 items 리스트만 반환
                        except json.JSONDecodeError:
                            print("JSON 파싱 오류")
                    else:
                        print(f"API 요청 오류: 상태 코드 {response.status_code}")
                except Exception as e:
                    print(f"requests 요청 오류: {e}")

            return None

        except Exception as e:
            print(f"API 요청 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return None


# API 데이터 가져오기 함수
def get_bike_route_data(page_no=1, num_of_rows=10, retry_count=3):
    """대전광역시 자전거 도로 데이터를 가져옵니다."""
    api = DaejeonBikeRouteAPI()
    return api.get_bike_routes(page_no=page_no, num_of_rows=num_of_rows, retry_count=retry_count)

def get_bike_storage_data(page_no=1, num_of_rows=10, retry_count=3):
    """대전광역시 자전거 보관소 데이터를 가져옵니다."""
    api = DaejeonBikeInfoAPI()
    return api.get_bike_info(page_no=page_no, num_of_rows=num_of_rows, retry_count=retry_count)

# 테스트 실행
if __name__ == "__main__":
    result = get_bike_route_data(page_no=1, num_of_rows=10)
    result2 = get_bike_storage_data(page_no=1, num_of_rows=10)
    
    if result:
        print("자전거 도로 정보:")
        for item in result:
            print(item)
    else:
        print("자전거 도로 정보를 가져오지 못했습니다.")
        
    if result2:
        print("자전거 보관소 정보:")
        for item in result2:
            print(item)

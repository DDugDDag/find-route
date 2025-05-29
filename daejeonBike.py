import requests
import json
import subprocess
import warnings
from dotenv import load_dotenv
import os
load_dotenv()
api_key=os.getenv("API_KEY")
enapi_key=os.getenv("ENAPI_KEY")


class DaejeonBikeRouteAPI:
    def __init__(self):
        
        self.api_key = api_key
        self.encoded_api_key = enapi_key
        self.base_url = "https://apis.data.go.kr/6300000/"
        self.bike_path_list_endpoint = "GetBycpListService/getBycpList"

    def get_bike_routes(self, page_no=1, num_of_rows=10):
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
                    response = requests.get(request_url, headers=headers, verify=False)
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

    def get_bike_info(self, page_no=1, num_of_rows=10):
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
                    response = requests.get(request_url, headers=headers, verify=False)
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


# 테스트 실행
if __name__ == "__main__":
    rapi = DaejeonBikeRouteAPI()
    result = rapi.get_bike_routes(page_no=1, num_of_rows=3)
    iapi=DaejeonBikeInfoAPI()
    result2 = iapi.get_bike_info(page_no=1, num_of_rows=3)
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
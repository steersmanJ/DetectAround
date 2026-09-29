import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import streamlit as st

def get_vworld_key():
    try:
        return st.secrets["VWORLD_API_KEY"]
    except:
        return "15B8468B-B7A6-4B22-A26C-726136C6AFB0"

VWORLD_API_KEY = get_vworld_key()

def get_cadastral_info(lon, lat):
    """
    (기존 기능 유지) 단일 좌표 기반 검색
    """
    url = "https://api.vworld.kr/req/data"
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LP_PA_CBND_BUBUN",
        "key": VWORLD_API_KEY,
        "geomFilter": f"POINT({lon} {lat})",
        "geometry": "false",
        "domain": "localhost"
    }
    
    try:
        response = requests.get(url, params=params, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data['response']['status'] == 'OK':
                features = data['response']['result']['featureCollection']['features']
                if features:
                    properties = features[0]['properties']
                    return {
                        "pnu": properties.get('pnu', ''),
                        "jibun": properties.get('jibun', ''),
                        "is_agri": properties.get('jibun', '').endswith(('전', '답', '과'))
                    }
    except Exception as e:
        print(f"API Error: {e}")
    return None

def get_cadastral_box(min_lon, min_lat, max_lon, max_lat):
    """
    (V2 추가 기능) 화면 바운딩 박스 내의 모든 지적도 정보를 가져오고, '농지'인 곳만 필터링하여 반환합니다.
    주의: geometry=true 로 설정하여 해당 지적도의 폴리곤 형태(경계선 좌표)도 함께 가져옵니다.
    """
    url = "https://api.vworld.kr/req/data"
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LP_PA_CBND_BUBUN",
        "key": VWORLD_API_KEY,
        "geomFilter": f"BOX({min_lon}, {min_lat}, {max_lon}, {max_lat})",
        "geometry": "true", # GEE에 넘길 폴리곤 모양을 그리기 위해 필수
        "size": 1000, # 한 번에 가져올 최대 개수 넉넉히 설정
        "domain": "localhost"
    }
    
    agri_features = []
    
    try:
        response = requests.get(url, params=params, verify=False)
        if response.status_code == 200:
            data = response.json()
            if data['response']['status'] == 'OK':
                features = data['response']['result']['featureCollection']['features']
                for feat in features:
                    properties = feat.get('properties', {})
                    jibun = properties.get('jibun', '')
                    # 농지(전, 답, 과)만 필터링
                    if jibun.endswith(('전', '답', '과')):
                        agri_features.append(feat)
    except Exception as e:
        print(f"API Error: {e}")
        
    return agri_features

def get_detailed_address(lon, lat):
    """
    Vworld 좌표->주소 변환(역지오코딩)을 통해 행정동, 법정동, 도로명 주소를 가져옵니다.
    """
    url = "https://api.vworld.kr/req/address"
    params = {
        "service": "address",
        "request": "getAddress",
        "version": "2.0",
        "crs": "epsg:4326",
        "point": f"{lon},{lat}",
        "format": "json",
        "type": "BOTH", # 도로명, 지번 둘 다
        "zipcode": "true",
        "simple": "false",
        "key": VWORLD_API_KEY
    }
    
    address_info = {
        "parcel": "", # 지번 주소
        "road": ""    # 도로명 주소
    }
    
    try:
        res = requests.get(url, params=params, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data.get('response', {}).get('status') == 'OK':
                results = data['response']['result']
                for item in results:
                    if item.get('type') == 'parcel':
                        address_info['parcel'] = item.get('text', '')
                    elif item.get('type') == 'road':
                        address_info['road'] = item.get('text', '')
    except Exception as e:
        print(f"Address API Error: {e}")
        
    return address_info

def get_static_map_image(lon, lat, map_type="PHOTO_HYBRID", zoom=17, width=500, height=400):
    """
    Vworld Static Map API를 사용하여 지도 이미지를 바이너리로 반환합니다.
    map_type: 'GRAPHIC' (일반), 'PHOTO' (위성), 'PHOTO_HYBRID' (위성+지적도)
    """
    # 중심 좌표에 마커를 하나 표시합니다
    # 만약 map_type 인자로 HYBRID가 들어오면 PHOTO_HYBRID로 강제 변환
    if map_type == "HYBRID":
        map_type = "PHOTO_HYBRID"
        
    url = f"https://api.vworld.kr/req/image?service=image&request=getmap&key={VWORLD_API_KEY}&center={lon},{lat}&zoom={zoom}&size={width},{height}&basemap={map_type}&marker={lon},{lat}"
    
    try:
        res = requests.get(url, verify=False)
        if res.status_code == 200:
            # 에러 JSON이 아닌 이미지 바이너리가 왔는지 검사 (Vworld 에러는 JSON을 반환함)
            if b'{"response"' in res.content[:20]:
                print(f"API returned error JSON: {res.content.decode('utf-8')}")
                return None
            return res.content
    except Exception as e:
        print(f"Static Map API Error: {e}")
    return None

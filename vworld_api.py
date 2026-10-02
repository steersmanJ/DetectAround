import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import streamlit as st

def get_vworld_key():
    try:
        return st.secrets["VWORLD_API_KEY"]
    except KeyError:
        raise Exception("VWORLD_API_KEY is not set in .streamlit/secrets.toml")

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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'http://localhost'}
        response = requests.get(url, params=params, headers=headers, verify=False)
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'http://localhost'}
        response = requests.get(url, params=params, headers=headers, verify=False)
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
            else:
                st.error(f"Vworld API Data Error: {data}")
        else:
            st.error(f"Vworld HTTP Error: {response.status_code}")
    except Exception as e:
        st.error(f"Vworld Request Exception: {e}")
        
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'http://localhost'}
        res = requests.get(url, params=params, headers=headers, verify=False)
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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'http://localhost'}
        res = requests.get(url, headers=headers, verify=False)
        if res.status_code == 200:
            # 에러 JSON이 아닌 이미지 바이너리가 왔는지 검사 (Vworld 에러는 JSON을 반환함)
            if b'{"response"' in res.content[:20]:
                print(f"API returned error JSON: {res.content.decode('utf-8')}")
                return None
            return res.content
    except Exception as e:
        print(f"Static Map API Error: {e}")
    return None

def get_land_use_plan(lon, lat):
    """
    Vworld 용도지역 API를 통해 해당 좌표의 토지이용계획 정보를 조회합니다.
    농업진흥구역/보호구역/일반농지 구분 및 용도지역(농림지역, 관리지역 등)을 반환합니다.
    """
    url = "https://api.vworld.kr/req/data"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Referer': 'http://localhost'}
    
    result = {
        "use_zone": "",           # 용도지역 (예: 농림지역, 관리지역, 자연녹지지역)
        "agri_promotion": "",     # 농업진흥구역/보호구역/해당없음
        "is_promotion_area": False,  # 농업진흥구역 여부
        "penalty_clause": "",     # 적용 벌칙 조항
        "raw_zones": []           # 원시 용도지역 목록
    }
    
    # 1단계: 용도지역 조회 (LT_C_UQ111)
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LT_C_UQ111",
        "key": VWORLD_API_KEY,
        "geomFilter": f"POINT({lon} {lat})",
        "geometry": "false",
        "domain": "localhost"
    }
    
    try:
        res = requests.get(url, params=params, headers=headers, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data['response']['status'] == 'OK':
                features = data['response']['result']['featureCollection']['features']
                zones = []
                for f in features:
                    uname = f['properties'].get('uname', '')
                    if uname:
                        zones.append(uname)
                result["raw_zones"] = zones
                result["use_zone"] = ", ".join(zones) if zones else "미확인"
                
                # 농업진흥지역 판별: 용도지역명에 '농림' 포함 여부로 1차 판정
                for zone in zones:
                    if '농림' in zone:
                        result["agri_promotion"] = "농업진흥지역(추정)"
                        result["is_promotion_area"] = True
                    elif '보전관리' in zone or '생산관리' in zone:
                        result["agri_promotion"] = "농업보호구역(추정)"
                        result["is_promotion_area"] = True
    except Exception as e:
        print(f"Land Use Plan API Error: {e}")
    
    # 2단계: 용도지구 추가 조회 (LT_C_UQ112)
    try:
        params2 = params.copy()
        params2["data"] = "LT_C_UQ112"
        res2 = requests.get(url, params=params2, headers=headers, verify=False)
        if res2.status_code == 200:
            data2 = res2.json()
            if data2['response']['status'] == 'OK':
                features2 = data2['response']['result']['featureCollection']['features']
                for f in features2:
                    uname = f['properties'].get('uname', '')
                    if uname and uname not in result["raw_zones"]:
                        result["raw_zones"].append(uname)
    except:
        pass
    
    # 농업진흥구역이 미확정이면 일반농지로 분류
    if not result["agri_promotion"]:
        result["agri_promotion"] = "농업진흥지역 밖 (일반농지)"
    
    # 벌칙 조항 자동 산정
    if result["is_promotion_area"]:
        result["penalty_clause"] = "농지법 제58조 제1호 (5년 이하 징역 또는 토지가액 이하 벌금)"
    else:
        result["penalty_clause"] = "농지법 제58조 제2호 (3년 이하 징역 또는 토지가액 50% 이하 벌금)"
    
    return result

def parse_jurisdiction(address_str):
    """
    주소 문자열에서 관할 지자체(시/군/구)를 파싱합니다.
    예: '경기도 이천시 부발읍 아미리 123-4' -> {'sido': '경기도', 'sigungu': '이천시', 'full': '경기도 이천시'}
    """
    result = {"sido": "", "sigungu": "", "full": ""}
    
    if not address_str:
        return result
    
    parts = address_str.strip().split()
    if len(parts) >= 1:
        result["sido"] = parts[0]
    if len(parts) >= 2:
        result["sigungu"] = parts[1]
        result["full"] = f"{parts[0]} {parts[1]}"
    
    return result

def estimate_penalty(jiga_per_sqm, total_area_sqm, violation_area_sqm, is_promotion_area):
    """
    농지법 위반 시 예상 벌금 범위를 산출합니다.
    - 농업진흥구역: 토지가액(개별공시지가 × 면적) 100% 이하 벌금
    - 일반농지: 토지가액 50% 이하 벌금
    """
    if not jiga_per_sqm or not violation_area_sqm:
        return None
    
    land_value = jiga_per_sqm * violation_area_sqm
    
    if is_promotion_area:
        max_fine = land_value
        clause = "제58조 제1호"
    else:
        max_fine = land_value * 0.5
        clause = "제58조 제2호"
    
    return {
        "land_value": land_value,
        "max_fine": max_fine,
        "clause": clause,
        "description": f"토지가액 {land_value:,.0f}원 기준, 최대 벌금 {max_fine:,.0f}원 ({clause})"
    }

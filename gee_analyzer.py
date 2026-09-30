import ee

import streamlit as st
from google.oauth2 import service_account

def init_gee(project_id="gen-lang-client-0917558039"):
    # 1. 클라우드 배포 환경 (st.secrets에 GCP 키가 있는 경우)
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            scoped_creds = creds.with_scopes(['https://www.googleapis.com/auth/earthengine'])
            ee.Initialize(credentials=scoped_creds, project=project_id)
            return True
    except Exception as e:
        pass # 설정이 없으면 아래 로컬 인증으로 넘어감
        
    # 2. 로컬 테스트 환경 (로컬 인증 정보 사용)
    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        return True
    except Exception as e:
        print("GEE Init Error:", e)
        return False

def check_current_vegetation(agri_features, year=2023, ndvi_threshold=0.25, project_id="gen-lang-client-0917558039"):
    """
    (V2 아키텍처)
    Vworld에서 찾은 '농지' 폴리곤 리스트를 받아,
    최근 여름철(6~9월) 평균 식생지수(NDVI)가 임계값 미만인(즉, 풀이 없고 시멘트/흙바닥인) 땅만 골라냅니다.
    """
    if not agri_features:
        return []
        
    if not init_gee(project_id):
        return []

    # 파이썬 딕셔너리(GeoJSON 형태)를 GEE Feature 객체로 변환
    ee_features = []
    for feat in agri_features:
        geom = ee.Geometry(feat['geometry'])
        ee_features.append(ee.Feature(geom, feat['properties']))
        
    fc = ee.FeatureCollection(ee_features)
    
    # Sentinel-2 위성 이미지 (해상도 10m)
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    
    # 폴리곤 전체 영역을 커버하는 최근 여름철 구름 적은 이미지 필터링
    summer_images = s2.filterBounds(fc.geometry()) \
                      .filterDate(f'{year}-06-01', f'{year}-09-30') \
                      .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    def calc_ndvi(img):
        ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return img.addBands(ndvi)
        
    # 중간값(Median) 합성으로 한 장의 깨끗한 여름 지도 생성
    median_ndvi = summer_images.map(calc_ndvi).select('NDVI').median()
    
    # 각 농지 폴리곤(지적도 모양) 내부 픽셀들의 NDVI 평균/중간값을 계산
    # reducer.median() 을 사용하면 결과 feature에 'median' 속성이 추가됨
    reduced = median_ndvi.reduceRegions(
        collection=fc,
        reducer=ee.Reducer.median(),
        scale=10,
        crs='EPSG:4326'
    )
    
    # 식생이 없는(콘크리트 등) 곳은 NDVI가 낮게 나옴
    # median 값이 임계값(0.25 등)보다 작은 폴리곤만 필터링
    flagged_fc = reduced.filter(ee.Filter.notNull(['median'])) \
                        .filter(ee.Filter.lt('median', ndvi_threshold))
    
    # 파이썬 리스트 형태로 결과 반환
    result_geojson = flagged_fc.getInfo()
    return result_geojson.get('features', [])

def get_yearly_satellite_images(lon, lat, current_year=2024, years=3):
    """
    과거 3년간의 여름철(6~8월) 위성사진 썸네일 URL을 가져옵니다.
    """
    if not init_gee():
        return []
    
    point = ee.Geometry.Point([lon, lat])
    urls = []
    
    for y in range(current_year - years + 1, current_year + 1):
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        summer = s2.filterBounds(point) \
                   .filterDate(f'{y}-06-01', f'{y}-08-31') \
                   .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        # 이미지가 있으면 썸네일 URL 생성
        if summer.size().getInfo() > 0:
            median_img = summer.median()
            # B4(Red), B3(Green), B2(Blue) 트루컬러 시각화
            vis = {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000}
            url = median_img.visualize(**vis).getThumbURL({
                'dimensions': 1024, # 무료 API 한도 내에서 초고해상도로 렌더링
                'region': point.buffer(800), # 반경 800m로 설정 (식생 변화 관찰용)
                'format': 'png'
            })
            urls.append({'year': y, 'url': url})
        else:
            urls.append({'year': y, 'url': None})
            
    return urls

def get_ndvi_timeseries(lon, lat, current_year=2024, years=3):
    """
    과거 3년간의 NDVI 시계열 데이터를 추출합니다.
    """
    if not init_gee():
        return []
        
    point = ee.Geometry.Point([lon, lat])
    
    start_date = f'{current_year - years}-01-01'
    end_date = f'{current_year}-12-31'
    
    s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED") \
           .filterBounds(point) \
           .filterDate(start_date, end_date) \
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
           
    def calc_ndvi(img):
        ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return img.addBands(ndvi).set('system:time_start', img.get('system:time_start'))
        
    with_ndvi = s2.map(calc_ndvi)
    
    def extract_point(img):
        val = img.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point,
            scale=10
        ).get('NDVI')
        
        date = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd')
        return ee.Feature(None, {'NDVI': val, 'date': date})
        
    ts_features = with_ndvi.map(extract_point).getInfo().get('features', [])
    
    results = []
    for f in ts_features:
        props = f.get('properties', {})
        if props.get('NDVI') is not None:
            results.append((props.get('date'), props.get('NDVI')))
            
    # 날짜순 정렬
    results.sort(key=lambda x: x[0])
    return results

def calculate_violation_area(lon, lat, polygon_coords, year=2024, ndvi_threshold=0.25, project_id='gen-lang-client-0917558039'):
    """
    Takes a single parcel's polygon coordinates (list of [lon, lat] pairs) and calculates how many square meters 
    within that polygon have NDVI < threshold.
    """
    if not init_gee(project_id):
        return {'total_area_sqm': 0.0, 'violation_area_sqm': 0.0, 'violation_ratio': 0.0}
        
    try:
        polygon = ee.Geometry.Polygon([polygon_coords])
        
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        summer_images = s2.filterBounds(polygon) \
                          .filterDate(f'{year}-06-01', f'{year}-09-30') \
                          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        def calc_ndvi(img):
            ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return img.addBands(ndvi)
            
        median_ndvi = summer_images.map(calc_ndvi).select('NDVI').median()
        
        violation_mask = median_ndvi.lt(ndvi_threshold)
        pixel_area = ee.Image.pixelArea()
        violation_area_img = pixel_area.updateMask(violation_mask)
        
        violation_area = violation_area_img.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=polygon,
            scale=10,
            maxPixels=1e9
        ).get('area')
        
        total_area = polygon.area()
        
        v_area_val = violation_area.getInfo()
        t_area_val = total_area.getInfo()
        
        v_area_val = float(v_area_val) if v_area_val is not None else 0.0
        t_area_val = float(t_area_val) if t_area_val is not None else 0.0
        
        ratio = (v_area_val / t_area_val) if t_area_val > 0 else 0.0
        
        return {
            'total_area_sqm': t_area_val,
            'violation_area_sqm': v_area_val,
            'violation_ratio': ratio
        }
    except Exception as e:
        print(f"Error calculating violation area: {e}")
        return {'total_area_sqm': 0.0, 'violation_area_sqm': 0.0, 'violation_ratio': 0.0}

def detect_violation_start_date(lon, lat, years=5, ndvi_threshold=0.25, project_id='gen-lang-client-0917558039'):
    """
    Analyzes NDVI over a longer period (default 5 years) to find when vegetation first disappeared.
    """
    if not init_gee(project_id):
        return {'violation_start_year': None, 'yearly_ndvi': []}
        
    try:
        point = ee.Geometry.Point([lon, lat])
        current_year = 2024
        start_year = current_year - years + 1
        yearly_ndvi = []
        
        s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        
        for y in range(start_year, current_year + 1):
            summer = s2.filterBounds(point) \
                       .filterDate(f'{y}-06-01', f'{y}-09-30') \
                       .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            
            if summer.size().getInfo() > 0:
                def calc_ndvi(img):
                    return img.normalizedDifference(['B8', 'B4']).rename('NDVI')
                    
                median_ndvi = summer.map(calc_ndvi).median()
                val = median_ndvi.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=point,
                    scale=10
                ).get('NDVI').getInfo()
                
                if val is not None:
                    yearly_ndvi.append((y, float(val)))
                    
        violation_start_year = None
        for y, ndvi in yearly_ndvi:
            if ndvi < ndvi_threshold:
                violation_start_year = y
                break
                
        return {
            'violation_start_year': violation_start_year,
            'yearly_ndvi': yearly_ndvi
        }
    except Exception as e:
        print(f"Error detecting violation start date: {e}")
        return {'violation_start_year': None, 'yearly_ndvi': []}

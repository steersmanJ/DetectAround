from playwright.sync_api import sync_playwright
import time

# 카카오맵 좌측 패널(390px) 및 상하단 불필요 UI를 제외한 순수 지도 영역 크롭(Clip) 설정
CLIP_REGION = {"x": 390, "y": 80, "width": 1024 - 390 - 60, "height": 768 - 80 - 40}

def hide_ui(page):
    try:
        page.evaluate('''
            const popups = document.querySelectorAll('.Popup, .layer_usedistrict, .CoachMark, .View .Panel, .View .Search, .info_roadview, .InfoWindow, .infoWindow, .dimmed_layer, .layer_body');
            popups.forEach(el => { if(el) el.remove(); });
            
            // X(닫기) 버튼 강제 클릭
            const closeBtns = document.querySelectorAll('button[title="닫기"], .btn_close');
            closeBtns.forEach(btn => { if(btn) btn.click(); });
        ''')
    except:
        pass

def capture_skyview(lat, lon):
    """
    Playwright를 사용하여 카카오맵 스카이뷰(위성사진)를 최대 확대로 띄운 뒤
    지적편집도를 켜서 캡처하고 이미지 바이트(jpeg)를 반환합니다.
    (좌측 패널 등 불필요한 UI는 잘라냅니다.)
    """
    url = f"https://map.kakao.com/?map_type=TYPE_SKYVIEW&q={lat},{lon}&level=2"
    print(f"RPA 봇 구동 중... 스카이뷰 접속 시도: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1024, "height": 768}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            try:
                page.click(".usedistrict", timeout=3000)
            except:
                pass
            
            time.sleep(3)
            hide_ui(page)
            screenshot_bytes = page.screenshot(type="jpeg", quality=80, clip=CLIP_REGION)
            
            browser.close()
            return screenshot_bytes
            
    except Exception as e:
        print(f"RPA 스카이뷰 캡처 실패: {e}")
        return None

def capture_cadastral_map(lat, lon):
    """
    위성사진이 아닌 카카오맵 일반지도(TYPE_MAP) 상태에서 지적편집도를 활성화하여
    순수 지적도 캡처본을 반환합니다.
    """
    url = f"https://map.kakao.com/?map_type=TYPE_MAP&q={lat},{lon}&level=1"
    print(f"RPA 봇 구동 중... 지적도 접속 시도: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1024, "height": 768}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(3)
            
            try:
                page.evaluate('''
                    () => {
                        const els = document.querySelectorAll('button, a, label, span');
                        for (let el of els) {
                            if (el.innerText && el.innerText.includes('지적편집도')) {
                                el.click();
                                return;
                            }
                        }
                        const btn = document.querySelector('.btn_district, .ico_district');
                        if (btn) btn.click();
                    }
                ''')
            except:
                pass
                
            time.sleep(2)
            hide_ui(page)
            screenshot_bytes = page.screenshot(type="jpeg", quality=80, clip=CLIP_REGION)
            
            browser.close()
            return screenshot_bytes
            
    except Exception as e:
        print(f"RPA 지적도 캡처 실패: {e}")
        return None

def capture_historical_skyviews(lat, lon, num_years=3):
    """
    Playwright를 사용하여 카카오맵 스카이뷰 과거 사진을 최대 확대로 띄운 뒤
    최근 N년치의 스카이뷰를 캡처하여 반환합니다. (UI 크롭 적용)
    """
    url = f"https://map.kakao.com/?map_type=TYPE_SKYVIEW&q={lat},{lon}&level=2"
    print(f"RPA 봇 구동 중... 과거 스카이뷰 접속 시도: {url}")
    
    results = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                viewport={"width": 1024, "height": 768}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            time.sleep(3)
            hide_ui(page)
            
            years_to_capture = page.evaluate('''
                (num) => {
                    const els = document.querySelectorAll('.yearRadio');
                    const arr = [];
                    for (let i = 1; i < els.length && arr.length < num; i++) {
                        arr.push(els[i].innerText.trim());
                    }
                    return arr;
                }
            ''', num_years)
            
            for year in years_to_capture:
                clicked = page.evaluate('''
                    (y) => {
                        const els = document.querySelectorAll('.yearRadio');
                        for (let i = 0; i < els.length; i++) {
                            if (els[i].innerText.includes(y)) {
                                els[i].click();
                                return true;
                            }
                        }
                        return false;
                    }
                ''', year)
                
                if clicked:
                    print(f"{year}년도 위성사진 로딩 대기 중...")
                    time.sleep(3)
                    hide_ui(page)
                    screenshot_bytes = page.screenshot(type="jpeg", quality=80, clip=CLIP_REGION)
                    results.append({'year': year, 'bytes': screenshot_bytes})
            
            browser.close()
            print("과거 스카이뷰 캡처 완료!")
            return results
            
    except Exception as e:
        print(f"RPA 과거 스카이뷰 캡처 실패: {e}")
        return results

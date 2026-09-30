from playwright.sync_api import sync_playwright
import urllib.parse as urlparse
from urllib.parse import parse_qs
import time

def capture_roadview(lat, lon):
    """
    Playwright를 사용하여 카카오맵 로드뷰 화면을 360도(4방향)로 캡처하고 이미지 바이트(jpeg) 리스트를 반환합니다.
    """
    url = f"https://map.kakao.com/link/roadview/{lat},{lon}"
    print(f"RPA 봇 구동 중... 로드뷰 URL 접속 시도: {url}")
    
    screenshots = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 800, "height": 600})
            page = context.new_page()
            
            # 최초 접속 (리다이렉트 대기)
            page.goto(url, wait_until="networkidle", timeout=15000)
            time.sleep(3) # UI 및 파노라마 로딩 대기
            
            # 불필요한 레이어 숨김 처리
            def hide_ui():
                try:
                    page.evaluate('''
                        const overlays = document.querySelectorAll('.InfoRoadview, .view_map, .float_search, .BottomMenu');
                        overlays.forEach(el => el.style.display = 'none');
                    ''')
                except:
                    pass
            
            hide_ui()
            
            current_url = page.url
            parsed = urlparse.urlparse(current_url)
            qs = parse_qs(parsed.query)
            
            # URL에 pan 파라미터가 있으면 4방향 회전, 없으면 그냥 1장만 찍고 끝
            if 'pan' in qs:
                base_pan = float(qs['pan'][0])
                print(f"기본 각도 발견: {base_pan}도. 4방향 캡처를 시작합니다.")
                
                for i in range(4):
                    new_pan = (base_pan + (i * 90)) % 360
                    new_url = current_url.replace(f"pan={qs['pan'][0]}", f"pan={new_pan}")
                    
                    if i > 0: # 첫 번째 장은 이미 열려있으므로 이동 불필요
                        page.goto(new_url, wait_until="networkidle")
                        time.sleep(2)
                        hide_ui()
                        
                    screenshot_bytes = page.screenshot(type="jpeg", quality=80)
                    screenshots.append(screenshot_bytes)
            else:
                print("URL에서 각도(pan) 정보를 찾지 못해 1장만 캡처합니다.")
                screenshot_bytes = page.screenshot(type="jpeg", quality=80)
                screenshots.append(screenshot_bytes)
            
            browser.close()
            print(f"로드뷰 {len(screenshots)}장 캡처 완료!")
            return screenshots
            
    except Exception as e:
        print(f"RPA 로드뷰 캡처 실패: {e}")
        return []


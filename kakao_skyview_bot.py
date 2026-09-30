from playwright.sync_api import sync_playwright
import time

def capture_skyview(lat, lon):
    """
    Playwright를 사용하여 카카오맵 스카이뷰(위성사진)를 최대 확대로 띄운 뒤
    지적편집도를 켜서 캡처하고 이미지 바이트(jpeg)를 반환합니다.
    """
    url = f"https://map.kakao.com/?map_type=TYPE_SKYVIEW&q={lat},{lon}&level=2"
    print(f"RPA 봇 구동 중... 스카이뷰 접속 시도: {url}")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 봇 탐지 우회를 위한 User-Agent 및 충분한 화면 크기 설정
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                viewport={"width": 1024, "height": 768}
            )
            page = context.new_page()
            
            # 페이지 접속 (네트워크 요청이 잦아들 때까지 대기)
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # 지적편집도 버튼 클릭 시도 (에러 나도 진행)
            try:
                page.click(".usedistrict", timeout=3000)
                print("지적편집도 버튼 클릭 성공")
            except Exception as e:
                print("지적편집도 버튼 클릭 실패:", e)
                pass
            
            # 위성 지도 타일 및 지적선이 완전히 렌더링되도록 3초 넉넉히 대기
            time.sleep(3)
            
            # 불필요한 UI 숨김 처리 (검색창, 사이드바, 컨트롤 버튼 등)
            try:
                page.evaluate('''
                    const overlays = document.querySelectorAll('.View .Panel, .View .Search, .info_roadview, .CoachMark, .layer_usedistrict');
                    overlays.forEach(el => { if(el) el.style.display = 'none'; });
                ''')
            except Exception as js_err:
                pass 
                
            # 스크린샷 캡처
            screenshot_bytes = page.screenshot(type="jpeg", quality=80)
            
            browser.close()
            print("스카이뷰 캡처 완료!")
            return screenshot_bytes
            
    except Exception as e:
        print(f"RPA 스카이뷰 캡처 실패: {e}")
        return None

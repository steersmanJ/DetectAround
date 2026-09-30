from playwright.sync_api import sync_playwright
import time

def capture_roadview(lat, lon):
    """
    Playwright를 사용하여 카카오맵 로드뷰 화면을 캡처하고 이미지 바이트(jpeg)를 반환합니다.
    """
    url = f"https://map.kakao.com/link/roadview/{lat},{lon}"
    print(f"RPA 봇 구동 중... 로드뷰 URL 접속 시도: {url}")
    
    try:
        with sync_playwright() as p:
            # 브라우저 실행 (headless=True 이면 윈도우 창이 눈에 보이지 않음)
            browser = p.chromium.launch(headless=True)
            # 깔끔한 비율의 해상도 설정
            context = browser.new_context(viewport={"width": 1024, "height": 768})
            page = context.new_page()
            
            # 로드뷰 페이지 접속 (네트워크 요청이 잦아들 때까지 대기)
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # 카카오 로드뷰가 캔버스에 렌더링될 때까지 안전하게 3초 추가 대기
            time.sleep(3)
            
            # 지도 위에 뜨는 불필요한 레이어(주소창, 버튼 등) 숨김 처리 시도
            try:
                # 카카오맵 UI 클래스들을 숨겨서 순수 로드뷰 사진만 건지도록 시도
                page.evaluate('''
                    const overlays = document.querySelectorAll('.InfoRoadview, .view_map, .float_search, .BottomMenu');
                    overlays.forEach(el => el.style.display = 'none');
                ''')
            except Exception as js_err:
                pass # 실패하더라도 전체 스크린샷 진행
                
            # 스크린샷 캡처 (용량 최적화를 위해 JPEG 80% 품질)
            screenshot_bytes = page.screenshot(type="jpeg", quality=80)
            
            browser.close()
            print("로드뷰 캡처 완료!")
            return screenshot_bytes
            
    except Exception as e:
        print(f"RPA 로드뷰 캡처 실패: {e}")
        return None

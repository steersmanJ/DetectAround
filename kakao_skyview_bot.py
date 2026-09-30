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

def capture_historical_skyviews(lat, lon, num_years=3):
    """
    Playwright를 사용하여 카카오맵 스카이뷰 과거 사진을 최대 확대로 띄운 뒤
    최근 N년치의 스카이뷰를 캡처하여 [{'year': '2023', 'bytes': ...}, ...] 형태로 반환합니다.
    """
    url = f"https://map.kakao.com/?map_type=TYPE_SKYVIEW&q={lat},{lon}&level=2"
    print(f"RPA 봇 구동 중... 과거 스카이뷰 접속 시도: {url}")
    
    results = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                viewport={"width": 1024, "height": 768}
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle", timeout=15000)
            
            # 방해 요소 숨김
            def hide_ui():
                try:
                    page.evaluate('''
                        const overlays = document.querySelectorAll('.View .Panel, .View .Search, .info_roadview, .CoachMark, .layer_usedistrict');
                        overlays.forEach(el => { if(el) el.style.display = 'none'; });
                    ''')
                except:
                    pass
            
            time.sleep(3) # 첫 화면 로딩 대기
            hide_ui()
            
            # 연도별 라디오 버튼을 찾고 최근 num_years개 만큼 순회하며 클릭
            years_to_capture = page.evaluate('''
                (num) => {
                    const els = document.querySelectorAll('.yearRadio');
                    const arr = [];
                    // 보통 0번 인덱스가 '최근사진'이고 1번부터 연도임.
                    // 최근사진은 제외하고 과거 연도부터 추출 (1번부터)
                    for (let i = 1; i < els.length && arr.length < num; i++) {
                        arr.push(els[i].innerText.trim());
                    }
                    return arr;
                }
            ''', num_years)
            
            for year in years_to_capture:
                # 자바스크립트로 해당 연도 버튼 클릭
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
                    time.sleep(3) # 타일 로딩 대기
                    hide_ui() # 지적편집도 등 초기화 대비 숨김 유지
                    screenshot_bytes = page.screenshot(type="jpeg", quality=80)
                    results.append({'year': year, 'bytes': screenshot_bytes})
            
            browser.close()
            print("과거 스카이뷰 캡처 완료!")
            return results
            
    except Exception as e:
        print(f"RPA 과거 스카이뷰 캡처 실패: {e}")
        return results

import os
import datetime
from fpdf import FPDF

# 현재 스크립트 경로를 기준으로 폰트 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(CURRENT_DIR, "NanumGothic.ttf")

def generate_report_pdf(pnu, jibun, jimok_char, jimok_desc, ndvi_score):
    """
    불법 농지 전용 신고용 PDF 보고서를 생성하고 바이트 데이터로 반환합니다.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # 폰트 등록 (한글 지원을 위해 필수)
    if os.path.exists(FONT_PATH):
        pdf.add_font("Nanum", "", FONT_PATH, uni=True)
        pdf.set_font("Nanum", "", 12)
    else:
        pdf.set_font("Arial", "", 12)  # 폰트가 없으면 기본 폰트 (한글 깨질 수 있음)

    # ── 제목 ──
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=18)
    pdf.cell(0, 15, "농지법 위반 의심 현장 조사 보고서", ln=True, align="C")
    pdf.ln(10)

    # ── 1. 기본 정보 ──
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=14)
    pdf.cell(0, 10, "[ 1. 대상 농지 정보 ]", ln=True)
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=12)
    
    pdf.cell(40, 8, "고유번호(PNU) :", border=0)
    pdf.cell(0, 8, str(pnu), border=0, ln=True)
    
    pdf.cell(40, 8, "소재지(지번) :", border=0)
    pdf.cell(0, 8, str(jibun), border=0, ln=True)
    
    pdf.cell(40, 8, "지목 :", border=0)
    pdf.cell(0, 8, f"{jimok_char} ({jimok_desc})", border=0, ln=True)
    
    pdf.cell(40, 8, "조사 일자 :", border=0)
    pdf.cell(0, 8, datetime.datetime.now().strftime("%Y-%m-%d"), border=0, ln=True)
    pdf.ln(10)

    # ── 2. 탐지 결과 요약 ──
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=14)
    pdf.cell(0, 10, "[ 2. 위성 데이터 탐지 결과 ]", ln=True)
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=12)
    
    pdf.cell(40, 8, "위성 식생지수 :", border=0)
    pdf.cell(0, 8, f"NDVI {ndvi_score} (기준치 미달)", border=0, ln=True)
    pdf.multi_cell(0, 8, "→ 정상적인 농작물이 존재하지 않거나, 콘크리트 포장/인공 건축물 등으로 덮여 있어 농지 본연의 기능을 상실한 것으로 강력히 의심됩니다.")
    pdf.ln(10)

    # ── 3. 국민신문고 신고용 템플릿 ──
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=14)
    pdf.cell(0, 10, "[ 3. 국민신문고 신고용 텍스트 (복사 가능) ]", ln=True)
    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=12)
    
    template_text = (
        f"농지법 위반 신고합니다.\n"
        f"지번: {jibun} (지목: {jimok_desc})\n\n"
        f"위 토지는 지목상 농지임에도 불구하고, 위성 분석 결과 식생이 전혀 확인되지 않습니다. "
        f"현재 주차장, 창고, 폐기물 적치장 등 농업 외의 용도로 무단 전용되어 사용되고 있을 확률이 매우 높습니다.\n\n"
        f"해당 지번에 대해 농지전용 허가나 타용도 일시사용 허가를 받았는지 현장 점검을 요청드리며, "
        f"불법 전용이 확인될 경우 농지법에 따른 원상회복 명령 및 행정처분을 내려주시기 바랍니다."
    )
    
    # 박스 형태로 출력
    pdf.multi_cell(0, 8, template_text, border=1)
    pdf.ln(15)

    pdf.set_font("Nanum" if os.path.exists(FONT_PATH) else "Arial", size=10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "본 보고서는 Global Vegetation Analysis Dashboard(위성 데이터 기반)에 의해 자동 생성되었습니다.", align="C")

    # PDF를 byte string으로 반환 (스트림릿 다운로드용)
    return bytes(pdf.output())

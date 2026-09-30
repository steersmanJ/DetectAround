import io
import datetime
import requests
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from vworld_api import get_detailed_address, get_static_map_image, get_land_use_plan, parse_jurisdiction, estimate_penalty
from gee_analyzer import get_yearly_satellite_images, get_ndvi_timeseries, calculate_violation_area, detect_violation_start_date

def create_ndvi_graph(ts_data):
    """
    NDVI 시계열 데이터를 바탕으로 matplotlib 그래프 이미지를 생성하여 바이트로 반환합니다.
    """
    if not ts_data:
        return None
        
    dates = [x[0] for x in ts_data]
    ndvis = [x[1] for x in ts_data]
    
    # 폰트 깨짐 방지를 위해 영어로 설정하거나, 폰트 설정을 스킵하고 기본 폰트 사용
    plt.figure(figsize=(7, 3))
    plt.plot(dates, ndvis, marker='o', linestyle='-', color='g')
    plt.axhline(y=0.25, color='r', linestyle='--', label='Threshold (0.25)')
    
    plt.title('NDVI Time-Series (Last 3 Years)', fontsize=12)
    plt.xlabel('Date')
    plt.ylabel('NDVI (Vegetation Index)')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    # x축 레이블 간격 조절 (너무 촘촘하지 않게)
    plt.xticks(dates[::max(1, len(dates)//6)], rotation=20)
    plt.legend()
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    plt.close()
    buf.seek(0)
    return buf

def generate_report_docx(lon, lat, pnu, jibun_short, jimok_char, jimok_desc, ndvi_score, jiga=None, polygon_coords=None):
    """
    python-docx를 사용하여 농지법 위반 의심 현장 조사 보고서를 생성합니다.
    신고 완결성을 위해 토지이용계획, 위반 면적, 위반 시점, 예상 벌금 등을 자동 산출합니다.
    """
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Malgun Gothic'
    style.font.size = Pt(11)
    
    # ── 사전 데이터 수집 ──
    addr_info = get_detailed_address(lon, lat)
    parcel_addr = addr_info.get("parcel") or jibun_short
    road_addr = addr_info.get("road") or "(도로명 주소 없음)"
    
    # 토지이용계획 조회
    land_use = get_land_use_plan(lon, lat)
    
    # 관할 지자체 파싱
    jurisdiction = parse_jurisdiction(parcel_addr)
    
    # 위반 면적 산출
    violation_area_info = None
    try:
        violation_area_info = calculate_violation_area(lon, lat, polygon_coords)
    except Exception as e:
        print(f"위반 면적 산출 실패: {e}")
    
    # 위반 시점 추정
    violation_start_info = None
    try:
        violation_start_info = detect_violation_start_date(lon, lat)
    except Exception as e:
        print(f"위반 시점 추정 실패: {e}")
    
    # 예상 벌금 산출
    penalty_info = None
    if jiga and violation_area_info and violation_area_info.get('violation_area_sqm'):
        try:
            penalty_info = estimate_penalty(
                int(jiga),
                violation_area_info.get('total_area_sqm', 0),
                violation_area_info.get('violation_area_sqm', 0),
                land_use.get('is_promotion_area', False)
            )
        except Exception as e:
            print(f"벌금 산출 실패: {e}")
    
    # ── 제목 ──
    title = doc.add_heading('농지법 위반 의심 현장 조사 보고서', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # ── 1. 대상 농지 정보 ──
    doc.add_heading('[ 1. 대상 농지 정보 ]', level=2)
    
    p_info = doc.add_paragraph()
    p_info.add_run("고유번호(PNU) : ").bold = True
    p_info.add_run(f"{pnu}\n")
    p_info.add_run("지번 주소 : ").bold = True
    p_info.add_run(f"{parcel_addr}\n")
    p_info.add_run("도로명 주소 : ").bold = True
    p_info.add_run(f"{road_addr}\n")
    p_info.add_run("지목 : ").bold = True
    p_info.add_run(f"{jimok_char} ({jimok_desc})\n")
    
    # 토지이용계획 정보
    p_info.add_run("용도지역 : ").bold = True
    p_info.add_run(f"{land_use.get('use_zone', '미확인')}\n")
    p_info.add_run("농업진흥지역 구분 : ").bold = True
    p_info.add_run(f"{land_use.get('agri_promotion', '미확인')}\n")
    p_info.add_run("적용 벌칙 : ").bold = True
    p_info.add_run(f"{land_use.get('penalty_clause', '미확인')}\n")
    
    if jiga:
        try:
            formatted_jiga = f"{int(jiga):,}원/㎡"
            p_info.add_run("개별공시지가 : ").bold = True
            p_info.add_run(f"{formatted_jiga}\n")
        except:
            pass
    
    # 위반 면적
    if violation_area_info:
        total_sqm = violation_area_info.get('total_area_sqm', 0)
        viol_sqm = violation_area_info.get('violation_area_sqm', 0)
        viol_ratio = violation_area_info.get('violation_ratio', 0)
        p_info.add_run("전체 필지 면적 : ").bold = True
        p_info.add_run(f"{total_sqm:,.0f}㎡\n")
        p_info.add_run("위반 추정 면적 : ").bold = True
        p_info.add_run(f"약 {viol_sqm:,.0f}㎡ (전체의 {viol_ratio*100:.0f}%)\n")
    
    # 위반 시점
    if violation_start_info and violation_start_info.get('violation_start_year'):
        p_info.add_run("위반 추정 시점 : ").bold = True
        p_info.add_run(f"{violation_start_info['violation_start_year']}년경부터 현재까지 계속\n")
    
    # 예상 벌금
    if penalty_info:
        p_info.add_run("예상 벌금 범위 : ").bold = True
        p_info.add_run(f"{penalty_info['description']}\n")
    
    # 관할 지자체
    if jurisdiction.get('full'):
        p_info.add_run("관할 지자체 : ").bold = True
        p_info.add_run(f"{jurisdiction['full']}\n")
            
    p_info.add_run("조사 일자 : ").bold = True
    p_info.add_run(f"{datetime.datetime.now().strftime('%Y-%m-%d')}")
    doc.add_paragraph()

    # ── 2. 현장 위성 및 지적도 사진 ──
    doc.add_heading('[ 2. 현재 상태 (지적도 및 지적위성) ]', level=2)
    
    # 1. 일반지도(지적도) 가져오기: 카카오 RPA 우선 시도, 실패시 Vworld
    graphic_img = None
    try:
        from kakao_skyview_bot import capture_cadastral_map
        kakao_cadastral_bytes = capture_cadastral_map(lat, lon)
        if kakao_cadastral_bytes:
            graphic_img = kakao_cadastral_bytes
    except:
        pass
        
    if not graphic_img:
        graphic_img = get_static_map_image(lon, lat, map_type="GRAPHIC")
        
    hybrid_img = get_static_map_image(lon, lat, map_type="PHOTO_HYBRID")
    
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    if graphic_img:
        run = table.cell(0, 0).paragraphs[0].add_run()
        run.add_picture(io.BytesIO(graphic_img), width=Inches(2.8))
        table.cell(0, 0).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        table.cell(0, 0).add_paragraph("지적도 (필지 경계)").alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    if hybrid_img:
        run2 = table.cell(0, 1).paragraphs[0].add_run()
        run2.add_picture(io.BytesIO(hybrid_img), width=Inches(2.8))
        table.cell(0, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        table.cell(0, 1).add_paragraph("위성 지적도").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()
    
    # ── 2-1. 카카오 초고해상도 스카이뷰 (RPA 캡처) ──
    try:
        from kakao_skyview_bot import capture_skyview
        sv_bytes = capture_skyview(lat, lon)
        if sv_bytes:
            p_sv_desc = doc.add_paragraph("▼ 초고해상도 스카이뷰 (지적편집도 적용, 최대 확대)")
            p_sv_desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_sv = doc.add_paragraph()
            p_sv.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p_sv.add_run().add_picture(io.BytesIO(sv_bytes), width=Inches(6.0))
    except Exception as e:
        doc.add_paragraph(f"(스카이뷰 RPA 구동 실패: {e})")
    doc.add_paragraph()

    # ── 3. 식생지수 시계열 분석 (과거 3년) ──
    doc.add_heading('[ 3. 과거 3년 식생 변화(NDVI) 추이 ]', level=2)
    doc.add_paragraph("아래 그래프는 과거 3년간 해당 토지의 식물 활력도(NDVI) 변화를 나타냅니다. 0.25 이하로 떨어진 시점부터 식물이 사라진(불법 전용된) 것으로 강력히 의심됩니다.")
    
    ts_data = get_ndvi_timeseries(lon, lat, years=3)
    graph_buf = create_ndvi_graph(ts_data)
    if graph_buf:
        p_graph = doc.add_paragraph()
        p_graph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_graph.add_run().add_picture(graph_buf, width=Inches(6.0))
    else:
        doc.add_paragraph("(시계열 데이터를 가져오지 못했습니다.)")
    doc.add_paragraph()

    # ── 4. 과거 3년 여름철 위성사진 비교 ──
    doc.add_heading('[ 4. 과거 3년 위성사진 비교 ]', level=2)
    doc.add_paragraph("연도별(6~8월) 맑은 날을 합성한 위성사진입니다. 대상 농지의 변화를 시각적으로 확인할 수 있습니다.")
    
    yearly_images = get_yearly_satellite_images(lon, lat, years=3)
    if yearly_images:
        num_imgs = len(yearly_images)
        t_img = doc.add_table(rows=1, cols=num_imgs)
        t_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for i, item in enumerate(yearly_images):
            cell = t_img.cell(0, i)
            url = item.get('url')
            year = item.get('year')
            p_cell = cell.paragraphs[0]
            p_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if url:
                try:
                    res = requests.get(url, verify=False)
                    if res.status_code == 200:
                        p_cell.add_run().add_picture(io.BytesIO(res.content), width=Inches(2.0))
                except:
                    p_cell.add_run("(이미지 로드 실패)")
            else:
                p_cell.add_run("(구름으로 인해 사진 없음)")
            cell.add_paragraph(f"{year}년 여름").alignment = WD_ALIGN_PARAGRAPH.CENTER
            
    doc.add_paragraph()
    doc.add_paragraph("▼ [RPA 초고해상도 캡처] 카카오맵 과거 위성사진 비교")
    
    try:
        from kakao_skyview_bot import capture_historical_skyviews
        hist_skyviews = capture_historical_skyviews(lat, lon, num_years=3)
        
        if hist_skyviews:
            t_hist = doc.add_table(rows=1, cols=len(hist_skyviews))
            t_hist.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for i, item in enumerate(hist_skyviews):
                cell = t_hist.cell(0, i)
                p_cell = cell.paragraphs[0]
                p_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_cell.add_run().add_picture(io.BytesIO(item['bytes']), width=Inches(2.0))
                cell.add_paragraph(f"{item['year']} (카카오)").alignment = WD_ALIGN_PARAGRAPH.CENTER
    except Exception as e:
        doc.add_paragraph(f"(카카오 과거 위성사진 캡처 실패: {e})")
        
    doc.add_paragraph()
    # ── 5. 현장 로드뷰 (RPA 캡처) ──
    doc.add_heading('[ 5. 카카오맵 현장 로드뷰 ]', level=2)
    doc.add_paragraph("파이썬 RPA를 통해 자동 캡처된 현장 주변의 로드뷰 사진입니다. (지형지물 및 불법 건축물/주차장 확인용)")
    
    try:
        from roadview_bot import capture_roadview
        rv_bytes_list = capture_roadview(lat, lon)
        if rv_bytes_list and len(rv_bytes_list) > 0:
            if len(rv_bytes_list) == 1:
                p_rv = doc.add_paragraph()
                p_rv.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_rv.add_run().add_picture(io.BytesIO(rv_bytes_list[0]), width=Inches(6.0))
            else:
                doc.add_paragraph("💡 아래 4장의 360도 회전 사진 중 타겟 농지가 가장 잘 보이는 사진만 남기고 나머지는 삭제해 주세요.")
                rv_table = doc.add_table(rows=2, cols=2)
                rv_table.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                for idx, img_bytes in enumerate(rv_bytes_list):
                    row_idx = idx // 2
                    col_idx = idx % 2
                    cell = rv_table.cell(row_idx, col_idx)
                    p_cell = cell.paragraphs[0]
                    p_cell.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_cell.add_run().add_picture(io.BytesIO(img_bytes), width=Inches(2.8))
                    cell.add_paragraph(f"사진 {idx+1}").alignment = WD_ALIGN_PARAGRAPH.CENTER
        else:
            doc.add_paragraph("(로드뷰를 캡처하지 못했거나 해당 지역에 로드뷰가 없습니다.)")
    except Exception as e:
        doc.add_paragraph(f"(RPA 모듈 구동 실패: {e})")
    doc.add_paragraph()

    # ── 6. 국민신문고 신고 템플릿 (법적 완결성 확보) ──
    doc.add_heading('[ 6. 국민신문고 신고서 ]', level=2)
    
    # 위반 시점 텍스트
    violation_time_str = "확인 중"
    if violation_start_info and violation_start_info.get('violation_start_year'):
        violation_time_str = f"{violation_start_info['violation_start_year']}년경부터 현재까지 계속 중"
    
    # 위반 면적 텍스트
    violation_area_str = "(위성 분석을 통해 추정 필요)"
    total_area_str = ""
    if violation_area_info:
        total_sqm = violation_area_info.get('total_area_sqm', 0)
        viol_sqm = violation_area_info.get('violation_area_sqm', 0)
        violation_area_str = f"전체 {total_sqm:,.0f}㎡ 중 약 {viol_sqm:,.0f}㎡"
        total_area_str = f", 면적: {total_sqm:,.0f}㎡"
    
    # 농업진흥구역 여부에 따른 법조항
    agri_promo = land_use.get('agri_promotion', '미확인')
    use_zone = land_use.get('use_zone', '미확인')
    penalty = land_use.get('penalty_clause', '농지법 제58조')
    is_promo = land_use.get('is_promotion_area', False)
    
    promo_emphasis = ""
    if is_promo:
        promo_emphasis = f"본 토지는 {agri_promo} 내 우량농지로서 농지법 제32조 행위제한 및 제34조를 정면으로 위반하여 {penalty} 대상입니다.\n\n"
    
    # 관할 지자체
    jurisdiction_str = jurisdiction.get('full', '해당 시·군·구')
    
    template_title = f"[농지법 제34조 위반] {parcel_addr} 농지 불법전용 및 무단 형질변경 신고"
    
    template_text = (
        f"[제목] {template_title}\n\n"
        f"[민원 취지]\n"
        f"농지법 제34조(농지의 전용허가)를 위반하여 농지를 무단 전용하고 있는 현장에 대해 "
        f"현장 실태조사를 실시하고, 동법 제42조에 따른 원상회복명령 및 {penalty.split('(')[0]}에 따른 "
        f"형사고발 처분을 요청합니다.\n\n"
        f"{promo_emphasis}"
        f"[신고 대상 토지 정보]\n"
        f"1. 소재지: {parcel_addr} (공부상 지목: {jimok_char}({jimok_desc}){total_area_str})\n"
        f"2. 토지이용계획: {use_zone} / {agri_promo}\n"
        f"3. 관할 지자체: {jurisdiction_str}\n\n"
        f"[구체적 위반 행위 사실]\n"
        f"1. 위반 일시: {violation_time_str}\n"
        f"2. 위반 면적: {violation_area_str}\n"
        f"3. 행위 내용:\n"
        f"  - 농지전용허가를 득하지 않고 농지를 비농업 목적으로 무단 사용 중입니다.\n"
        f"  - 위성 식생분석(NDVI) 결과 해당 필지의 식생지수가 {ndvi_score:.2f}로 "
        f"정상 영농 기준치(0.25) 미만이며, 과거 위성사진 비교 결과 형질변경이 확인됩니다.\n"
        f"  - (※ 구체적 위반 유형은 첨부 사진 참조: 주차장/건축물/적치장/성토 등)\n\n"
        f"[관련 법령 위반 내역]\n"
        f"1. 농지법 제34조(농지전용허가) 위반 → {penalty}\n"
        f"2. 건축법 제20조(가설건축물) 및 국토계획법 제56조(개발행위허가) 위반 여부 확인 요망\n\n"
        f"[요청 사항]\n"
        f"1. 소관 부서(농정과, 건축과, 도시과)의 합동 현장 출장 및 위반 면적 실측\n"
        f"2. 농지법 제42조에 따른 원상회복명령 사전통지 및 발령\n"
        f"3. 원상회복명령 불응 시 제42조의2에 따른 이행강제금 부과\n"
        f"4. {penalty.split('(')[0]}에 따른 관할 경찰서 형사고발 조치\n"
        f"5. 현장 점검 결과 및 향후 행정처분 일정을 민원 답변을 통해 구체적으로 통보 요망\n\n"
        f"[첨부 서류]\n"
        f"1. 위성 분석 기반 현장 조사 보고서 1부 (본 문서)\n"
        f"2. 시계열 위성사진 비교자료 (과거 3~5개년)\n"
        f"3. 초고해상도 스카이뷰 및 로드뷰 캡처 자료\n"
        f"4. 식생지수(NDVI) 시계열 분석 그래프\n"
        f"5. 토지이용계획확인서 발급 후 별도 첨부 요망"
    )
    p_template = doc.add_paragraph(template_text)
    p_template.paragraph_format.left_indent = Inches(0.3)
    p_template.style.font.size = Pt(10)
    
    # 예상 벌금 참고 정보
    if penalty_info:
        doc.add_paragraph()
        p_penalty = doc.add_paragraph()
        p_penalty.add_run("※ 참고: 예상 벌금 범위\n").bold = True
        p_penalty.add_run(f"{penalty_info['description']}")
    
    doc.add_paragraph()
    p_footer = doc.add_paragraph("본 보고서는 농지법 위반 원격 탐지 시스템(Global Vegetation Analysis Dashboard)에 의해 자동 생성되었습니다.")
    p_footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    
    return doc_io.read()

import math
import streamlit as st
import folium
from streamlit_folium import st_folium

from vworld_api import get_cadastral_box, get_cadastral_info
from gee_analyzer import check_current_vegetation

st.set_page_config(page_title="Geospatial Analysis Dashboard", layout="wide")
st.title("🌍 Global Vegetation Analysis Dashboard (V2)")

# ── 세션 상태 ──
for k, v in {
    "detected_areas": [],
    "navigate_to": None,
    "clicked_info": None,
    "prev_click_coords": None,
    "map_center": [37.5665, 126.9780],
    "map_zoom": 15,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

JIMOK = {
    "전": "밭 (Field)", "답": "논 (Paddy)", "과": "과수원 (Orchard)",
    "임": "임야", "대": "대지 (Site)", "잡": "잡종지", "도": "도로",
    "하": "하천", "목": "목장용지", "주": "주차장", "학": "학교용지",
    "공": "공장용지", "창": "창고용지", "유": "유지", "종": "종교용지",
}

def parse_jibun(s):
    if not s: return "", "", ""
    return s[:-1], s[-1], JIMOK.get(s[-1], s[-1])

def poly_center(f):
    gt, co = f["geometry"]["type"], f["geometry"]["coordinates"]
    r = co[0] if gt == "Polygon" else co[0][0] if gt == "MultiPolygon" else None
    if not r: return None, None
    return sum(c[1] for c in r)/len(r), sum(c[0] for c in r)/len(r)

# ── 네비게이션 (📍 버튼 클릭 시) ──
nav = st.session_state.get("navigate_to")
if nav:
    st.session_state["map_center"] = [nav["lat"], nav["lon"]]
    st.session_state["map_zoom"] = nav.get("zoom", 18)
    st.session_state["navigate_to"] = None

# ── 사이드바 ──
with st.sidebar:
    st.header("⚙️ Settings")
    map_type = st.radio("Map Layer", ["OpenStreetMap", "Satellite", "Satellite + Cadastral"], horizontal=True)
    target_year = st.number_input("Analysis Year", 2015, 2025, 2023)
    ndvi_threshold = st.slider("NDVI Threshold", 0.05, 0.50, 0.25, 0.05)
    search_radius = st.slider("Search Radius (m)", 100, 2000, 500, 100,
        help="Detection area around the clicked point")

    st.divider()

    clicked = st.session_state.get("prev_click_coords")
    if clicked:
        st.success(f"Target: `{clicked[0]:.5f}, {clicked[1]:.5f}`")
    else:
        st.warning("Click on the map to set a target point.")

    if st.button("🔍 Detect Around Clicked Point", disabled=not clicked, type="primary", use_container_width=True):
        lat, lon = clicked
        lat_off = search_radius / 111000
        lon_off = search_radius / (111000 * math.cos(math.radians(lat)))
        min_lat, max_lat = lat - lat_off, lat + lat_off
        min_lon, max_lon = lon - lon_off, lon + lon_off

        with st.spinner("Step 1/2 — Fetching cadastral data..."):
            agri = get_cadastral_box(min_lon, min_lat, max_lon, max_lat)
        if not agri:
            st.warning("No agricultural parcels found.")
            st.session_state["detected_areas"] = []
        else:
            st.info(f"Found {len(agri)} agricultural parcels.")
            with st.spinner("Step 2/2 — Analyzing NDVI..."):
                try:
                    res = check_current_vegetation(agri, year=target_year, ndvi_threshold=ndvi_threshold)
                    st.session_state["detected_areas"] = res
                    st.success(f"Done! {len(res)} suspicious." if res else "All healthy!")
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state["detected_areas"]:
        if st.button("🗑️ Clear Results", use_container_width=True):
            st.session_state["detected_areas"] = []
            st.session_state["clicked_info"] = None
            st.rerun()

# ── 지도 생성 ──
mc = st.session_state["map_center"]
mz = st.session_state["map_zoom"]

if map_type == "Satellite":
    m = folium.Map(location=mc, zoom_start=mz, tiles=None)
    folium.TileLayer("https://xdworld.vworld.kr/2d/Satellite/service/{z}/{x}/{y}.jpeg", attr="V").add_to(m)
elif map_type == "Satellite + Cadastral":
    m = folium.Map(location=mc, zoom_start=mz, tiles=None)
    folium.TileLayer("https://xdworld.vworld.kr/2d/Satellite/service/{z}/{x}/{y}.jpeg", attr="V").add_to(m)
    folium.TileLayer("https://xdworld.vworld.kr/2d/Hybrid/service/{z}/{x}/{y}.png", attr="V", overlay=True).add_to(m)
else:
    m = folium.Map(location=mc, zoom_start=mz, tiles="OpenStreetMap")

# 탐지 반경 원형 표시 (클릭한 곳이 있으면)
if clicked:
    folium.Circle(
        location=[clicked[0], clicked[1]],
        radius=search_radius,
        color="#3388ff", weight=2, fill=True, fill_opacity=0.1,
        tooltip=f"Detection area ({search_radius}m radius)"
    ).add_to(m)

# 탐지 결과 폴리곤
for idx, feat in enumerate(st.session_state["detected_areas"]):
    gt, co = feat["geometry"]["type"], feat["geometry"]["coordinates"]
    p = feat.get("properties", {})
    jibun = p.get("jibun", "?")
    lot, jc, jd = parse_jibun(jibun)
    med = p.get("median")
    ns = f"{med:.3f}" if isinstance(med, (int, float)) else "?"
    ph = f"<b>#{idx+1}</b><br>{lot}·{jc}({jd})<br>PNU:{p.get('pnu','?')}<br>NDVI:{ns}"
    def _d(ring, m=m, ph=ph, idx=idx, jibun=jibun):
        folium.Polygon([[c[1],c[0]] for c in ring], color="#e74c3c", weight=2,
            fill=True, fill_color="#e74c3c", fill_opacity=0.5,
            tooltip=f"#{idx+1} {jibun}", popup=folium.Popup(ph, max_width=300)).add_to(m)
    if gt == "Polygon": _d(co[0])
    elif gt == "MultiPolygon":
        for poly in co: _d(poly[0])

# ── 레이아웃 ──
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗺️ Map View")
    st.caption("① Click map to set target · ② Adjust radius · ③ Run Detection")

    # ═══════════════════════════════════════════════════════════
    # returned_objects=["last_clicked"] ONLY → 깜박임 완전 제거
    # bounds 사용하지 않음 → 클릭 좌표 + 반경으로 탐지 영역 결정
    # ═══════════════════════════════════════════════════════════
    st_data = st_folium(m, width=800, height=600, key="main_map", returned_objects=["last_clicked"])

    if st_data and st_data.get("last_clicked"):
        click = st_data["last_clicked"]
        coords = (round(click["lat"], 5), round(click["lng"], 5))
        if coords != st.session_state.get("prev_click_coords"):
            st.session_state["prev_click_coords"] = coords
            # 클릭한 좌표를 지도 중심으로 저장 (레이어 변경 시 위치 보존)
            st.session_state["map_center"] = list(coords)
            info = get_cadastral_info(click["lng"], click["lat"])
            st.session_state["clicked_info"] = {"lat": click["lat"], "lon": click["lng"], "info": info}
            st.rerun()

with col2:
    st.subheader("📌 Land Type Lookup")
    ci = st.session_state.get("clicked_info")
    if ci:
        info = ci.get("info")
        st.markdown(f"📍 `{ci['lat']:.5f}`, `{ci['lon']:.5f}`")
        if info:
            lot, jc, jd = parse_jibun(info.get("jibun", ""))
            st.markdown(f"**PNU:** `{info.get('pnu','?')}`")
            st.markdown(f"**Lot:** `{lot}`")
            if info.get("is_agri"):
                st.error(f"🌾 **{jc}** — {jd} (**AGRICULTURAL**)")
            else:
                st.info(f"**{jc}** — {jd}")
        else:
            st.warning("No data at this location.")
    else:
        st.info("Click anywhere on the map.")

    st.divider()

    st.subheader("📋 Detection Results")
    results = st.session_state["detected_areas"]
    if results:
        st.caption(f"**{len(results)}** suspicious parcel(s)")
        
        # DOCX 생성을 위해 임포트
        from docx_generator import generate_report_docx
        
        for idx, feat in enumerate(results):
            p = feat.get("properties", {})
            jibun = p.get("jibun", "")
            lot, jc, jd = parse_jibun(jibun)
            med = p.get("median")
            ns = f"{med:.3f}" if isinstance(med, (int, float)) else "?"
            clat, clon = poly_center(feat)
            pnu = p.get("pnu", "?")
            
            with st.container(border=True):
                st.markdown(f"**#{idx+1}** · `{lot}` · **{jc}** ({jd})")
                st.caption(f"PNU `{pnu}` · NDVI `{ns}`")
                
                col_nav, col_pdf = st.columns(2)
                with col_nav:
                    if clat and clon:
                        if st.button(f"📍 Go", key=f"nav_{idx}", use_container_width=True):
                            st.session_state["navigate_to"] = {"lat": clat, "lon": clon, "zoom": 18}
                            st.rerun()
                with col_pdf:
                    if clat and clon:
                        docx_key = f"docx_bytes_{idx}"
                        if docx_key not in st.session_state:
                            if st.button("🔄 Generate", key=f"gen_{idx}", use_container_width=True):
                                with st.spinner("Wait..."):
                                    jiga = p.get("jiga")
                                    # 폴리곤 좌표 추출 (위반 면적 산출용)
                                    poly_coords = None
                                    geom = feat.get("geometry")
                                    if geom and geom.get("type") == "Polygon":
                                        poly_coords = geom["coordinates"][0]
                                    elif geom and geom.get("type") == "MultiPolygon":
                                        poly_coords = geom["coordinates"][0][0]
                                    st.session_state[docx_key] = generate_report_docx(clon, clat, pnu, jibun, jc, jd, ns, jiga, poly_coords)
                                    st.rerun()
                        else:
                            st.download_button(
                                label="💾 Download",
                                data=st.session_state[docx_key],
                                file_name=f"report_{pnu}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"docx_{idx}",
                                use_container_width=True
                            )
                    else:
                        st.button("📝 Word", disabled=True, key=f"docx_disabled_{idx}", use_container_width=True)
    else:
        st.info("Click map → Detect.")

    st.divider()
    st.subheader("🤖 Task Runner")
    if st.button("Execute Task", type="primary"):
        st.code("python report_bot.py", language="bash")

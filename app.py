import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# 1. 페이지 설정
st.set_page_config(
    page_title="COREBUILD 클라우드 온습도", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
/* 🚀 1. 스트림릿 클라우드 강제 주입 아이콘 완벽 철거 (오른쪽 아래 빨간배, 노란 로고) */
/* 클라우드가 몰래 심어두는 고유 뱃지 클래스명과 iframe을 통째로 날려버립니다. */
[data-testid="stToolbar"], 
[data-testid="stStatusWidget"], 
footer,
.stAppDeployButton,
[class^="viewerBadge_"], 
iframe[title="Streamlit cloud badge"] {
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* 🚀 2. 하얀색으로 숨어버린 메뉴 열기(>) 버튼 강제 발굴 및 '빨간색(Red)' 도색 */
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}

/* stroke(테두리 선)와 fill(채우기) 모두 빨간색으로 강제하여 라이트/다크 모드 상관없이 무조건 보이게 함 */
[data-testid="collapsedControl"] button,
[data-testid="collapsedControl"] svg,
[data-testid="collapsedControl"] path {
    color: red !important;
    fill: red !important;
    stroke: red !important;
}

/* 🚀 3. 보이지 않는 헤더 막이 버튼 클릭을 방해하지 못하도록 투과 처리 */
header[data-testid="stHeader"] {
    background: transparent !important;
    pointer-events: none !important; 
}
[data-testid="collapsedControl"] {
    pointer-events: auto !important; 
}

/* ✅ 4. 부장님 디테일 설정값 절대 사수 */
div[data-testid="stExpander"] label p { font-size: 13px !important; }
.stCheckbox label p { font-size: 13px !important; }
.stCheckbox:first-child label p { font-weight: bold; color: #FFD700; }

@media (max-width: 768px) {
    h1 { 
        font-size: 22px !important; 
        padding-top: 1rem !important; 
    }
    h3 {
        font-size: 12px !important; 
    }
}
</style>
""", unsafe_allow_html=True)

st.title("🌡️ COREBUILD 실시간 온습도 현황")
st.markdown("---") 

@st.cache_data(ttl=600) 
def load_data():
    url = 'https://raw.githubusercontent.com/DforceJ/Saveris-Data-Collector/main/Saveris_Data.csv' 
    df = pd.read_csv(url)
    df['측정시간'] = pd.to_datetime(df['측정시간'], utc=True).dt.tz_convert('Asia/Seoul').dt.tz_localize(None)
    return df

try:
    df = load_data()
    COL_TIME, COL_DEVICE, COL_TEMP, COL_HUMI = '측정시간', '장비명', '℃', '%rF'

    device_list = sorted(df[COL_DEVICE].unique())
    years = sorted(df[COL_TIME].dt.year.unique())
    months = sorted(df[COL_TIME].dt.month.unique())
    days = sorted(df[COL_TIME].dt.day.unique())
    hours = sorted(df[COL_TIME].dt.hour.unique())

    if 'initialized' not in st.session_state:
        st.session_state.m_dev, st.session_state.m_y, st.session_state.m_m, st.session_state.m_d, st.session_state.m_h = True, True, True, True, True
        for d in device_list: st.session_state[f"dev_{d}"] = True
        for y in years: st.session_state[f"y_{y}"] = True
        for m in months: st.session_state[f"m_{m}"] = True
        for d in days: st.session_state[f"d_{d}"] = True
        for h in hours: st.session_state[f"h_{h}"] = True
        st.session_state.initialized = True

    def toggle_all(key_prefix, target_list, master_key):
        for item in target_list: st.session_state[f"{key_prefix}_{item}"] = st.session_state[master_key]

    st.sidebar.header("🔍 데이터 필터")
    selected_devices = []
    with st.sidebar.expander("✅ 측정 위치", expanded=True):
        st.checkbox("전체 선택/해제", key="m_dev", on_change=toggle_all, args=("dev", device_list, "m_dev"))
        for d in device_list:
            if st.checkbox(d, key=f"dev_{d}"): selected_devices.append(d)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 측정 일자 및 시간")
    
    def render_filter(label, item_list, key_p):
        sel = []
        with st.sidebar.expander(label):
            m_key = f"m_{key_p}"
            st.checkbox(f"{label} 전체", key=m_key, on_change=toggle_all, args=(key_p, item_list, m_key))
            for item in item_list:
                disp = f"{item}년" if key_p=='y' else f"{item}월" if key_p=='m' else f"{item}일" if key_p=='d' else f"{item}시"
                if st.checkbox(disp, key=f"{key_p}_{item}"): sel.append(item)
        return sel

    s_y = render_filter("년도", years, "y")
    s_m = render_filter("월", months, "m")
    s_d = render_filter("일", days, "d")
    s_h = render_filter("시간", hours, "h")

    if not selected_devices or not s_y or not s_m or not s_d or not s_h:
        st.warning("👈 데이터 필터에서 항목을 선택해 주세요.")
        st.stop()

    filtered_df = df[(df[COL_DEVICE].isin(selected_devices)) & (df[COL_TIME].dt.year.isin(s_y)) & (df[COL_TIME].dt.month.isin(s_m)) & (df[COL_TIME].dt.day.isin(s_d)) & (df[COL_TIME].dt.hour.isin(s_h))]
    plot_df = filtered_df.groupby(COL_TIME, as_index=False)[[COL_TEMP, COL_HUMI]].mean() if len(selected_devices) == len(device_list) else filtered_df.copy()
    plot_df[COL_DEVICE] = '전체 평균' if len(selected_devices) == len(device_list) else plot_df[COL_DEVICE]

    if plot_df.empty:
        st.warning("해당 조건에 맞는 데이터가 없습니다.")
        st.stop()

    st.markdown("### ⏱️ 측정 일자 및 시간 범위 정밀 조절")
    min_t = plot_df[COL_TIME].min().to_pydatetime()
    max_t = plot_df[COL_TIME].max().to_pydatetime()
    
    if min_t != max_t:
        col_slider, _ = st.columns([1, 4]) 
        with col_slider:
            sel_time = st.slider(
                "기간 조절", 
                min_value=min_t, 
                max_value=max_t, 
                value=(min_t, max_t), 
                format="MM/DD HH:mm", 
                step=timedelta(hours=1), 
                label_visibility="collapsed"
            )
        plot_df = plot_df[(plot_df[COL_TIME] >= sel_time[0]) & (plot_df[COL_TIME] <= sel_time[1])]

    display_count = 10 
    step_lbl = max(1, len(plot_df) // display_count)
    plot_df['T_L'] = [str(round(v, 1)) if i % step_lbl == 0 else "" for i, v in enumerate(plot_df[COL_TEMP])]
    plot_df['H_L'] = [str(round(v, 1)) if i % step_lbl == 0 else "" for i, v in enumerate(plot_df[COL_HUMI])]
    x_fmt = "%m월 %d일" if len(plot_df[COL_TIME].dt.date.unique()) > 1 else "%H시"

    col1, col2 = st.columns(2)

    with col1:
        fig_t = px.line(plot_df, x=COL_TIME, y=COL_TEMP, color=COL_DEVICE, text='T_L', 
                        markers=True, title="📈 실시간 온도 현황", line_shape='spline')
        fig_t.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="상한(30℃)")
        fig_t.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="하한(20℃)")
        fig_t.update_traces(textposition="top center", textfont_size=15, line_width=2, marker_size=10)
        fig_t.update_layout(yaxis=dict(range=[18, 32], dtick=2, autorange=False, fixedrange=True, title="온도 (℃)"),
                            xaxis=dict(tickformat=x_fmt, title="측정시간"))
        st.plotly_chart(fig_t, use_container_width=True)

    with col2:
        fig_h = px.line(plot_df, x=COL_TIME, y=COL_HUMI, color=COL_DEVICE, text='H_L', 
                        markers=True, title="💧 실시간 습도 현황", line_shape='spline')
        fig_h.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="상한(60%)")
        fig_h.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="하한(30%)")
        fig_h.update_traces(textposition="top center", textfont_size=15, line_width=2, marker_size=10)
        fig_h.update_layout(yaxis=dict(range=[25, 65], dtick=5, autorange=False, fixedrange=True, title="습도 (%rF)"),
                            xaxis=dict(tickformat=x_fmt, title="측정시간"))
        st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("---")
    with st.expander("🔍 클라우드 서버 원본 데이터 상세 보기"):
        st.dataframe(filtered_df)

    with st.expander("ℹ️ 데이터 측정 기준"):
        st.markdown("""
        **🌡️ 코어빌드 온습도 데이터 자동 수집 시스템 데이터 측정 기준**
        
        코어빌드 회로/기구자재 창고 및 생산라인, IQC, OQC 온습도 데이터를 매 시간 자동으로 수집하여 저장하는 시스템입니다.

        **⚙️ 작동 방식**
        1. **수집 주기:** 매 시간마다 GitHub Actions 로봇이 자동으로 실행됩니다.
        2. **실행 스크립트:** `saveris_auto_collector.py` (파이썬)
        3. **결과 저장소:** GitHub 클라우드의 `Saveris_Data.csv` 파일에 데이터가 누적됩니다.
        4. **실행 감시 (Health Check):** GitHub Actions의 서버 상태에 따른 실행 지연(로봇 지각)을 감시하기 위해 **외부 모니터링 알람**이 설정되어 있습니다.

        **📊 장비별 수집 조건 (필터링 로직)**
        1. **A, B 장비 (회로자재 창고):** 24시간 상시 수집
        2. **C, D, E, F, G 장비:** 휴일을 제외한 근무 시간 (09:00 ~ 17:00) 데이터만 수집

        **🖥️ 대시보드 연동**
        수집 로봇이 적재한 CSV 원본 데이터는 **코어빌드 자체 클라우드 관제 대시보드(Streamlit)** 서버와 실시간으로 연동되어 있습니다.
        """)

    st.markdown(
        f"""
        <div style='text-align: right; color: #888888; font-size: 15px; margin-top: 30px; margin-bottom: 20px;'>
            🛠️ <b>Developed by:</b> Corebuild 조동진 부장 <br>
            📧 <b>관리자 문의:</b> <a href='mailto:djcho@corebuild.co.kr' style='color: #888888; text-decoration: none;'>djcho@corebuild.co.kr</a>
        </div>
        """, 
        unsafe_allow_html=True
    )

except Exception as e:
    st.error(f"🚨 오류 발생: {e}")
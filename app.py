import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# 1. 페이지 설정
st.set_page_config(page_title="COREBUILD 클라우드 온습도", layout="wide")

st.markdown("""
<style>
/* 1. 우측 상단 툴바(Deploy, 세로점3개 등) 및 하단 종이배 완벽 제거 */
[data-testid="stToolbar"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
    display: none !important;
}

/* 2. ✅ 좌측 상단 화살표(>) 버튼 - 위치와 가시성 절대 고정 */
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    position: fixed !important;
    top: 0px !important;  /* 최상단 */
    left: 10px !important; /* 왼쪽 살짝 띄움 */
    z-index: 9999999 !important; /* 모든 것보다 위에 */
    background-color: transparent !important;
    width: 50px !important;
    height: 50px !important;
}

/* 3. ✅ 부장님이 직접 고르신 '빨간색(Red)' 아이콘 강제 적용 */
[data-testid="collapsedControl"] svg {
    fill: red !important;
    color: red !important;
    width: 35px !important; /* 모바일에서도 잘 보이게 조금 키움 */
    height: 35px !important;
}

/* 4. 버튼을 가리고 있던 헤더의 배경만 지우고 높이를 확보함 */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0px !important; /* 헤더가 본문을 가리지 않게 함 */
}

/* 기존 부장님 설정값 유지 */
div[data-testid="stExpander"] label p { font-size: 13px !important; }
.stCheckbox label p { font-size: 13px !important; }
.stCheckbox:first-child label p { font-weight: bold; color: #FFD700; }

@media (max-width: 768px) {
    h1 { 
        font-size: 22px !important; 
        padding-top: 3rem !important; /* 빨간 화살표와 겹치지 않게 본문 더 내림 */
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

    # ==========================================
    # 💡 [요청 반영] 슬라이더 크기를 1/5 로 축소
    # ==========================================
    st.markdown("### ⏱️ 측정 일자 및 시간 범위 정밀 조절")
    min_t = plot_df[COL_TIME].min().to_pydatetime()
    max_t = plot_df[COL_TIME].max().to_pydatetime()
    
    if min_t != max_t:
        # 전체 가로폭을 1:4 비율로 쪼개서, 왼쪽 1/5 영역에만 슬라이더를 그립니다.
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

    step_lbl = max(1, len(plot_df) // 12)
    plot_df['T_L'] = [str(round(v, 1)) if i % step_lbl == 0 else "" for i, v in enumerate(plot_df[COL_TEMP])]
    plot_df['H_L'] = [str(round(v, 1)) if i % step_lbl == 0 else "" for i, v in enumerate(plot_df[COL_HUMI])]
    x_fmt = "%m월 %d일" if len(plot_df[COL_TIME].dt.date.unique()) > 1 else "%H시"

    # ==========================================
    # 📊 그래프 시각화 
    # ==========================================
    col1, col2 = st.columns(2)

    with col1:
        fig_t = px.line(plot_df, x=COL_TIME, y=COL_TEMP, color=COL_DEVICE, text='T_L', 
                        markers=True, title="📈 실시간 온도 현황", line_shape='spline')
        fig_t.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="상한(30℃)")
        fig_t.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="하한(20℃)")
        
        fig_t.update_traces(textposition="top center", textfont_size=15, line_width=2, marker_size=10)
        
        fig_t.update_layout(
            yaxis=dict(range=[18, 32], dtick=2, autorange=False, fixedrange=True, title="온도 (℃)"),
            xaxis=dict(tickformat=x_fmt, title="측정시간")
        )
        fig_t.update_xaxes(rangeslider=dict(visible=False)) 
        
        st.plotly_chart(fig_t, use_container_width=True)

    with col2:
        fig_h = px.line(plot_df, x=COL_TIME, y=COL_HUMI, color=COL_DEVICE, text='H_L', 
                        markers=True, title="💧 실시간 습도 현황", line_shape='spline')
        fig_h.add_hline(y=60, line_dash="dash", line_color="red", annotation_text="상한(60%)")
        fig_h.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="하한(30%)")
        
        fig_h.update_traces(textposition="top center", textfont_size=15, line_width=2, marker_size=10)
        
        fig_h.update_layout(
            yaxis=dict(range=[25, 65], dtick=5, autorange=False, fixedrange=True, title="습도 (%rF)"),
            xaxis=dict(tickformat=x_fmt, title="측정시간")
        )
        fig_h.update_xaxes(rangeslider=dict(visible=False))

        st.plotly_chart(fig_h, use_container_width=True)

    st.markdown("---")
    with st.expander("🔍 클라우드 서버 원본 데이터 상세 보기"):
        st.dataframe(filtered_df)

    # =======================================================
    # 💡 [여기에 새로 추가!] 데이터 측정 기준 안내 토글 (Expander)
    # =======================================================
    with st.expander("ℹ️ 데이터 측정 기준"):
        st.markdown("""
        **🌡️ 코어빌드 온습도 데이터 자동 수집 시스템 데이터 측정 기준**
        
        코어빌드 회로/기구자재 창고 및 생산라인, IQC, OQC 온습도 데이터를 매 시간 자동으로 수집하여 저장하는 시스템입니다.

        **⚙️ 작동 방식**
        1. **수집 주기:** 매 시간마다 GitHub Actions 로봇이 자동으로 실행됩니다.
        2. **실행 스크립트:** `saveris_auto_collector.py` (파이썬)
        3. **결과 저장소:** GitHub 클라우드의 `Saveris_Data.csv` 파일에 데이터가 누적됩니다.
       
        **📊 장비별 수집 조건 (필터링 로직)**
        1. **A, B 장비 (회로자재 창고):** 24시간 상시 수집
        2. **C, D, E, F, G 장비:** 휴일을 제외한 근무 시간 (09:00 ~ 17:00) 데이터만 수집

        **🖥️ 대시보드 연동**
        수집 로봇이 클라우드에 적재한 CSV 원본 데이터는, 현재 배포된 **코어빌드 자체 클라우드 관제 대시보드(Streamlit)** 서버와 실시간으로 연동되어 있습니다. 내부 동적 시각화 엔진(Plotly)을 거쳐 24시간 언제 어디서든 PC와 스마트폰으로 최신 온습도 현황을 즉시 관제할 수 있습니다.
        """)

    # ==========================================
    # 💡 [요청 반영] 우측 하단 만든 사람 및 문의처 표시
    # ==========================================
    st.markdown(
        """
        <div style='text-align: right; color: #888888; font-size: 15px; margin-top: 30px; margin-bottom: 20px;'>
            🛠️ <b>Developed by:</b> Corebuild 조동진 부장 <br>
            📧 <b>관리자 문의:</b> <a href='mailto:admin@corebuild.co.kr' style='color: #888888; text-decoration: none;'>djcho@corebuild.co.kr</a>
        </div>
        """, 
        unsafe_allow_html=True
    )

except Exception as e:
    st.error(f"🚨 오류 발생: {e}")

"""
장기국고채 마켓 데일리 — Streamlit 웹 앱
실행: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import tempfile
from datetime import datetime
from bond_engine import (
    load_all_data, run_all_questions, format_report,
    natural_language_query, setup_korean_font,
    ALL_BOND_NAMES, INVESTOR_SHORT, INVESTORS,
    q3_box_position, q4_moving_averages, q8_volume_vs_avg,
    q11_spread_box, level_text, position_in_box,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  페이지 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.set_page_config(
    page_title="장기국고채 마켓 데일리",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 한글 폰트 설정
FONT_OK = setup_korean_font()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("""
<style>
  .main-header { background: linear-gradient(135deg, #1a3a6b, #2563a8); color: white;
    padding: 20px 28px; border-radius: 10px; margin-bottom: 20px; }
  .main-header h1 { font-size: 24px; margin: 0; }
  .main-header p { font-size: 13px; opacity: 0.85; margin: 4px 0 0 0; }
  .q-card { background: #f8f9fc; border: 1px solid #dce3ee; border-radius: 10px;
    padding: 16px; margin-bottom: 12px; }
  .q-num { background: #1a3a6b; color: white; border-radius: 50%; width: 28px; height: 28px;
    display: inline-flex; align-items: center; justify-content: center; font-size: 13px;
    font-weight: 700; margin-right: 8px; }
  .metric-box { background: white; border: 1px solid #e0e5ee; border-radius: 8px;
    padding: 12px; text-align: center; }
  .metric-label { font-size: 11px; color: #888; }
  .metric-value { font-size: 20px; font-weight: 700; color: #1a3a6b; }
  .badge-red { background: #fde8e8; color: #c0392b; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .badge-blue { background: #e8f0fe; color: #1a56d6; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .badge-green { background: #e8f5e9; color: #1a7a3c; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
  .badge-orange { background: #fff3e0; color: #d07a00; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  사이드바
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with st.sidebar:
    st.title("⚙️ 설정")

    uploaded = st.file_uploader("📂 엑셀 데이터 업로드", type=['xlsx','xls'])

    st.divider()
    target_bond = st.selectbox("📌 기준 종목", ALL_BOND_NAMES, index=1)  # 25-7 기본

    st.divider()
    st.subheader("Q6 대차잔고 설정")
    q6_ref_day = st.number_input("기준 영업일 (n일차)", min_value=1, max_value=20, value=7)
    q6_months = st.number_input("조회 개월수", min_value=1, max_value=24, value=6)

    st.divider()
    st.subheader("Q12 잔고변화 종목")
    q12_targets = st.multiselect("종목 선택", ALL_BOND_NAMES, default=['26-2','25-7','25-2','24-11'])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인 컨텐츠
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

st.markdown("""
<div class="main-header">
  <h1>📊 장기국고채 마켓 데일리</h1>
  <p>엑셀 파일을 업로드하면 핵심질문 12개가 자동 분석됩니다</p>
</div>
""", unsafe_allow_html=True)

if uploaded is None:
    st.info("👈 왼쪽 사이드바에서 엑셀 파일을 업로드해 주세요.")
    st.stop()

# ── 데이터 로딩 ──
@st.cache_data(show_spinner="데이터 로딩 중...")
def cached_load(file_bytes):
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    bonds, rates, issuance = load_all_data(tmp_path)
    os.unlink(tmp_path)
    return bonds, rates, issuance

bonds, rates, issuance = cached_load(uploaded.getvalue())

# 기준일
ref_df = bonds.get(target_bond)
if ref_df is None or ref_df.empty:
    st.error(f"종목 '{target_bond}' 데이터가 없습니다.")
    st.stop()

base_date = ref_df.iloc[-1]['일자'].strftime('%Y년 %m월 %d일')
st.caption(f"📅 기준일: **{base_date}**  |  종목: **{target_bond}**")


# ── 12개 질문 분석 ──
with st.spinner("🔍 핵심질문 12개 분석 중..."):
    results = run_all_questions(bonds, rates, target_bond, q6_ref_day, q6_months, q12_targets)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭 구성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

tab1, tab2, tab3, tab4 = st.tabs(["📋 분석 결과", "📝 편집 가능 리포트", "📊 차트", "💬 추가 질문"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TAB 1: 분석 결과
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab1:

    # ── Q1 ──
    st.subheader("1️⃣ 전일대비 변동성 TOP10")
    q1 = results['Q1']
    if q1:
        df_q1 = pd.DataFrame(q1)[['종목','변수','전일값','당일값','변동']]
        st.dataframe(df_q1, use_container_width=True, hide_index=True)

    # ── Q2 ──
    st.subheader(f"2️⃣ 공격적 매수 투자자 — {target_bond}")
    q2 = results['Q2']
    if q2.get('순위'):
        df_q2 = pd.DataFrame(q2['순위'])
        df_q2.columns = ['투자자','매수금액(억)','평균수익률(%)']
        st.dataframe(df_q2, use_container_width=True, hide_index=True)

    # ── Q3 ──
    st.subheader(f"3️⃣ 20일 박스권 위치 — {target_bond}")
    q3 = results['Q3']
    if q3:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재 금리", f"{q3['현재금리']:.3f}%")
        c2.metric("박스권 하단", f"{q3['박스권하단']:.3f}%")
        c3.metric("박스권 상단", f"{q3['박스권상단']:.3f}%")
        c4.metric("위치", f"{q3['레벨']} {q3['현재위치']:.1f}%")
        st.progress(min(q3['현재위치'] / 100, 1.0))

    # ── Q4 ──
    st.subheader(f"4️⃣ 이동평균금리 — {target_bond}")
    q4 = results['Q4']
    if q4:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재", f"{q4['현재금리']:.3f}%")
        c2.metric("MA5 (단기)", f"{q4['MA5']:.3f}%", f"현재 {q4['단기비교']}")
        c3.metric("MA20 (중기)", f"{q4['MA20']:.3f}%", f"현재 {q4['중기비교']}")
        c4.metric("MA60 (장기)", f"{q4['MA60']:.3f}%", f"현재 {q4['장기비교']}")

    # ── Q5 ──
    st.subheader(f"5️⃣ 박스권 상·하단 매수 주체 — {target_bond}")
    q5 = results['Q5']
    if q5:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**상단** ({q5.get('박스권상단',0):.3f}%)")
            st.markdown(f"주요 매수: **{q5.get('상단매수주체','-')}** / 순매수 {q5.get('상단순매수억',0):+,.0f}억")
        with c2:
            st.markdown(f"**하단** ({q5.get('박스권하단',0):.3f}%)")
            st.markdown(f"주요 매수: **{q5.get('하단매수주체','-')}** / 순매수 {q5.get('하단순매수억',0):+,.0f}억")

    # ── Q6 ──
    st.subheader(f"6️⃣ 대차잔고비율 월별 추이 — {target_bond}")
    q6 = results['Q6']
    if q6.get('추이'):
        st.dataframe(pd.DataFrame(q6['추이']), use_container_width=True, hide_index=True)

    # ── Q7 ──
    st.subheader(f"7️⃣ 대차잔고 비율·속도 박스권 — {target_bond}")
    q7 = results['Q7']
    if q7:
        c1, c2 = st.columns(2)
        c1.metric("대차잔고비율", f"{q7.get('현재비율',0):.3f}%",
                  f"박스 {q7.get('비율위치',0):.1f}%")
        c2.metric("순증감속도", f"{q7.get('현재속도_억',0):+,.1f}억",
                  f"박스 {q7.get('속도위치',0):.1f}%")

    # ── Q8 ──
    st.subheader(f"8️⃣ 당일 거래량 vs 20일 평균 — {target_bond}")
    q8 = results['Q8']
    if q8:
        c1, c2, c3 = st.columns(3)
        c1.metric("당일 거래량", f"{q8.get('당일거래량_억',0):,.0f}억")
        c2.metric("20일 평균", f"{q8.get('20일평균_억',0):,.0f}억")
        c3.metric("평균 대비", f"{q8.get('비율',0):.1f}%")

    # ── Q9 ──
    st.subheader(f"9️⃣ 거래량 × 변동폭 4분면 — {target_bond}")
    q9 = results['Q9']
    if q9:
        st.info(f"📌 {q9.get('4분면','')}")
        c1, c2 = st.columns(2)
        c1.metric("거래량", q9.get('거래량증감',''), f"{q9.get('당일거래량_억',0):,.0f}억")
        c2.metric("변동폭", q9.get('변동폭증감',''), f"{q9.get('당일변동폭bp',0):.1f}bp")

    # ── Q10 ──
    st.subheader("🔟 국고30년 원금 발행증감 (최근 6개월)")
    q10 = results['Q10']
    if q10.get('추이'):
        st.dataframe(pd.DataFrame(q10['추이']), use_container_width=True, hide_index=True)

    # ── Q11 ──
    st.subheader(f"1️⃣1️⃣ 스프레드 박스권 위치 — {target_bond}")
    q11 = results['Q11']
    if q11.get('스프레드'):
        df_q11 = pd.DataFrame([{
            '비교대상': s['비교대상'],
            '스프레드(bp)': s['스프레드bp'],
            '박스하단(bp)': s['박스하단bp'],
            '박스상단(bp)': s['박스상단bp'],
            '위치(%)': s['위치'],
            '레벨': s['레벨'],
        } for s in q11['스프레드']])
        st.dataframe(df_q11, use_container_width=True, hide_index=True)

    # ── Q12 ──
    st.subheader("1️⃣2️⃣ 투자자별 잔고 변화")
    q12 = results['Q12']
    if q12:
        cols = st.columns(len(q12))
        for i, bd in enumerate(q12):
            with cols[i]:
                st.markdown(f"**{bd['종목']}**")
                for c in bd['투자자별']:
                    v = c['잔고변화_억']
                    color = '🔴' if v > 0 else '🔵' if v < 0 else '⚪'
                    st.markdown(f"{color} {c['투자자']}: {v:+,.2f}억")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TAB 2: 편집 가능 리포트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab2:
    st.subheader("📝 편집 가능 텍스트 리포트")
    st.caption("자동 생성된 내용을 직접 수정한 뒤 복사하여 사용하세요.")

    default_text = format_report(results, base_date)
    edited = st.text_area("리포트 편집", value=default_text, height=700, key="report_editor")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 클립보드 복사용 텍스트 보기"):
            st.code(edited, language=None)
    with col2:
        st.download_button(
            "💾 TXT 다운로드",
            data=edited.encode('utf-8'),
            file_name=f"마켓데일리_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TAB 3: 차트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab3:

    # ── Q4 차트 ──
    st.subheader(f"📊 Q4. 이동평균금리 차트 — {target_bond}")
    q4 = results['Q4']
    if q4 and 'chart_df' in q4:
        cd = q4['chart_df']
        rate_col = '민평4사 수익률(산출일) 당일'

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(cd['일자'], cd[rate_col], color='#1f77b4', linewidth=1.5,
                label='민평수익률' if FONT_OK else 'Yield', zorder=5)
        ax.plot(cd['일자'], cd['MA5'],  color='#ff7f0e', linewidth=1.5, linestyle='--',
                label='MA5 (단기)' if FONT_OK else 'MA5 (5D)')
        ax.plot(cd['일자'], cd['MA20'], color='#2ca02c', linewidth=1.8, linestyle='-.',
                label='MA20 (중기)' if FONT_OK else 'MA20 (20D)')
        ax.plot(cd['일자'], cd['MA60'], color='#d62728', linewidth=2.0, linestyle=':',
                label='MA60 (장기)' if FONT_OK else 'MA60 (60D)')

        cur = q4['현재금리']
        ax.axhline(cur, color='navy', linewidth=0.9, alpha=0.5)
        lbl = f'현재 {cur:.3f}%' if FONT_OK else f'Now {cur:.3f}%'
        ax.text(cd['일자'].iloc[-1], cur, f'  {lbl}', va='center', fontsize=9, color='navy')

        title = f'{target_bond} 이동평균금리' if FONT_OK else f'KTB 30Y ({target_bond}) Moving Average'
        ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
        ylabel = '수익률 (%)' if FONT_OK else 'Yield (%)'
        ax.set_ylabel(ylabel)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%y.%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.tick_params(axis='x', rotation=30)
        ax.legend(loc='upper right', fontsize=9, framealpha=0.85)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    # ── Q11 차트 ──
    st.subheader(f"📊 Q11. 스프레드 박스권 위치 — {target_bond}")
    q11 = results['Q11']
    if q11.get('스프레드'):
        spreads = q11['스프레드']

        # 바 차트
        fig1, ax1 = plt.subplots(figsize=(10, 4.5))
        labels = [s['비교대상'] for s in spreads]
        positions = [s['위치'] for s in spreads]
        cur_spreads = [s['스프레드bp'] for s in spreads]
        colors = ['#1a56d6' if p <= 25 else '#2ca02c' if p <= 50 else '#ff7f0e' if p <= 75 else '#d62728' for p in positions]

        bars = ax1.bar(labels, positions, color=colors, edgecolor='white', linewidth=1.5, zorder=3)
        for bar, pos, sp in zip(bars, positions, cur_spreads):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                     f'{pos:.1f}%\n({sp:+.1f}bp)', ha='center', va='bottom', fontsize=9, fontweight='bold')
        ul = '상단 75%' if FONT_OK else 'Upper 75%'
        ml = '중간 50%' if FONT_OK else 'Mid 50%'
        ll = '하단 25%' if FONT_OK else 'Lower 25%'
        ax1.axhline(75, color='#d62728', linestyle='--', linewidth=1, alpha=0.7, label=ul)
        ax1.axhline(50, color='gray',    linestyle=':',  linewidth=1, alpha=0.6, label=ml)
        ax1.axhline(25, color='#1a56d6', linestyle='--', linewidth=1, alpha=0.7, label=ll)
        ax1.set_ylim(0, 115)
        title = f'{target_bond} 스프레드 박스권 위치 (20일)' if FONT_OK else f'KTB 30Y ({target_bond}) Spread Box [20-day]'
        ax1.set_title(title, fontsize=12, fontweight='bold')
        ylabel = '박스권 위치 (%)' if FONT_OK else 'Box Position (%)'
        ax1.set_ylabel(ylabel)
        ax1.legend(loc='upper right', fontsize=8)
        ax1.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
        fig1.tight_layout()
        st.pyplot(fig1)
        plt.close(fig1)

        # 시계열
        n = len(spreads)
        cols_n = min(3, n)
        rows_n = (n + cols_n - 1) // cols_n
        fig2, axes = plt.subplots(rows_n, cols_n, figsize=(12, 3.5 * rows_n))
        if n == 1:
            axes = np.array([[axes]])
        elif rows_n == 1:
            axes = np.array([axes])

        for i, sd in enumerate(spreads):
            row, col = divmod(i, cols_n)
            ax = axes[row][col] if rows_n > 1 else axes[0][col]
            series = sd['series'] * 100
            ax.plot(series.index, series.values, color='#1f77b4', linewidth=1.3)
            ax.axhline(sd['박스상단bp'], color='#d62728', linestyle='--', linewidth=1, alpha=0.7)
            ax.axhline(sd['박스하단bp'], color='#1a56d6', linestyle='--', linewidth=1, alpha=0.7)
            cur_sp = sd['스프레드bp']
            ax.axhline(cur_sp, color='darkgreen', linestyle='-', linewidth=0.8, alpha=0.5)
            ax.set_title(sd['비교대상'], fontsize=10, fontweight='bold')
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%y.%m'))
            ax.tick_params(axis='x', rotation=30, labelsize=7)
            ax.grid(linestyle='--', alpha=0.3)

        for i in range(n, rows_n * cols_n):
            row, col = divmod(i, cols_n)
            (axes[row][col] if rows_n > 1 else axes[0][col]).set_visible(False)

        fig2.tight_layout()
        st.pyplot(fig2)
        plt.close(fig2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TAB 4: 추가 질문 (자연어 Q&A)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab4:
    st.subheader("💬 데이터 기반 추가 질문")
    st.caption("데이터 범위 내에서 자연어로 질문할 수 있습니다.")

    st.markdown("""
    **사용 가능한 키워드 예시:**
    - `25-7 금리` → 종목 금리 현황
    - `26-2 거래량` → 거래량 상세
    - `25-7 잔고` → 투자자별 잔고
    - `25-2 대차` → 대차잔고 현황
    - `스프레드` → 스프레드 박스권
    - `25-7 박스권` → 박스권 위치
    - `26-2 vs 25-7 비교` → 종목 비교
    - `외국인 25-7 거래량` → 특정 투자자 거래량
    """)

    # 대화 기록
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # 입력
    user_q = st.chat_input("질문을 입력하세요 (예: 25-7 외국인 거래량은?)")

    if user_q:
        answer = natural_language_query(user_q, bonds, rates, results)
        st.session_state.chat_history.append(('user', user_q))
        st.session_state.chat_history.append(('assistant', answer))

    # 대화 출력
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            if role == 'assistant':
                st.text(msg)
            else:
                st.markdown(msg)

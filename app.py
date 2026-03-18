"""
장기국고채 마켓 데일리 — Streamlit App
엑셀 업로드 → 데이터 자동 감지 → 분석 결과 표시
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import warnings
warnings.filterwarnings('ignore')

from bond_engine import (
    load_all_data, run_all_questions, format_report,
    natural_language_query, setup_korean_font,
    BOND_SHEETS_ALL, PRINCIPAL_SHEETS_ALL, SHORT_NAMES,
    q11_spread_box, q4_moving_averages,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  페이지 기본 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="장기국고채 마켓 데일리",
    page_icon="📊",
    layout="wide",
)

setup_korean_font()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  세션 상태 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_file" not in st.session_state:
    st.session_state.last_file = None
if "bonds" not in st.session_state:
    st.session_state.bonds = None
if "rates" not in st.session_state:
    st.session_state.rates = None
if "available_bonds" not in st.session_state:
    st.session_state.available_bonds = []
if "results" not in st.session_state:
    st.session_state.results = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  데이터 로딩 (캐시)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_data(show_spinner="엑셀 데이터 로딩 중...")
def cached_load(file_bytes):
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        bonds, rates, issuance = load_all_data(tmp_path)
    finally:
        os.unlink(tmp_path)
    return bonds, rates, issuance

def get_available_bonds(bonds):
    """업로드된 엑셀에 실제로 존재하는 종목 리스트 반환"""
    available = []
    all_short = [SHORT_NAMES[s] for s in BOND_SHEETS_ALL if s in SHORT_NAMES]
    for sname in all_short:
        if sname in bonds and len(bonds[sname]) > 0:
            available.append(sname)
    return available

def get_latest_date(bonds, available_bonds):
    """가장 최신 기준일 반환"""
    dates = []
    for b in available_bonds:
        df = bonds.get(b)
        if df is not None and len(df) > 0:
            dates.append(df.iloc[-1]['일자'])
    if dates:
        return max(dates).strftime('%Y-%m-%d')
    return '미상'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헤더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.title("📊 장기국고채 마켓 데일리")
st.caption("엑셀 데이터를 업로드하면 12개 핵심 질문에 자동 답변합니다")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  사이드바 — 파일 업로드 + 자동 감지 옵션
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.header("⚙️ 설정")

    uploaded = st.file_uploader(
        "채권 데이터 엑셀 (.xlsx)",
        type=["xlsx"],
        help="장기국고채 분석용 엑셀 파일을 업로드하세요"
    )

    # ── 파일 로딩 ──
    if uploaded is not None:
        file_id = uploaded.name + str(uploaded.size)
        if st.session_state.last_file != file_id:
            with st.spinner("데이터 분석 중..."):
                bonds, rates, _ = cached_load(uploaded.read())
                available = get_available_bonds(bonds)
                st.session_state.bonds = bonds
                st.session_state.rates = rates
                st.session_state.available_bonds = available
                st.session_state.last_file = file_id
                st.session_state.results = None  # 설정 변경 시 재계산
            st.success(f"✅ 종목 {len(available)}개 감지됨")

    bonds = st.session_state.bonds
    rates = st.session_state.rates
    available_bonds = st.session_state.available_bonds

    # ── 데이터가 있을 때만 옵션 표시 ──
    if bonds and available_bonds:
        st.divider()
        st.subheader("📌 분석 옵션")

        # 기준 종목 — 엑셀에 있는 것만 표시
        target_bond = st.selectbox(
            "기준 종목 (Q2~Q11)",
            options=available_bonds,
            index=min(1, len(available_bonds) - 1),  # 두 번째 항목을 기본값으로
            help="분석 기준이 될 종목을 선택하세요"
        )

        # Q6 설정
        st.markdown("**Q6. 대차잔고 월별 추이**")
        # 실제 데이터 기간으로 최대 개월수 제한
        df_target = bonds.get(target_bond)
        max_months = 12
        if df_target is not None and len(df_target) > 0:
            months_in_data = df_target['일자'].dt.to_period('M').nunique()
            max_months = min(12, months_in_data)

        q6_months = st.slider(
            "조회 개월수",
            min_value=1, max_value=max_months,
            value=min(6, max_months),
            help=f"데이터에 최대 {max_months}개월 존재"
        )
        q6_ref_day = st.number_input(
            "기준 영업일 (월 N번째 영업일)",
            min_value=1, max_value=23,
            value=7,
        )

        # Q12 설정 — 엑셀에 있는 종목만 체크박스로
        st.markdown("**Q12. 잔고 변화 대상 종목**")
        q12_targets = []
        # 30년 종목 우선, 50년 종목 후
        thirty_yr = [b for b in available_bonds if '원금' not in b and b in ['26-2','25-7','25-2','24-8','24-2','23-7']]
        fifty_yr = [b for b in available_bonds if '원금' not in b and b in ['24-11','22-12']]

        for b in thirty_yr[:4]:  # 최대 4개 기본 체크
            checked = st.checkbox(f"30년 {b}", value=True, key=f"q12_{b}")
            if checked:
                q12_targets.append(b)
        for b in fifty_yr:
            checked = st.checkbox(f"50년 {b}", value=False, key=f"q12_{b}")
            if checked:
                q12_targets.append(b)

        if not q12_targets:
            q12_targets = available_bonds[:2]

        st.divider()

        # ── 분석 실행 버튼 ──
        run_btn = st.button("🔍 분석 실행", type="primary", use_container_width=True)
        if run_btn or st.session_state.results is None:
            with st.spinner("12개 질문 분석 중..."):
                try:
                    results = run_all_questions(
                        bonds, rates,
                        target=target_bond,
                        q6_ref_day=q6_ref_day,
                        q6_months=q6_months,
                        q12_targets=q12_targets,
                    )
                    st.session_state.results = results
                except Exception as e:
                    st.error(f"분석 오류: {e}")
                    st.session_state.results = None

        # 기준일 표시
        latest = get_latest_date(bonds, available_bonds)
        st.caption(f"📅 기준일: {latest}")

    else:
        st.info("👆 엑셀 파일을 업로드하면\n분석 옵션이 나타납니다")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인 화면
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if st.session_state.results is None or bonds is None:
    # 업로드 전 안내 화면
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📥 1단계\n왼쪽 사이드바에서\n채권 데이터 엑셀 업로드")
    with col2:
        st.markdown("### ⚙️ 2단계\n기준 종목·기간 선택 후\n**분석 실행** 클릭")
    with col3:
        st.markdown("### 📊 3단계\n분석 결과, 차트,\n리포트 자동 생성")
    st.stop()

results = st.session_state.results
latest_date = get_latest_date(bonds, available_bonds)

# ── 4개 탭 ──
tab1, tab2, tab3, tab4 = st.tabs(["📋 분석결과", "✏️ 편집가능 리포트", "📈 차트", "💬 추가 질문"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭1: 분석결과
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab1:
    st.subheader(f"📋 분석 결과  |  기준일: {latest_date}  |  기준종목: {target_bond}")

    # Q1
    with st.expander("Q1. 전일대비 변동성 TOP10", expanded=True):
        q1 = results.get('Q1', [])
        if q1:
            df_q1 = pd.DataFrame(q1)[['종목','변수','전일값','당일값','변동']]
            df_q1.index = range(1, len(df_q1)+1)
            st.dataframe(df_q1, use_container_width=True)
        else:
            st.info("데이터 없음")

    col_a, col_b = st.columns(2)

    with col_a:
        # Q2
        with st.expander("Q2. 공격적 매수 투자자", expanded=True):
            q2 = results.get('Q2', {})
            buyers = q2.get('순위', [])
            if buyers:
                df_q2 = pd.DataFrame(buyers)
                df_q2.index = range(1, len(df_q2)+1)
                st.dataframe(df_q2, use_container_width=True)
            else:
                st.info("매수 거래 없음")

        # Q3
        with st.expander("Q3. 20일 박스권 위치", expanded=True):
            q3 = results.get('Q3', {})
            if q3:
                pos = q3.get('현재위치', 0)
                st.metric("현재 금리", f"{q3.get('현재금리',0):.3f}%")
                col_i, col_ii = st.columns(2)
                col_i.metric("박스 하단", f"{q3.get('박스권하단',0):.3f}%")
                col_ii.metric("박스 상단", f"{q3.get('박스권상단',0):.3f}%")
                st.progress(int(pos), text=f"{q3.get('레벨','-')} | {pos:.1f}%")
            else:
                st.info("데이터 부족 (최소 20일)")

        # Q5
        with st.expander("Q5. 박스권 상·하단 매수 주체", expanded=False):
            q5 = results.get('Q5', {})
            if q5:
                c1, c2 = st.columns(2)
                c1.metric("상단 매수 주체", q5.get('상단매수주체','-'),
                          f"{q5.get('상단순매수억',0):+,.0f}억")
                c2.metric("하단 매수 주체", q5.get('하단매수주체','-'),
                          f"{q5.get('하단순매수억',0):+,.0f}억")
            else:
                st.info("데이터 없음")

    with col_b:
        # Q4
        with st.expander("Q4. 이동평균 금리 위치", expanded=True):
            q4 = results.get('Q4', {})
            if q4:
                cur = q4.get('현재금리', 0)
                ma5 = q4.get('MA5', 0)
                ma20 = q4.get('MA20', 0)
                ma60 = q4.get('MA60', 0)
                st.metric("현재 금리", f"{cur:.3f}%")
                c1, c2, c3 = st.columns(3)
                c1.metric("MA5 (단기)", f"{ma5:.3f}%",
                          f"{'▲ 위' if cur > ma5 else '▼ 아래'}")
                c2.metric("MA20 (중기)", f"{ma20:.3f}%",
                          f"{'▲ 위' if cur > ma20 else '▼ 아래'}")
                c3.metric("MA60 (장기)", f"{ma60:.3f}%",
                          f"{'▲ 위' if cur > ma60 else '▼ 아래'}")
            else:
                st.info("데이터 부족 (최소 5일)")

        # Q6
        with st.expander("Q6. 대차잔고비율 월별 추이", expanded=True):
            q6 = results.get('Q6', {})
            trend = q6.get('추이', [])
            if trend:
                df_q6 = pd.DataFrame(trend)
                df_q6.columns = ['월', '날짜', '대차잔고비율(%)']
                st.dataframe(df_q6, use_container_width=True)
            else:
                st.info("대차 데이터 없음")

        # Q7
        with st.expander("Q7. 대차잔고 비율·속도 박스권", expanded=False):
            q7 = results.get('Q7', {})
            if q7.get('error'):
                st.warning(q7['error'])
            elif q7:
                c1, c2 = st.columns(2)
                rpos = q7.get('비율위치', 0)
                spos = q7.get('속도위치', 0)
                c1.metric("현재 비율", f"{q7.get('현재비율',0):.3f}%")
                c1.progress(int(rpos), text=f"비율 박스 위치: {rpos:.1f}%")
                c2.metric("증감 속도", f"{q7.get('현재속도_억',0):+.1f}억")
                c2.progress(int(spos), text=f"속도 박스 위치: {spos:.1f}%")
            else:
                st.info("데이터 없음")

    # Q8, Q9 나란히
    col_c, col_d = st.columns(2)
    with col_c:
        with st.expander("Q8. 당일 거래량 vs 20일 평균", expanded=False):
            q8 = results.get('Q8', {})
            if q8:
                ratio = q8.get('비율', 0)
                st.metric("당일 거래량", f"{q8.get('당일거래량_억',0):,.0f}억",
                          f"20일평균 {q8.get('20일평균_억',0):,.0f}억 대비 {ratio:.1f}%")
                st.progress(min(100, int(ratio)), text=f"{ratio:.1f}%")
            else:
                st.info("데이터 없음")

    with col_d:
        with st.expander("Q9. 거래량×변동폭 4분면", expanded=False):
            q9 = results.get('Q9', {})
            if q9:
                st.info(f"**{q9.get('4분면','-')}**")
                c1, c2 = st.columns(2)
                c1.metric("거래량", q9.get('거래량증감','-'))
                c2.metric("변동폭", q9.get('변동폭증감','-'))
            else:
                st.info("데이터 없음")

    # Q10, Q11, Q12
    with st.expander("Q10. 원금 발행증감 월별 추이", expanded=False):
        q10 = results.get('Q10', {})
        trend10 = q10.get('추이', [])
        if trend10:
            df_q10 = pd.DataFrame(trend10)
            df_q10.columns = ['월', '발행액(조)', '전월대비(조)']
            st.dataframe(df_q10, use_container_width=True)
        else:
            st.info("원금 데이터 없음")

    with st.expander("Q11. 스프레드 박스권 위치", expanded=False):
        q11 = results.get('Q11', {})
        spreads = q11.get('스프레드', [])
        if spreads:
            rows = [{
                '비교대상': s['비교대상'],
                '스프레드(bp)': f"{s['스프레드bp']:+.1f}",
                '박스하단': f"{s['박스하단bp']:+.1f}",
                '박스상단': f"{s['박스상단bp']:+.1f}",
                '레벨': s['레벨'],
                '위치(%)': f"{s['위치']:.1f}",
            } for s in spreads]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("스프레드 데이터 없음 (금리 시트 필요)")

    with st.expander("Q12. 투자자별 잔고 변화", expanded=False):
        q12 = results.get('Q12', [])
        if q12:
            for bond_data in q12:
                st.markdown(f"**{bond_data['종목']}**")
                df_12 = pd.DataFrame(bond_data['투자자별'])
                if not df_12.empty:
                    df_12.columns = ['투자자', '잔고변화(억)']
                    st.dataframe(df_12, use_container_width=True)
        else:
            st.info("잔고 데이터 없음")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭2: 편집 가능 리포트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab2:
    st.subheader("✏️ 편집 가능 리포트")
    st.caption("아래 텍스트를 직접 수정한 후 복사하거나 다운로드하세요")

    report_text = format_report(results, base_date=latest_date)

    edited = st.text_area(
        "리포트 (자유롭게 편집)",
        value=report_text,
        height=600,
        key="report_editor",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ 텍스트 파일로 다운로드",
            data=edited.encode('utf-8'),
            file_name=f"마켓데일리_{latest_date}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col2:
        if st.button("🔄 원본으로 초기화", use_container_width=True):
            st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭3: 차트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab3:
    st.subheader("📈 차트")

    # ── Q4 차트: 금리 + 이동평균 ──
    st.markdown(f"#### Q4. {target_bond} 금리 이동평균선")
    q4 = results.get('Q4', {})
    chart_df = q4.get('chart_df')

    if chart_df is not None and len(chart_df) > 0:
        fig, ax = plt.subplots(figsize=(12, 4))
        rate_col = '민평4사 수익률(산출일) 당일'
        x = range(len(chart_df))
        labels = chart_df['일자'].dt.strftime('%m/%d').tolist()

        ax.plot(x, chart_df[rate_col], color='#1f77b4', linewidth=1.5, label='Yield')
        ax.plot(x, chart_df['MA5'],  color='#ff7f0e', linewidth=1.2, linestyle='--', label='MA5 (5D)')
        ax.plot(x, chart_df['MA20'], color='#2ca02c', linewidth=1.2, linestyle='--', label='MA20 (20D)')
        ax.plot(x, chart_df['MA60'], color='#d62728', linewidth=1.2, linestyle='--', label='MA60 (60D)')

        # 마지막 값 표시
        last_idx = len(chart_df) - 1
        last_val = chart_df[rate_col].iloc[-1]
        ax.annotate(f'{last_val:.3f}%', xy=(last_idx, last_val),
                    xytext=(last_idx - 5, last_val + 0.003),
                    fontsize=8, color='#1f77b4')

        # x축 레이블 (20개만)
        tick_step = max(1, len(x) // 20)
        ax.set_xticks(x[::tick_step])
        ax.set_xticklabels(labels[::tick_step], rotation=45, fontsize=7)
        ax.set_ylabel('Yield (%)', fontsize=9)
        ax.set_title(f'KTB 30Y {target_bond} — Yield & Moving Averages', fontsize=10)
        ax.legend(fontsize=8, loc='upper left')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=130)
        buf.seek(0)
        st.image(buf, use_container_width=True)
        plt.close(fig)

        st.download_button("⬇️ Q4 차트 다운로드 (PNG)",
                           data=buf.getvalue(),
                           file_name=f"Q4_MA_{target_bond}_{latest_date}.png",
                           mime="image/png")
    else:
        st.info("이동평균 데이터가 부족합니다 (최소 5일)")

    st.divider()

    # ── Q11 차트: 스프레드 박스권 ──
    st.markdown(f"#### Q11. {target_bond} 스프레드 박스권 위치")
    q11 = results.get('Q11', {})
    spreads = q11.get('스프레드', [])

    if spreads:
        n = len(spreads)
        fig, axes = plt.subplots(1, n, figsize=(4 * n, 4), sharey=False)
        if n == 1:
            axes = [axes]

        colors = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd']

        for i, (s, ax) in enumerate(zip(spreads, axes)):
            series = s['series']
            lo = s['박스하단bp'] / 100
            hi = s['박스상단bp'] / 100
            cur = s['스프레드bp'] / 100
            x = range(len(series))
            labels = series.index.strftime('%m/%d').tolist()

            ax.plot(x, series.values, color=colors[i % len(colors)], linewidth=1.2, label='Spread')
            ax.axhline(lo, color='green',  linewidth=1, linestyle=':', label='Box Lo')
            ax.axhline(hi, color='red',    linewidth=1, linestyle=':', label='Box Hi')
            ax.axhline(cur, color='black', linewidth=0.8, linestyle='--')

            # 현재 위치 점 표시
            ax.scatter([len(series)-1], [series.iloc[-1]], color=colors[i % len(colors)], zorder=5, s=30)
            ax.annotate(f'{s["스프레드bp"]:+.1f}bp', xy=(len(series)-1, series.iloc[-1]),
                        xytext=(-20, 6), textcoords='offset points', fontsize=7)

            tick_step = max(1, len(x) // 8)
            ax.set_xticks(x[::tick_step])
            ax.set_xticklabels(labels[::tick_step], rotation=45, fontsize=6)
            ax.set_title(f'KTB30Y - {s["비교대상"]}\n{s["레벨"]} ({s["위치"]:.1f}%)', fontsize=8)
            ax.legend(fontsize=6, loc='upper left')
            ax.grid(True, alpha=0.3)

        plt.suptitle(f'Spread Box Position — {target_bond}', fontsize=10, y=1.02)
        plt.tight_layout()

        buf2 = io.BytesIO()
        fig.savefig(buf2, format='png', dpi=130, bbox_inches='tight')
        buf2.seek(0)
        st.image(buf2, use_container_width=True)
        plt.close(fig)

        st.download_button("⬇️ Q11 차트 다운로드 (PNG)",
                           data=buf2.getvalue(),
                           file_name=f"Q11_Spread_{target_bond}_{latest_date}.png",
                           mime="image/png")
    else:
        st.info("스프레드 데이터가 없습니다 (금리 비교 시트 필요)")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭4: 추가 질문 (Chat)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab4:
    st.subheader("💬 추가 질문")
    st.caption("종목명(예: 25-7)이나 키워드(금리, 거래량, 잔고, 대차, 스프레드, 박스권)를 포함해 질문하세요")

    # 채팅 히스토리 표시
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 입력
    if prompt := st.chat_input("질문을 입력하세요..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("분석 중..."):
                answer = natural_language_query(
                    prompt, bonds, rates, results
                )
            st.markdown(f"```\n{answer}\n```")
        st.session_state.chat_history.append({"role": "assistant", "content": f"```\n{answer}\n```"})

    if st.session_state.chat_history:
        if st.button("대화 초기화", use_container_width=False):
            st.session_state.chat_history = []
            st.rerun()

"""
장기국고채 마켓 데일리 — Streamlit App
"""

import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import warnings
warnings.filterwarnings('ignore')

# matplotlib은 차트 생성 시에만 임포트 (모듈 레벨 오류 방지)

# ── 페이지 설정 (가장 먼저) ──
st.set_page_config(
    page_title="장기국고채 마켓 데일리",
    page_icon="📊",
    layout="wide",
)

# ── bond_engine 임포트 ──
try:
    from bond_engine import (
        load_all_data, run_all_questions, format_report,
        natural_language_query, setup_korean_font,
        BOND_SHEETS_ALL, SHORT_NAMES, moving_avg,
        q3_box_position,
    )
except Exception as e:
    st.error(f"bond_engine 임포트 오류: {e}")
    st.stop()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  세션 상태 초기화
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for key, default in [
    ("chat_history", []),
    ("last_file_id", None),
    ("bonds", None),
    ("rates", None),
    ("available_bonds", []),
    ("results", None),
    ("target_bond", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_available_bonds(bonds):
    all_short = [SHORT_NAMES[s] for s in BOND_SHEETS_ALL if s in SHORT_NAMES]
    return [s for s in all_short if s in bonds and len(bonds[s]) > 0]

def get_latest_date(bonds, available_bonds):
    dates = []
    for b in available_bonds:
        df = bonds.get(b)
        if df is not None and len(df) > 0:
            dates.append(df.iloc[-1]["일자"])
    return max(dates).strftime("%Y-%m-%d") if dates else "미상"

def load_data_from_upload(uploaded_file):
    """업로드된 파일을 임시 파일로 저장 후 로딩"""
    import tempfile
    file_bytes = uploaded_file.getvalue()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        bonds, rates, _ = load_all_data(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return bonds, rates

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  헤더
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.title("📊 장기국고채 마켓 데일리")
st.caption("엑셀 파일을 업로드하면 12개 핵심 질문에 자동 답변합니다")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  사이드바
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.header("⚙️ 설정")
    uploaded = st.file_uploader("채권 데이터 엑셀 (.xlsx)", type=["xlsx"])

    if uploaded is not None:
        file_id = f"{uploaded.name}_{uploaded.size}"
        if st.session_state.last_file_id != file_id:
            with st.spinner("데이터 로딩 중..."):
                try:
                    bonds, rates = load_data_from_upload(uploaded)
                    available = get_available_bonds(bonds)
                    st.session_state.bonds = bonds
                    st.session_state.rates = rates
                    st.session_state.available_bonds = available
                    st.session_state.last_file_id = file_id
                    st.session_state.results = None
                    if available:
                        st.session_state.target_bond = available[min(1, len(available)-1)]
                    st.success(f"✅ 종목 {len(available)}개 로드 완료")
                except Exception as e:
                    st.error(f"파일 로딩 오류: {e}")

# 사이드바 분석 옵션 (데이터 있을 때만)
bonds = st.session_state.bonds
rates = st.session_state.rates
available_bonds = st.session_state.available_bonds

with st.sidebar:
    if bonds is not None and len(available_bonds) > 0:
        st.divider()
        st.subheader("📌 분석 옵션")

        # 기준 종목
        default_idx = min(1, len(available_bonds) - 1)
        saved_target = st.session_state.target_bond
        if saved_target in available_bonds:
            default_idx = available_bonds.index(saved_target)

        target_bond = st.selectbox(
            "기준 종목 (Q2~Q11)",
            options=available_bonds,
            index=default_idx,
        )
        st.session_state.target_bond = target_bond

        # Q6 옵션
        st.markdown("**Q6. 대차잔고 월별**")
        df_t = bonds.get(target_bond)
        max_months = 12
        if df_t is not None and len(df_t) > 0:
            n_months = df_t["일자"].dt.to_period("M").nunique()
            max_months = max(1, min(12, n_months))

        q6_months = st.slider("조회 개월수", 1, max_months, min(6, max_months))
        q6_ref_day = st.number_input("기준 영업일", min_value=1, max_value=23, value=7)

        # Q12 대상 종목
        st.markdown("**Q12. 잔고변화 종목**")
        q12_targets = []
        bonds_30y = [b for b in available_bonds if b in ["26-2","25-7","25-2","24-8","24-2","23-7"]]
        bonds_50y = [b for b in available_bonds if b in ["24-11","22-12"]]
        for b in bonds_30y[:4]:
            if st.checkbox(f"30년 {b}", value=True, key=f"chk_{b}"):
                q12_targets.append(b)
        for b in bonds_50y:
            if st.checkbox(f"50년 {b}", value=False, key=f"chk_{b}"):
                q12_targets.append(b)
        if not q12_targets:
            q12_targets = available_bonds[:2]

        st.divider()
        if st.button("🔍 분석 실행", type="primary", use_container_width=True):
            with st.spinner("분석 중..."):
                try:
                    st.session_state.results = run_all_questions(
                        bonds, rates,
                        target=target_bond,
                        q6_ref_day=q6_ref_day,
                        q6_months=q6_months,
                        q12_targets=q12_targets,
                    )
                    st.success("분석 완료!")
                except Exception as e:
                    st.error(f"분석 오류: {e}")
                    st.session_state.results = None

        # 자동 실행 (처음 로드 시)
        if st.session_state.results is None and bonds is not None:
            with st.spinner("초기 분석 중..."):
                try:
                    st.session_state.results = run_all_questions(
                        bonds, rates,
                        target=target_bond,
                        q6_ref_day=7,
                        q6_months=min(6, max_months),
                        q12_targets=q12_targets if q12_targets else available_bonds[:2],
                    )
                except Exception as e:
                    st.error(f"초기 분석 오류: {e}")

        latest = get_latest_date(bonds, available_bonds)
        st.caption(f"📅 기준일: {latest}")
    else:
        st.info("👆 엑셀 파일을 업로드하세요")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  업로드 전 안내
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if bonds is None or st.session_state.results is None:
    st.markdown("---")
    st.subheader("사용 방법")
    c1, c2, c3 = st.columns(3)
    c1.info("**1단계**\n\n왼쪽 사이드바에서\n채권 데이터 엑셀 업로드")
    c2.info("**2단계**\n\n기준 종목과 기간을\n선택 후 분석 실행")
    c3.info("**3단계**\n\n분석결과, 차트,\n리포트 자동 생성")
    st.stop()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인 콘텐츠
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
results = st.session_state.results
target_bond = st.session_state.target_bond or available_bonds[0]
latest_date = get_latest_date(bonds, available_bonds)

tab1, tab2, tab3, tab4 = st.tabs(["📋 분석결과", "✏️ 편집리포트", "📈 차트", "💬 추가질문"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭1: 분석결과
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab1:
    st.subheader(f"분석 결과 | 기준일: {latest_date} | 기준종목: {target_bond}")

    # Q1
    with st.expander("Q1. 전일대비 변동성 TOP10", expanded=True):
        q1 = results.get("Q1", [])
        if q1:
            df_q1 = pd.DataFrame(q1)[["종목","변수","전일값","당일값","변동"]]
            df_q1.index = range(1, len(df_q1)+1)
            st.dataframe(df_q1, use_container_width=True)
        else:
            st.info("데이터 없음")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("Q2. 공격적 매수 투자자", expanded=True):
            q2 = results.get("Q2", {})
            buyers = q2.get("순위", [])
            if buyers:
                df_q2 = pd.DataFrame(buyers)
                df_q2.index = range(1, len(df_q2)+1)
                st.dataframe(df_q2, use_container_width=True)
            else:
                st.info("매수 거래 없음")

        with st.expander("Q3. 20일 박스권 위치", expanded=True):
            q3 = results.get("Q3", {})
            if q3:
                pos = q3.get("현재위치", 0)
                st.metric("현재 금리", f"{q3.get('현재금리',0):.3f}%")
                c1, c2 = st.columns(2)
                c1.metric("박스 하단", f"{q3.get('박스권하단',0):.3f}%")
                c2.metric("박스 상단", f"{q3.get('박스권상단',0):.3f}%")
                st.progress(min(100, max(0, int(pos))))
                st.caption(f"{q3.get('레벨','-')} | {pos:.1f}%")
            else:
                st.info("데이터 부족 (최소 20일)")

        with st.expander("Q5. 박스권 상·하단 매수 주체", expanded=False):
            q5 = results.get("Q5", {})
            if q5:
                c1, c2 = st.columns(2)
                c1.metric("상단 매수", q5.get("상단매수주체","-"),
                          f"{q5.get('상단순매수억',0):+,.0f}억")
                c2.metric("하단 매수", q5.get("하단매수주체","-"),
                          f"{q5.get('하단순매수억',0):+,.0f}억")
            else:
                st.info("데이터 없음")

    with col_b:
        with st.expander("Q4. 이동평균 금리 위치", expanded=True):
            q4 = results.get("Q4", {})
            if q4:
                cur = q4.get("현재금리", 0)
                st.metric("현재 금리", f"{cur:.3f}%")
                c1, c2, c3 = st.columns(3)
                ma5 = q4.get("MA5", 0)
                ma20 = q4.get("MA20", 0)
                ma60 = q4.get("MA60", 0)
                c1.metric("MA5", f"{ma5:.3f}%", "▲위" if cur > ma5 else "▼아래")
                c2.metric("MA20", f"{ma20:.3f}%", "▲위" if cur > ma20 else "▼아래")
                c3.metric("MA60", f"{ma60:.3f}%", "▲위" if cur > ma60 else "▼아래")
            else:
                st.info("데이터 부족")

        with st.expander("Q6. 대차잔고비율 월별 추이", expanded=True):
            q6 = results.get("Q6", {})
            trend6 = q6.get("추이", [])
            if trend6:
                df_q6 = pd.DataFrame(trend6)
                df_q6.columns = ["월", "날짜", "대차잔고비율(%)"]
                st.dataframe(df_q6, use_container_width=True)
            else:
                st.info("대차 데이터 없음")

        with st.expander("Q7. 대차잔고 비율·속도 박스권", expanded=False):
            q7 = results.get("Q7", {})
            if q7.get("error"):
                st.warning(q7["error"])
            elif q7:
                rpos = min(100, max(0, int(q7.get("비율위치", 0))))
                spos = min(100, max(0, int(q7.get("속도위치", 0))))
                c1, c2 = st.columns(2)
                c1.metric("현재 비율", f"{q7.get('현재비율',0):.3f}%")
                c1.progress(rpos)
                c1.caption(f"박스 위치: {rpos}%")
                c2.metric("증감 속도", f"{q7.get('현재속도_억',0):+.1f}억")
                c2.progress(spos)
                c2.caption(f"박스 위치: {spos}%")
            else:
                st.info("데이터 없음")

    col_c, col_d = st.columns(2)
    with col_c:
        with st.expander("Q8. 당일 거래량 vs 20일 평균", expanded=False):
            q8 = results.get("Q8", {})
            if q8:
                ratio = q8.get("비율", 0)
                st.metric("당일 거래량", f"{q8.get('당일거래량_억',0):,.0f}억",
                          f"20일평균 대비 {ratio:.1f}%")
                st.progress(min(100, max(0, int(ratio))))
            else:
                st.info("데이터 없음")

    with col_d:
        with st.expander("Q9. 거래량×변동폭 4분면", expanded=False):
            q9 = results.get("Q9", {})
            if q9:
                st.info(q9.get("4분면", "-"))
                c1, c2 = st.columns(2)
                c1.metric("거래량", q9.get("거래량증감", "-"))
                c2.metric("변동폭", q9.get("변동폭증감", "-"))
            else:
                st.info("데이터 없음")

    with st.expander("Q10. 원금 발행증감 월별 추이", expanded=False):
        q10 = results.get("Q10", {})
        trend10 = q10.get("추이", [])
        if trend10:
            df_q10 = pd.DataFrame(trend10)
            df_q10.columns = ["월", "발행액(조)", "전월대비(조)"]
            st.dataframe(df_q10, use_container_width=True)
        else:
            st.info("원금 데이터 없음")

    with st.expander("Q11. 스프레드 박스권 위치", expanded=False):
        q11 = results.get("Q11", {})
        spreads = q11.get("스프레드", [])
        if spreads:
            rows = [{
                "비교대상": s["비교대상"],
                "스프레드(bp)": f"{s['스프레드bp']:+.1f}",
                "박스하단": f"{s['박스하단bp']:+.1f}",
                "박스상단": f"{s['박스상단bp']:+.1f}",
                "레벨": s["레벨"],
                "위치(%)": f"{s['위치']:.1f}",
            } for s in spreads]
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
        else:
            st.info("스프레드 데이터 없음")

    with st.expander("Q12. 투자자별 잔고 변화", expanded=False):
        q12 = results.get("Q12", [])
        if q12:
            for bd in q12:
                st.markdown(f"**{bd['종목']}**")
                df12 = pd.DataFrame(bd["투자자별"])
                if not df12.empty:
                    df12.columns = ["투자자", "잔고변화(억)"]
                    st.dataframe(df12, use_container_width=True)
        else:
            st.info("잔고 데이터 없음")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭2: 편집 리포트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab2:
    st.subheader("✏️ 편집 가능 리포트")
    report_text = format_report(results, base_date=latest_date)
    edited = st.text_area("리포트 (자유 편집)", value=report_text, height=600)
    st.download_button(
        "⬇️ 텍스트 다운로드",
        data=edited.encode("utf-8"),
        file_name=f"마켓데일리_{latest_date}.txt",
        mime="text/plain",
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭3: 차트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab3:
    st.subheader("📈 차트")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        setup_korean_font()
    except Exception as e:
        st.error(f"matplotlib 초기화 오류: {e}")
        st.stop()

    # Q4 차트
    st.markdown(f"#### Q4. {target_bond} 금리 이동평균선")
    q4 = results.get("Q4", {})
    chart_df = q4.get("chart_df")

    if chart_df is not None and len(chart_df) > 0:
        try:
            fig, ax = plt.subplots(figsize=(12, 4))
            rate_col = "민평4사 수익률(산출일) 당일"
            n = len(chart_df)
            x = list(range(n))
            labels = chart_df["일자"].dt.strftime("%m/%d").tolist()

            ax.plot(x, chart_df[rate_col].tolist(), color="#1f77b4", lw=1.5, label="Yield")
            ax.plot(x, chart_df["MA5"].tolist(),  color="#ff7f0e", lw=1.2, ls="--", label="MA5")
            ax.plot(x, chart_df["MA20"].tolist(), color="#2ca02c", lw=1.2, ls="--", label="MA20")
            ax.plot(x, chart_df["MA60"].tolist(), color="#d62728", lw=1.2, ls="--", label="MA60")

            step = max(1, n // 20)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(labels[::step], rotation=45, fontsize=7)
            ax.set_ylabel("Yield (%)", fontsize=9)
            ax.set_title(f"KTB 30Y {target_bond} - Yield & Moving Averages", fontsize=10)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=120)
            buf.seek(0)
            st.image(buf.getvalue())
            st.download_button("⬇️ Q4 차트 PNG", data=buf.getvalue(),
                               file_name=f"Q4_{target_bond}_{latest_date}.png", mime="image/png")
            plt.close(fig)
        except Exception as e:
            st.error(f"Q4 차트 오류: {e}")
    else:
        st.info("이동평균 데이터 부족")

    st.divider()

    # Q11 차트
    st.markdown(f"#### Q11. {target_bond} 스프레드 박스권")
    q11 = results.get("Q11", {})
    spreads = q11.get("스프레드", [])

    if spreads:
        try:
            n_sp = len(spreads)
            fig2, axes = plt.subplots(1, n_sp, figsize=(4 * n_sp, 4), sharey=False)
            if n_sp == 1:
                axes = [axes]
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

            for i, (s, ax) in enumerate(zip(spreads, axes)):
                series = s["series"]
                lo = s["박스하단bp"] / 100
                hi = s["박스상단bp"] / 100
                n_s = len(series)
                x_s = list(range(n_s))
                lbs = series.index.strftime("%m/%d").tolist()

                ax.plot(x_s, series.values.tolist(), color=colors[i % 5], lw=1.2)
                ax.axhline(lo, color="green", lw=1, ls=":")
                ax.axhline(hi, color="red",   lw=1, ls=":")

                step_s = max(1, n_s // 8)
                ax.set_xticks(x_s[::step_s])
                ax.set_xticklabels(lbs[::step_s], rotation=45, fontsize=6)
                ax.set_title(f"KTB30Y-{s['비교대상']}\n{s['레벨']} ({s['위치']:.1f}%)", fontsize=8)
                ax.grid(True, alpha=0.3)

            plt.tight_layout()
            buf2 = io.BytesIO()
            fig2.savefig(buf2, format="png", dpi=120, bbox_inches="tight")
            buf2.seek(0)
            st.image(buf2.getvalue())
            st.download_button("⬇️ Q11 차트 PNG", data=buf2.getvalue(),
                               file_name=f"Q11_{target_bond}_{latest_date}.png", mime="image/png")
            plt.close(fig2)
        except Exception as e:
            st.error(f"Q11 차트 오류: {e}")
    else:
        st.info("스프레드 데이터 없음")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  탭4: 추가 질문
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab4:
    st.subheader("💬 추가 질문")
    st.caption("예: '25-7 금리 알려줘', '외국인 거래량은?', '스프레드 현황'")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("질문 입력...")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            answer = natural_language_query(prompt, bonds, rates, results)
        except Exception as e:
            answer = f"오류: {e}"
        with st.chat_message("assistant"):
            st.text(answer)
        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    if st.session_state.chat_history:
        if st.button("대화 초기화"):
            st.session_state.chat_history = []
            st.rerun()

"""
장기국고채 분석 엔진 (bond_engine.py)
- 데이터 로딩 + 단위 변환
- 핵심질문 12개 분석 함수
- 차트 생성
- 자연어 Q&A 처리
"""

import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  상수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BOND_SHEETS_30Y = ['30년 26-2','30년 25-7','30년 25-2','30년 24-8','30년 24-2','30년 23-7']
BOND_SHEETS_50Y = ['50년 24-11','50년 22-12']
BOND_SHEETS_ALL = BOND_SHEETS_30Y + BOND_SHEETS_50Y

PRINCIPAL_SHEETS_30Y = ['30년 26-2원금','30년 25-7원금','30년 25-2원금','30년 24-8원금','30년 24-2원금','30년 23-7원금']
PRINCIPAL_SHEETS_50Y = ['50년 24-11원금','50년 22-12원금']
PRINCIPAL_SHEETS_ALL = PRINCIPAL_SHEETS_30Y + PRINCIPAL_SHEETS_50Y

SHORT_NAMES = {
    '30년 26-2': '26-2', '30년 25-7': '25-7', '30년 25-2': '25-2',
    '30년 24-8': '24-8', '30년 24-2': '24-2', '30년 23-7': '23-7',
    '50년 24-11': '24-11', '50년 22-12': '22-12',
    '30년 26-2원금': '26-2원금', '30년 25-7원금': '25-7원금',
    '30년 25-2원금': '25-2원금', '30년 24-8원금': '24-8원금',
    '30년 24-2원금': '24-2원금', '30년 23-7원금': '23-7원금',
    '50년 24-11원금': '24-11원금', '50년 22-12원금': '22-12원금',
}

INVESTORS = ['외국인','은행','보험기금','자산운용(공모)','종금']
INVESTOR_SHORT = {'외국인':'외국인','은행':'은행','보험기금':'보험','자산운용(공모)':'자산운용','종금':'종금'}

ALL_BOND_NAMES = ['26-2','25-7','25-2','24-8','24-2','23-7','24-11','22-12']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  한글 폰트 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def setup_korean_font():
    """matplotlib 한글 폰트 자동 설정"""
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import platform

    system = platform.system()
    font_found = False

    # 시스템별 한글 폰트 후보
    candidates = []
    if system == 'Windows':
        candidates = ['Malgun Gothic', '맑은 고딕', 'NanumGothic', '나눔고딕']
    elif system == 'Darwin':  # macOS
        candidates = ['AppleGothic', 'Apple SD Gothic Neo', 'NanumGothic']
    else:  # Linux
        candidates = ['NanumGothic', 'Noto Sans CJK KR', 'Noto Sans KR', 'UnDotum']

    # 설치된 폰트 목록에서 매칭
    installed = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in installed:
            plt.rcParams['font.family'] = name
            font_found = True
            break

    # 못 찾으면 ttf 파일 직접 검색
    if not font_found:
        search_paths = [
            os.path.expanduser('~/.fonts'),
            '/usr/share/fonts',
            'C:/Windows/Fonts',
            '/System/Library/Fonts',
            '/Library/Fonts',
        ]
        for sp in search_paths:
            if not os.path.isdir(sp):
                continue
            for root, dirs, files in os.walk(sp):
                for f in files:
                    if 'nanum' in f.lower() or 'malgun' in f.lower() or 'notosanscjk' in f.lower():
                        path = os.path.join(root, f)
                        fm.fontManager.addfont(path)
                        prop = fm.FontProperties(fname=path)
                        plt.rcParams['font.family'] = prop.get_name()
                        font_found = True
                        break
                if font_found:
                    break
            if font_found:
                break

    plt.rcParams['axes.unicode_minus'] = False
    return font_found


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  데이터 로딩
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_sheet(raw, sheet_name):
    """종목 시트 로딩 + 단위 변환 (→ 억) + 날짜 오름차순"""
    df = raw[sheet_name].copy()
    cols = df.iloc[2].tolist()
    data = df.iloc[3:].copy()
    data.columns = cols
    data = data.rename(columns={cols[0]: '일자'})
    data = data[pd.to_datetime(data['일자'], errors='coerce').notna()].copy()
    data['일자'] = pd.to_datetime(data['일자'])
    data = data.sort_values('일자').reset_index(drop=True)

    vol_cols = [c for c in cols if '거래량' in str(c) or '순매수' in str(c)]
    for c in vol_cols:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors='coerce') / 1e8

    for c in ['전일잔량','금일거래','금일상환','금일잔량']:
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors='coerce') / 100

    if '발행액' in data.columns:
        data['발행액'] = pd.to_numeric(data['발행액'], errors='coerce') / 10000

    for inv in INVESTORS:
        c = f'{inv} 잔고수량'
        if c in data.columns:
            data[c] = pd.to_numeric(data[c], errors='coerce') / 10000

    for c in data.columns:
        if c != '일자':
            data[c] = pd.to_numeric(data[c], errors='coerce')

    data['종목'] = SHORT_NAMES.get(sheet_name, sheet_name)
    return data


def load_rate_sheet(raw, sheet_name):
    df = raw[sheet_name].copy()
    cols = df.iloc[2].tolist()
    data = df.iloc[3:].copy()
    data.columns = cols
    data = data.rename(columns={cols[0]: '일자'})
    data = data[pd.to_datetime(data['일자'], errors='coerce').notna()].copy()
    data['일자'] = pd.to_datetime(data['일자'])
    data = data.sort_values('일자').reset_index(drop=True)
    for c in data.columns:
        if c != '일자' and not isinstance(c, float):
            try:
                data[c] = pd.to_numeric(data[c], errors='coerce')
            except Exception:
                pass
    return data


def load_all_data(filepath):
    raw = pd.read_excel(filepath, sheet_name=None, header=None)

    bonds = {}
    for s in BOND_SHEETS_ALL + PRINCIPAL_SHEETS_ALL:
        if s in raw:
            bonds[SHORT_NAMES[s]] = load_sheet(raw, s)

    rates = {}
    rate_map = {
        'KTB10': ('10년국채선물&현물수익률', '국고10년 수익율'),
        'KTB3': ('3넌국채선물&현물수익률', None),
        'IRS10': ('원화IRS10년', 'MID종가'),
        'IRS30': ('원화IRS30년', 'MID종가'),
        'US10': ('미국 10년', 'MID_Close'),
        'US30': ('미국 30년', 'MID_Close'),
        'JP10': ('일본 10년', 'MID_Close'),
        'JP30': ('일본 30년', 'MID_Close'),
        'AU10': ('호주 10년', 'MID_Close'),
        'AU30': ('호주 30년', 'MID_Close'),
    }
    for key, (sname, _) in rate_map.items():
        if sname in raw:
            rates[key] = load_rate_sheet(raw, sname)

    issuance = None
    if '국채추가발행' in raw:
        df = raw['국채추가발행'].copy()
        cols = df.iloc[2].tolist()
        data = df.iloc[3:].copy()
        data.columns = cols
        data = data[data['발행년월'].notna()].copy()
        for c in ['발행예정액','낙찰금액','상장잔액','응찰금액']:
            if c in data.columns:
                data[c] = pd.to_numeric(data[c], errors='coerce') / 100
        issuance = data

    return bonds, rates, issuance


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  유틸리티
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def box_range(series, window=20):
    recent = series.dropna().iloc[-window:]
    return recent.quantile(0.25), recent.quantile(0.75)

def position_in_box(value, lower, upper):
    if upper == lower:
        return 50.0
    return round(max(0, min(100, (value - lower) / (upper - lower) * 100)), 1)

def level_text(pos):
    if pos <= 25: return '하단'
    elif pos <= 50: return '중하단'
    elif pos <= 75: return '중상단'
    else: return '상단'

def moving_avg(series, n):
    return series.rolling(n, min_periods=1).mean()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  핵심질문 12개
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def q1_volatility_top(bonds, n=10):
    """Q1. 전일대비 변동성 TOP"""
    results = []
    metrics = {
        '금리변동': '민평4사 수익률(산출일) 당일',
        '전체매수거래량': '전체 매수 거래량',
        '전체매도거래량': '전체 매도 거래량',
        '전체순매수거래량': '전체 순매수 거래량',
        '대차금일거래': '금일거래',
        '대차금일잔량': '금일잔량',
    }
    for inv in INVESTORS:
        short = INVESTOR_SHORT[inv]
        metrics[f'{short}매수거래량'] = f'{inv} 매수 거래량'
        metrics[f'{short}매도거래량'] = f'{inv} 매도 거래량'
        metrics[f'{short}순매수거래량'] = f'{inv} 순매수 거래량'

    for bname, df in bonds.items():
        if '원금' in bname or len(df) < 2:
            continue
        cur, prev = df.iloc[-1], df.iloc[-2]
        for label, col in metrics.items():
            if col not in df.columns:
                continue
            c_val, p_val = cur.get(col), prev.get(col)
            if pd.isna(c_val) or pd.isna(p_val):
                continue
            chg = c_val - p_val
            if abs(chg) < 0.001:
                continue
            results.append({
                '종목': bname, '변수': label, '컬럼': col,
                '전일값': round(p_val, 2), '당일값': round(c_val, 2),
                '변동': round(chg, 2), '절대변동': abs(chg),
            })
    df_r = pd.DataFrame(results).sort_values('절대변동', ascending=False)
    return df_r.head(n).to_dict('records')


def q2_aggressive_buyers(bonds, target='25-7'):
    """Q2. 공격적 매수 투자자 순위"""
    df = bonds.get(target)
    if df is None or len(df) < 1:
        return {'종목': target, '순위': []}
    cur = df.iloc[-1]
    buyers = []
    for inv in INVESTORS:
        buy_col = f'{inv} 매수 거래량'
        rate_col = f'{inv} 매수 수익률'
        buy_amt = cur.get(buy_col, np.nan)
        buy_rate = cur.get(rate_col, np.nan)
        if pd.notna(buy_amt) and buy_amt > 0:
            buyers.append({
                '투자자': INVESTOR_SHORT.get(inv, inv),
                '매수금액_억': round(buy_amt, 0),
                '매수수익률': round(buy_rate, 3) if pd.notna(buy_rate) else None,
            })
    buyers.sort(key=lambda x: x['매수금액_억'], reverse=True)
    return {'종목': target, '기준일': cur['일자'], '순위': buyers}


def q3_box_position(bonds, target='25-7', window=20):
    """Q3. 박스권 대비 현재 금리 위치"""
    df = bonds.get(target)
    if df is None or len(df) < window:
        return {}
    rate_col = '민평4사 수익률(산출일) 당일'
    series = df[rate_col].dropna()
    cur = series.iloc[-1]
    lower, upper = box_range(series, window)
    pos = position_in_box(cur, lower, upper)
    return {
        '종목': target, '현재금리': round(cur, 3),
        '박스권하단': round(lower, 3), '박스권상단': round(upper, 3),
        '현재위치': pos, '레벨': level_text(pos),
    }


def q4_moving_averages(bonds, target='25-7'):
    """Q4. 이동평균금리와 현재 위치"""
    df = bonds.get(target)
    if df is None or len(df) < 5:
        return {}
    rate_col = '민평4사 수익률(산출일) 당일'
    series = df[rate_col].dropna()
    cur = series.iloc[-1]
    ma5 = moving_avg(series, 5).iloc[-1]
    ma20 = moving_avg(series, 20).iloc[-1]
    ma60 = moving_avg(series, 60).iloc[-1]

    df2 = df[['일자', rate_col]].dropna(subset=[rate_col]).copy().reset_index(drop=True)
    s2 = df2[rate_col]
    df2['MA5'] = moving_avg(s2, 5)
    df2['MA20'] = moving_avg(s2, 20)
    df2['MA60'] = moving_avg(s2, 60)

    return {
        '종목': target, '기준일': df.iloc[-1]['일자'],
        '현재금리': round(cur, 3),
        'MA5': round(ma5, 3), 'MA20': round(ma20, 3), 'MA60': round(ma60, 3),
        '단기비교': '위' if cur > ma5 else '아래',
        '중기비교': '위' if cur > ma20 else '아래',
        '장기비교': '위' if cur > ma60 else '아래',
        'chart_df': df2.tail(120),
    }


def q5_box_buyers(bonds, target='25-7', window=20):
    """Q5. 박스권 상·하단 주요 매수 주체"""
    df = bonds.get(target)
    if df is None or len(df) < window:
        return {}
    rate_col = '민평4사 수익률(산출일) 당일'
    series = df[rate_col]
    lower, upper = box_range(series, window)
    recent = df.tail(window).copy()
    recent_rate = series.tail(window)

    def best_net_buyer(subset):
        if subset.empty:
            return '-', 0, '-', None
        agg = {}
        for inv in INVESTORS:
            col = f'{inv} 순매수 거래량'
            if col in subset.columns:
                val = subset[col].sum()
                if pd.notna(val):
                    agg[INVESTOR_SHORT.get(inv, inv)] = val
        if not agg:
            return '-', 0, '-', None
        best = max(agg, key=lambda k: agg[k])
        date_val = subset.iloc[0]['일자'] if len(subset) == 1 else f"최근 {len(subset)}일"
        rate_val = recent_rate.iloc[subset.index[0] - recent.index[0]] if len(subset) == 1 else None
        return best, round(agg[best], 0), date_val, rate_val

    top_days = recent[recent_rate.values >= upper]
    bot_days = recent[recent_rate.values <= lower]
    t_inv, t_amt, t_date, t_rate = best_net_buyer(top_days)
    b_inv, b_amt, b_date, b_rate = best_net_buyer(bot_days)

    return {
        '종목': target, '박스권하단': round(lower, 3), '박스권상단': round(upper, 3),
        '상단매수주체': t_inv, '상단순매수억': t_amt, '상단날짜': t_date,
        '하단매수주체': b_inv, '하단순매수억': b_amt, '하단날짜': b_date,
    }


def q6_short_balance_monthly(bonds, target='25-7', n_months=6, ref_day=7):
    """Q6. 대차잔고비율 월별 추이"""
    df = bonds.get(target)
    if df is None or '금일잔량' not in df.columns or '발행액' not in df.columns:
        return {}
    df2 = df[['일자','금일잔량','발행액']].dropna().copy()
    df2['비율'] = df2['금일잔량'] / df2['발행액']  # 단위 보정: 백만/만 → 자동 %
    df2['연월'] = df2['일자'].dt.to_period('M')
    results = []
    for period in sorted(df2['연월'].unique())[-n_months:]:
        mdata = df2[df2['연월'] == period].reset_index(drop=True)
        idx = min(ref_day - 1, len(mdata) - 1)
        if idx < 0:
            continue
        row = mdata.iloc[idx]
        results.append({
            '월': str(period), '날짜': row['일자'].strftime('%Y-%m-%d'),
            '대차잔고비율': round(row['비율'], 3),
        })
    return {'종목': target, '기준영업일': ref_day, '추이': results}


def q7_short_balance_speed(bonds, target='25-7', window=20):
    """Q7. 대차잔고 비율 증감속도 + 박스권"""
    df = bonds.get(target)
    if df is None or '금일잔량' not in df.columns:
        return {}
    df2 = df.copy()
    df2['비율'] = df2['금일잔량'] / df2['발행액']  # 단위 보정: 백만/만 → 자동 %
    df2['속도'] = df2['금일거래'] - df2['금일상환']

    ratio_s = df2['비율'].dropna()
    speed_s = df2['속도'].dropna()
    r_cur, s_cur = ratio_s.iloc[-1], speed_s.iloc[-1]
    r_lo, r_hi = box_range(ratio_s, window)
    s_lo, s_hi = box_range(speed_s, window)

    return {
        '종목': target,
        '현재비율': round(r_cur, 3), '비율박스하단': round(r_lo, 3), '비율박스상단': round(r_hi, 3),
        '비율위치': position_in_box(r_cur, r_lo, r_hi),
        '현재속도_억': round(s_cur, 1), '속도박스하단': round(s_lo, 1), '속도박스상단': round(s_hi, 1),
        '속도위치': position_in_box(s_cur, s_lo, s_hi),
    }


def q8_volume_vs_avg(bonds, target='25-7', window=20):
    """Q8. 당일 거래량 vs 20일 평균"""
    df = bonds.get(target)
    if df is None:
        return {}
    vol = df['전체 매수 거래량'].dropna()
    if len(vol) < window + 1:
        return {}
    cur = vol.iloc[-1]
    avg = vol.iloc[-window-1:-1].mean()
    return {
        '종목': target, '당일거래량_억': round(cur, 0),
        '20일평균_억': round(avg, 0), '비율': round(cur / avg * 100, 1) if avg else 0,
    }


def q9_quadrant(bonds, target='25-7', window=20):
    """Q9. 거래량 × 변동폭 4분면"""
    df = bonds.get(target)
    if df is None or len(df) < window + 1:
        return {}
    vol = df['전체 매수 거래량'].dropna()
    hi = df['장내국채-고 수익률']
    lo = df['장내국채-저 수익률']
    comb = pd.DataFrame({'hi': hi, 'lo': lo}).dropna()
    comb['spread_bp'] = (comb['hi'] - comb['lo']) * 100
    if len(vol) < 2 or len(comb) < 2:
        return {}
    cur_vol = vol.iloc[-1]
    avg_vol = vol.iloc[-window-1:-1].mean()
    cur_sp = comb['spread_bp'].iloc[-1]
    avg_sp = comb['spread_bp'].iloc[-window-1:-1].mean()
    vol_up = cur_vol >= avg_vol
    sp_up = cur_sp >= avg_sp

    quads = {
        (True, True): '1사분면 (거래량↑+변동폭↑) — 추세 확인형',
        (False, True): '2사분면 (거래량↓+변동폭↑) — 변동성 확대형',
        (True, False): '3사분면 (거래량↑+변동폭↓) — 안정적 강세형',
        (False, False): '4사분면 (거래량↓+변동폭↓) — 관망·소강형',
    }
    return {
        '종목': target,
        '당일거래량_억': round(cur_vol, 0), '20일평균거래량_억': round(avg_vol, 0),
        '거래량증감': '증가' if vol_up else '감소',
        '당일변동폭bp': round(cur_sp, 1), '20일평균변동폭bp': round(avg_sp, 1),
        '변동폭증감': '증가' if sp_up else '감소',
        '4분면': quads[(vol_up, sp_up)],
    }


def q10_principal_issuance(bonds, n_months=6):
    """Q10. 원금 발행증감 월별 추이"""
    by_month = {}
    for sname in ['26-2원금','25-7원금','25-2원금','24-8원금','24-2원금','23-7원금']:
        df = bonds.get(sname)
        if df is None or '발행액' not in df.columns:
            continue
        t = df[['일자','발행액']].dropna(subset=['발행액']).copy()
        t['연월'] = t['일자'].dt.to_period('M')
        for p, g in t.groupby('연월'):
            val = g['발행액'].iloc[-1]
            by_month[p] = by_month.get(p, 0) + val

    months = sorted(by_month.keys())[-(n_months+1):]
    trend = []
    for i in range(1, len(months)):
        m, pm = months[i], months[i-1]
        cur_v, prev_v = by_month[m], by_month[pm]
        chg = cur_v - prev_v
        trend.append({
            '월': str(m),
            '발행액조': round(cur_v / 10000, 2),
            '전월대비조': round(chg / 10000, 2),
        })
    return {'추이': trend}


def q11_spread_box(bonds, rates, target='25-7', window=20):
    """Q11. 스프레드 박스권 위치"""
    df = bonds.get(target)
    if df is None:
        return {}
    rate_col = '민평4사 수익률(산출일) 당일'
    ktb30 = df.set_index('일자')[rate_col].dropna()

    comparisons = [
        ('국고10년', 'KTB10', '국고10년 수익율'),
        ('IRS30년', 'IRS30', 'MID종가'),
        ('미국30년', 'US30', 'MID_Close'),
        ('일본30년', 'JP30', 'MID_Close'),
        ('호주30년', 'AU30', 'MID_Close'),
    ]
    results = []
    for label, key, col in comparisons:
        rdf = rates.get(key)
        if rdf is None or col not in rdf.columns:
            continue
        other = rdf.set_index('일자')[col].dropna()
        common = ktb30.index.intersection(other.index)
        if len(common) < window:
            continue
        spread = (ktb30[common] - other[common]).sort_index()
        cur_sp = spread.iloc[-1]
        lo, hi = box_range(spread, window)
        pos = position_in_box(cur_sp, lo, hi)
        results.append({
            '비교대상': label,
            '스프레드bp': round(cur_sp * 100, 1),
            '박스하단bp': round(lo * 100, 1), '박스상단bp': round(hi * 100, 1),
            '위치': pos, '레벨': level_text(pos),
            'series': spread.tail(120),
        })
    return {'종목': target, '스프레드': results}


def q12_balance_changes(bonds, targets=None):
    """Q12. 투자자별 잔고 변화"""
    if targets is None:
        targets = ['26-2','25-7','25-2','24-11']
    results = []
    for t in targets:
        df = bonds.get(t)
        if df is None or len(df) < 2:
            continue
        cur, prev = df.iloc[-1], df.iloc[-2]
        changes = []
        for inv in INVESTORS:
            col = f'{inv} 잔고수량'
            if col not in df.columns:
                continue
            c_val, p_val = cur.get(col, np.nan), prev.get(col, np.nan)
            if pd.isna(c_val) or pd.isna(p_val):
                continue
            chg = c_val - p_val
            changes.append({'투자자': INVESTOR_SHORT.get(inv, inv), '잔고변화_억': round(chg, 2)})
        changes.sort(key=lambda x: abs(x['잔고변화_억']), reverse=True)
        results.append({'종목': t, '투자자별': changes})
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  전체 분석 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all_questions(bonds, rates, target='25-7',
                      q6_ref_day=7, q6_months=6,
                      q12_targets=None):
    """12개 질문 전부 실행 → dict 반환"""
    if q12_targets is None:
        q12_targets = ['26-2','25-7','25-2','24-11']
    return {
        'Q1': q1_volatility_top(bonds),
        'Q2': q2_aggressive_buyers(bonds, target),
        'Q3': q3_box_position(bonds, target),
        'Q4': q4_moving_averages(bonds, target),
        'Q5': q5_box_buyers(bonds, target),
        'Q6': q6_short_balance_monthly(bonds, target, q6_months, q6_ref_day),
        'Q7': q7_short_balance_speed(bonds, target),
        'Q8': q8_volume_vs_avg(bonds, target),
        'Q9': q9_quadrant(bonds, target),
        'Q10': q10_principal_issuance(bonds),
        'Q11': q11_spread_box(bonds, rates, target),
        'Q12': q12_balance_changes(bonds, q12_targets),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  텍스트 리포트 생성 (편집 가능 기본 초안)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def format_report(results, base_date=None):
    """12개 질문 결과를 한글 텍스트 리포트로 변환"""
    lines = []
    lines.append(f"━━ 장기국고채 마켓 데일리 ━━  기준일: {base_date or '미정'}\n")

    # Q1
    lines.append("■ Q1. 전일대비 변동성 TOP10")
    for i, r in enumerate(results.get('Q1', []), 1):
        chg = r['변동']
        sign = '+' if chg > 0 else ''
        lines.append(f"  {i}. {r['종목']} {r['변수']}: {sign}{chg:,.1f}억")
    lines.append("")

    # Q2
    q2 = results.get('Q2', {})
    lines.append(f"■ Q2. 공격적 매수 투자자 — {q2.get('종목','')}")
    for i, b in enumerate(q2.get('순위', []), 1):
        rate_str = f", 평균 {b['매수수익률']:.3f}%" if b['매수수익률'] else ""
        lines.append(f"  {i}. {b['투자자']}: {b['매수금액_억']:,.0f}억 매수{rate_str}")
    lines.append("")

    # Q3
    q3 = results.get('Q3', {})
    lines.append(f"■ Q3. 20일 박스권 위치 — {q3.get('종목','')}")
    lines.append(f"  현재 금리: {q3.get('현재금리',0):.3f}%")
    lines.append(f"  박스권: {q3.get('박스권하단',0):.3f}% ~ {q3.get('박스권상단',0):.3f}%")
    lines.append(f"  위치: {q3.get('레벨','-')}에서 {q3.get('현재위치',0):.1f}%")
    lines.append("")

    # Q4
    q4 = results.get('Q4', {})
    lines.append(f"■ Q4. 이동평균금리 위치 — {q4.get('종목','')}")
    lines.append(f"  현재: {q4.get('현재금리',0):.3f}%  |  MA5: {q4.get('MA5',0):.3f}%({q4.get('단기비교','')})  MA20: {q4.get('MA20',0):.3f}%({q4.get('중기비교','')})  MA60: {q4.get('MA60',0):.3f}%({q4.get('장기비교','')})")
    lines.append("")

    # Q5
    q5 = results.get('Q5', {})
    lines.append(f"■ Q5. 박스권 상·하단 매수 주체 — {q5.get('종목','')}")
    lines.append(f"  상단({q5.get('박스권상단',0):.3f}%): {q5.get('상단매수주체','-')} 순매수 {q5.get('상단순매수억',0):+,.0f}억")
    lines.append(f"  하단({q5.get('박스권하단',0):.3f}%): {q5.get('하단매수주체','-')} 순매수 {q5.get('하단순매수억',0):+,.0f}억")
    lines.append("")

    # Q6
    q6 = results.get('Q6', {})
    lines.append(f"■ Q6. 대차잔고비율 월별 추이 — {q6.get('종목','')} (영업일 {q6.get('기준영업일','-')}일차)")
    for t in q6.get('추이', []):
        lines.append(f"  {t['월']} ({t['날짜']}): {t['대차잔고비율']:.3f}%")
    lines.append("")

    # Q7
    q7 = results.get('Q7', {})
    lines.append(f"■ Q7. 대차잔고 비율·속도 박스권 — {q7.get('종목','')}")
    lines.append(f"  비율: {q7.get('현재비율',0):.3f}%  박스 {q7.get('비율박스하단',0):.3f}%~{q7.get('비율박스상단',0):.3f}%  위치 {q7.get('비율위치',0):.1f}%")
    lines.append(f"  속도: {q7.get('현재속도_억',0):+,.1f}억  박스 {q7.get('속도박스하단',0):+,.1f}~{q7.get('속도박스상단',0):+,.1f}억  위치 {q7.get('속도위치',0):.1f}%")
    lines.append("")

    # Q8
    q8 = results.get('Q8', {})
    lines.append(f"■ Q8. 당일 거래량 — {q8.get('종목','')}")
    lines.append(f"  당일 {q8.get('당일거래량_억',0):,.0f}억 / 20일평균 {q8.get('20일평균_억',0):,.0f}억 = {q8.get('비율',0):.1f}%")
    lines.append("")

    # Q9
    q9 = results.get('Q9', {})
    lines.append(f"■ Q9. 거래량×변동폭 4분면 — {q9.get('종목','')}")
    lines.append(f"  거래량 {q9.get('거래량증감','-')} / 변동폭 {q9.get('변동폭증감','-')}")
    lines.append(f"  → {q9.get('4분면','-')}")
    lines.append("")

    # Q10
    q10 = results.get('Q10', {})
    lines.append("■ Q10. 국고30년 원금 발행증감 (최근 6개월)")
    for t in q10.get('추이', []):
        lines.append(f"  {t['월']}: {t['발행액조']:.2f}조 ({t['전월대비조']:+.2f}조)")
    lines.append("")

    # Q11
    q11 = results.get('Q11', {})
    lines.append(f"■ Q11. 스프레드 박스권 위치 — {q11.get('종목','')}")
    for s in q11.get('스프레드', []):
        lines.append(f"  국고30년-{s['비교대상']}: {s['스프레드bp']:+.1f}bp  박스 {s['박스하단bp']:+.1f}~{s['박스상단bp']:+.1f}bp  {s['레벨']} {s['위치']:.1f}%")
    lines.append("")

    # Q12
    q12 = results.get('Q12', [])
    lines.append("■ Q12. 투자자별 잔고 변화")
    for bond_data in q12:
        lines.append(f"  [{bond_data['종목']}]")
        for c in bond_data['투자자별']:
            v = c['잔고변화_억']
            lines.append(f"    {c['투자자']}: {v:+,.2f}억")
    lines.append("")

    return '\n'.join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  자연어 Q&A 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def natural_language_query(question, bonds, rates, results):
    """데이터 기반 자연어 질문 응답"""
    q = question.strip()

    # 종목 추출
    found_bond = None
    for b in ALL_BOND_NAMES:
        if b in q:
            found_bond = b
            break

    # 투자자 추출
    found_investor = None
    inv_keywords = {'외국인':'외국인','은행':'은행','보험':'보험기금','자산운용':'자산운용(공모)','종금':'종금'}
    for short, full in inv_keywords.items():
        if short in q:
            found_investor = (short, full)
            break

    # ── 패턴별 응답 ──

    # 금리 관련
    if any(kw in q for kw in ['금리', '수익률', '현재']):
        target = found_bond or '25-7'
        df = bonds.get(target)
        if df is not None and len(df) > 0:
            cur = df.iloc[-1]
            rate = cur.get('민평4사 수익률(산출일) 당일')
            hi = cur.get('장내국채-고 수익률')
            lo = cur.get('장내국채-저 수익률')
            date = cur['일자'].strftime('%Y-%m-%d')
            text = f"[{target}] {date} 기준\n"
            if pd.notna(rate):
                text += f"  민평수익률: {rate:.3f}%\n"
            if pd.notna(hi) and pd.notna(lo):
                text += f"  장내 고가: {hi:.3f}% / 저가: {lo:.3f}% (변동폭: {(hi-lo)*100:.1f}bp)\n"
            # 이동평균
            s = df['민평4사 수익률(산출일) 당일'].dropna()
            text += f"  MA5: {moving_avg(s,5).iloc[-1]:.3f}%  MA20: {moving_avg(s,20).iloc[-1]:.3f}%  MA60: {moving_avg(s,60).iloc[-1]:.3f}%"
            return text

    # 거래량 관련
    if '거래량' in q:
        target = found_bond or '25-7'
        df = bonds.get(target)
        if df is not None and len(df) > 0:
            cur = df.iloc[-1]
            date = cur['일자'].strftime('%Y-%m-%d')
            text = f"[{target}] {date} 거래량\n"
            text += f"  전체 매수: {cur.get('전체 매수 거래량', 0):,.0f}억\n"
            text += f"  전체 매도: {cur.get('전체 매도 거래량', 0):,.0f}억\n"
            text += f"  순매수: {cur.get('전체 순매수 거래량', 0):+,.0f}억\n"
            if found_investor:
                short, full = found_investor
                buy = cur.get(f'{full} 매수 거래량', 0)
                sell = cur.get(f'{full} 매도 거래량', 0)
                net = cur.get(f'{full} 순매수 거래량', 0)
                text += f"\n  [{short}]\n  매수: {buy:,.0f}억 / 매도: {sell:,.0f}억 / 순매수: {net:+,.0f}억"
            else:
                text += "\n  투자자별 매수:\n"
                for inv in INVESTORS:
                    val = cur.get(f'{inv} 매수 거래량', 0)
                    if pd.notna(val) and val > 0:
                        text += f"    {INVESTOR_SHORT[inv]}: {val:,.0f}억\n"
            return text

    # 잔고 관련
    if '잔고' in q:
        target = found_bond or '25-7'
        df = bonds.get(target)
        if df is not None and len(df) > 1:
            cur, prev = df.iloc[-1], df.iloc[-2]
            date = cur['일자'].strftime('%Y-%m-%d')
            text = f"[{target}] {date} 잔고 (억 단위)\n"
            for inv in INVESTORS:
                col = f'{inv} 잔고수량'
                c_v = cur.get(col, 0)
                p_v = prev.get(col, 0)
                chg = c_v - p_v if pd.notna(c_v) and pd.notna(p_v) else 0
                text += f"  {INVESTOR_SHORT[inv]}: {c_v:,.1f}억 ({chg:+,.1f}억)\n"
            return text

    # 대차 관련
    if '대차' in q:
        target = found_bond or '25-7'
        df = bonds.get(target)
        if df is not None and len(df) > 0:
            cur = df.iloc[-1]
            date = cur['일자'].strftime('%Y-%m-%d')
            bal = cur.get('금일잔량', 0)
            issue = cur.get('발행액', 0)
            ratio = bal / issue if issue > 0 else 0  # 단위 보정
            text = f"[{target}] {date} 대차 현황\n"
            text += f"  금일잔량: {bal:,.1f}억 / 발행액: {issue:,.0f}억\n"
            text += f"  대차잔고비율: {ratio:.3f}%\n"
            text += f"  금일거래: {cur.get('금일거래',0):,.1f}억 / 금일상환: {cur.get('금일상환',0):,.1f}억"
            return text

    # 스프레드 관련
    if '스프레드' in q:
        q11 = results.get('Q11', {})
        if q11:
            text = f"[{q11.get('종목','')}] 스프레드 현황\n"
            for s in q11.get('스프레드', []):
                text += f"  국고30년-{s['비교대상']}: {s['스프레드bp']:+.1f}bp  박스 {s['레벨']} {s['위치']:.1f}%\n"
            return text

    # 박스권 관련
    if '박스' in q:
        target = found_bond or '25-7'
        r3 = q3_box_position(bonds, target)
        if r3:
            return f"[{target}] 20일 박스권\n  하단: {r3['박스권하단']:.3f}% / 상단: {r3['박스권상단']:.3f}%\n  현재: {r3['현재금리']:.3f}% → {r3['레벨']}에서 {r3['현재위치']:.1f}%"

    # 비교 (종목간)
    if '비교' in q or 'vs' in q.lower():
        found_bonds = [b for b in ALL_BOND_NAMES if b in q]
        if len(found_bonds) >= 2:
            text = "종목 비교:\n"
            for b in found_bonds:
                df = bonds.get(b)
                if df is not None:
                    cur = df.iloc[-1]
                    rate = cur.get('민평4사 수익률(산출일) 당일', 0)
                    vol = cur.get('전체 매수 거래량', 0)
                    text += f"  [{b}] 금리: {rate:.3f}% / 거래량: {vol:,.0f}억\n"
            return text

    # 종목 전체 요약
    if found_bond:
        df = bonds.get(found_bond)
        if df is not None:
            cur = df.iloc[-1]
            date = cur['일자'].strftime('%Y-%m-%d')
            rate = cur.get('민평4사 수익률(산출일) 당일', 0)
            vol = cur.get('전체 매수 거래량', 0)
            net = cur.get('전체 순매수 거래량', 0)
            bal = cur.get('금일잔량', 0)
            issue = cur.get('발행액', 1)
            ratio = bal / issue if issue > 0 else 0  # 단위 보정
            text = f"[{found_bond}] {date} 종합\n"
            text += f"  민평수익률: {rate:.3f}%\n"
            text += f"  거래량: {vol:,.0f}억 / 순매수: {net:+,.0f}억\n"
            text += f"  대차잔고비율: {ratio:.3f}%\n"
            # 주요 매수자
            best_inv, best_amt = '-', 0
            for inv in INVESTORS:
                v = cur.get(f'{inv} 매수 거래량', 0)
                if pd.notna(v) and v > best_amt:
                    best_inv, best_amt = INVESTOR_SHORT[inv], v
            text += f"  최대 매수 주체: {best_inv} ({best_amt:,.0f}억)"
            return text

    return "질문을 이해하지 못했습니다. 종목명(예: 25-7)이나 키워드(금리, 거래량, 잔고, 대차, 스프레드, 박스권)를 포함해 주세요."

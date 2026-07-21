import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta

# 페이지 기본 설정
st.set_page_config(page_title="Asset Allocation Backtester", layout="wide")

# 통화 포맷터 (digit_group=3: 3자리 천단위, digit_group=4: 4자리 만단위)
def format_currency(val, digit_group=3):
    try:
        is_negative = val < 0
        s = str(abs(int(val)))
        parts = []
        while len(s) > digit_group:
            parts.append(s[-digit_group:])
            s = s[:-digit_group]
        parts.append(s)
        formatted = ",".join(reversed(parts))
        return f"-{formatted}" if is_negative else formatted
    except Exception:
        return str(val)

# 추천 자산배분 포트폴리오 가이드 팝업 창
@st.dialog("💡 추천 자산배분 포트폴리오 가이드")
def show_recommendations_dialog():
    st.write("세계적인 투자 거장들이 사용해 온 검증된 자산배분 모델들입니다. **[전략 적용하기]**를 클릭하시면 좌측 구성에 자동으로 반영됩니다.")
    
    strategies = {
        "Classic 60:40 포트폴리오": [
            {"type": "미국 (US)", "ticker": "SPY", "kr_input": "", "weight": 60.0},
            {"type": "미국 (US)", "ticker": "TLT", "kr_input": "", "weight": 40.0}
        ],
        "올웨더 포트폴리오 (간소화)": [
            {"type": "미국 (US)", "ticker": "SPY", "kr_input": "", "weight": 30.0},
            {"type": "미국 (US)", "ticker": "TLT", "kr_input": "", "weight": 40.0},
            {"type": "미국 (US)", "ticker": "IEF", "kr_input": "", "weight": 15.0},
            {"type": "미국 (US)", "ticker": "GLD", "kr_input": "", "weight": 15.0}
        ],
        "영구 포트폴리오 (Permanent)": [
            {"type": "미국 (US)", "ticker": "SPY", "kr_input": "", "weight": 25.0},
            {"type": "미국 (US)", "ticker": "TLT", "kr_input": "", "weight": 25.0},
            {"type": "미국 (US)", "ticker": "GLD", "kr_input": "", "weight": 25.0},
            {"type": "한국 (KR)", "ticker": "157030.KS", "kr_input": "TIGER 단기통안채", "weight": 25.0}
        ],
        "골든 버터플라이 (Golden Butterfly)": [
            {"type": "미국 (US)", "ticker": "SPY", "kr_input": "", "weight": 20.0},
            {"type": "미국 (US)", "ticker": "IJS", "kr_input": "", "weight": 20.0},
            {"type": "미국 (US)", "ticker": "TLT", "kr_input": "", "weight": 20.0},
            {"type": "미국 (US)", "ticker": "SHY", "kr_input": "", "weight": 20.0},
            {"type": "미국 (US)", "ticker": "GLD", "kr_input": "", "weight": 20.0}
        ]
    }
    
    cols = st.columns(2)
    for idx, (name, config) in enumerate(strategies.items()):
        with cols[idx % 2]:
            st.markdown(f"#### {name}")
            for asset in config:
                label = asset["kr_input"] if asset["kr_input"] else asset["ticker"]
                st.write(f"- {label}: **{asset['weight']}%**")
            if st.button(f"📋 {name} 적용하기", key=f"apply_strat_{idx}", use_container_width=True):
                for i in range(10):
                    for prefix in ["type_", "ticker_", "kr_input_", "weight_"]:
                        key_to_del = f"{prefix}{i}"
                        if key_to_del in st.session_state:
                            del st.session_state[key_to_del]
                
                for i, asset in enumerate(config):
                    st.session_state[f"type_{i}"] = asset.get("type", "미국 (US)")
                    st.session_state[f"weight_{i}"] = float(asset.get("weight", 0.0))
                    if asset.get("type") == "미국 (US)":
                        st.session_state[f"ticker_{i}"] = asset.get("ticker", "")
                    else:
                        st.session_state[f"kr_input_{i}"] = asset.get("kr_input", "")
                
                st.session_state.assets = config
                st.rerun()

# 추천 자산군 팝업 창
@st.dialog("🔍 ETF 추천 자산군 목록")
def show_asset_classes_dialog():
    st.write("자산배분 전략에 널리 사용되는 신뢰성 높은 주요 자산군의 ETF 목록입니다. 원하는 자산 우측의 **[추가]** 버튼을 누르시면 포트폴리오 설정 창의 빈 슬롯에 자동 입력됩니다.")
    
    categories = {
        "📈 주식 자산군": [
            {"label": "미국 S&P500", "country": "미국 (US)", "ticker": "SPY", "kr_input": "", "desc": "글로벌 시장의 중심, S&P 500 추종"},
            {"label": "미국 나스닥100", "country": "미국 (US)", "ticker": "QQQ", "kr_input": "", "desc": "기술주 및 혁신 성장주 추종"},
            {"label": "미국 배당다우존스", "country": "미국 (US)", "ticker": "SCHD", "kr_input": "", "desc": "우량 배당주 성과 추종"},
            {"label": "미국 소형 가치주", "country": "미국 (US)", "ticker": "IJS", "kr_input": "", "desc": "골든 버터플라이 핵심 자산군"},
            {"label": "한국 KOSPI 200", "country": "한국 (KR)", "ticker": "069500.KS", "kr_input": "KODEX 200", "desc": "한국 시장 대표 200대 기업 추종"},
            {"label": "한국 미국S&P500", "country": "한국 (KR)", "ticker": "360750.KS", "kr_input": "TIGER 미국S&P500", "desc": "연금계좌에서 유용한 원화 상장 미국 S&P500"},
            {"label": "한국 미국나스닥100", "country": "한국 (KR)", "ticker": "133690.KS", "kr_input": "TIGER 미국나스닥100", "desc": "연금계좌 유용 원화 상장 나스닥"}
        ],
        "💵 채권 자산군": [
            {"label": "미국 장기 국채", "country": "미국 (US)", "ticker": "TLT", "kr_input": "", "desc": "20년 이상 장기국채, 주식 하락 시 방어 효과"},
            {"label": "미국 중기 국채", "country": "미국 (US)", "ticker": "IEF", "kr_input": "", "desc": "7-10년 중기 국채, 안정적 이자 수익과 가치 보존"},
            {"label": "미국 단기 국채", "country": "미국 (US)", "ticker": "SHY", "kr_input": "", "desc": "1-3년 단기 국채, 변동성이 낮은 안전 자산"},
            {"label": "한국 국고채 3년", "country": "한국 (KR)", "ticker": "114260.KS", "kr_input": "KODEX 국고채3년", "desc": "한국 3년 만기 국채 추종 상품"},
            {"label": "한국 국고채 10년", "country": "한국 (KR)", "ticker": "148070.KS", "kr_input": "KOSEF 국고채10년", "desc": "한국 10년 만기 장기 국채 추종"}
        ],
        "🪙 대체 자산군": [
            {"label": "금 현물 (미국)", "country": "미국 (US)", "ticker": "GLD", "kr_input": "", "desc": "대표적인 안전자산 및 인플레이션 헤지 자산"},
            {"label": "금 현물 (한국)", "country": "한국 (KR)", "ticker": "411060.KS", "kr_input": "ACE KRX금현물", "desc": "국내 연금계좌에서 투자 가능한 금 현물"},
            {"label": "원자재 종합", "country": "미국 (US)", "ticker": "DBC", "kr_input": "", "desc": "에너지, 농산물, 금속 등 주요 원자재 추종"},
            {"label": "미국 부동산 리츠", "country": "미국 (US)", "ticker": "VNQ", "kr_input": "", "desc": "미국 상업용 부동산 및 리츠 투자"}
        ],
        "🏦 현금 및 외화": [
            {"label": "미국 초단기채 (현금성)", "country": "미국 (US)", "ticker": "BIL", "kr_input": "", "desc": "1-3개월 미공채 추종, 달러 현금 대용"},
            {"label": "한국 단기 통안채", "country": "한국 (KR)", "ticker": "157030.KS", "kr_input": "TIGER 단기통안채", "desc": "무위험 단기 채권, 안전 자금 대피처"},
            {"label": "KOFR 금리액티브", "country": "한국 (KR)", "ticker": "429870.KS", "kr_input": "KODEX KOFR금리액티브", "desc": "한국 무위험 지표금리 추종 초단기 파킹형"},
            {"label": "미국 달러선물 (한국)", "country": "한국 (KR)", "ticker": "261240.KS", "kr_input": "KODEX 미국달러선물", "desc": "원화 가치 하락 시 헤지용 달러 추종"}
        ]
    }
    
    tabs = st.tabs(list(categories.keys()))
    for tab, (cat_name, assets) in zip(tabs, categories.items()):
        with tab:
            st.markdown(f"##### {cat_name} 대표 리스트")
            for idx, item in enumerate(assets):
                col1, col2, col3, col4 = st.columns([2, 1, 3, 1])
                with col1:
                    st.markdown(f"**{item['label']}**")
                    st.caption(item['desc'])
                with col2:
                    st.write(item['country'])
                with col3:
                    if item['country'] == "미국 (US)":
                        st.code(item['ticker'])
                    else:
                        st.write(f"{item['kr_input']} (`{item['ticker'].split('.')[0]}`)")
                with col4:
                    if st.button("➕ 추가", key=f"add_rec_asset_{cat_name}_{idx}", use_container_width=True):
                        add_recommended_asset(item['country'], item['ticker'], item['kr_input'])
                        st.rerun()

def add_recommended_asset(asset_type, ticker, kr_input):
    for idx, asset in enumerate(st.session_state.assets):
        if not asset.get("ticker") and not asset.get("kr_input"):
            st.session_state[f"type_{idx}"] = asset_type
            if asset_type == "미국 (US)":
                st.session_state[f"ticker_{idx}"] = ticker
            else:
                st.session_state[f"kr_input_{idx}"] = kr_input
            st.session_state.assets[idx] = {
                "type": asset_type,
                "ticker": ticker,
                "kr_input": kr_input,
                "weight": asset.get("weight", 0.0)
            }
            st.toast(f"✅ 자산군 {idx+1}에 {kr_input if kr_input else ticker}를 추가했습니다.")
            return

    if len(st.session_state.assets) < 8:
        new_idx = len(st.session_state.assets)
        st.session_state[f"type_{new_idx}"] = asset_type
        if asset_type == "미국 (US)":
            st.session_state[f"ticker_{new_idx}"] = ticker
        else:
            st.session_state[f"kr_input_{new_idx}"] = kr_input
        st.session_state[f"weight_{new_idx}"] = 0.0
        st.session_state.assets.append({
            "type": asset_type,
            "ticker": ticker,
            "kr_input": kr_input,
            "weight": 0.0
        })
        st.toast(f"✅ 자산군 {new_idx+1}에 {kr_input if kr_input else ticker}를 추가했습니다.")
    else:
        st.error("⚠️ 슬롯이 모두 차 있습니다(최대 8개). 사용하지 않는 자산을 삭제해 주세요.")

KR_ASSET_MAPPING = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "KODEX 200": "069500.KS",
    "KODEX 레버리지": "122630.KS",
    "KODEX 인버스": "114800.KS",
    "KODEX 200선물인버스2X": "252670.KS",
    "TIGER 미국S&P500": "360750.KS",
    "TIGER 미국나스닥100": "133690.KS",
    "TIGER 미국필라델피아반도체나스닥": "381170.KS",
    "KODEX 국고채3년": "114260.KS",
    "TIGER 단기통안채": "157030.KS",
    "KODEX 미국달러선물": "261240.KS",
    "TIGER 미국배당다우존스": "456730.KS",
    "KOSEF 국고채10년": "148070.KS",
    "ACE KRX금현물": "411060.KS",
    "KODEX 골드선물(H)": "132030.KS",
    "KODEX KOFR금리액티브": "429870.KS",
    "KODEX 국고채30년액티브": "272580.KS"
}

@st.cache_data(show_spinner=False)
def get_listing_date(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="max")
        if not hist.empty:
            return hist.index[0].date()
    except Exception:
        pass
    return None

if 'assets' not in st.session_state:
    st.session_state.assets = [
        {"type": "미국 (US)", "ticker": "SPY", "kr_input": "", "weight": 60.0},
        {"type": "미국 (US)", "ticker": "TLT", "kr_input": "", "weight": 40.0}
    ]

st.title("📈 스마트 자산배분 & 리밸런싱 백테스터")
st.write("원하는 주식 및 ETF 자산군을 조합하여 과거 성과와 최대 낙폭(MDD), 리밸런싱 효과를 백테스팅해보세요.")

st.sidebar.header("⚙️ 시뮬레이션 설정")

col_btn1, col_btn2 = st.sidebar.columns(2)
with col_btn1:
    if st.button("💡 추천 포트폴리오", use_container_width=True, type="secondary"):
        show_recommendations_dialog()
with col_btn2:
    if st.button("🔍 추천 자산군 ETF", use_container_width=True, type="secondary"):
        show_asset_classes_dialog()

st.sidebar.markdown("---")

initial_capital_input = st.sidebar.number_input(
    "💵 초기 투자 금액 (₩)", 
    min_value=100000, 
    max_value=10000000000, 
    value=10000000, 
    step=1000000,
    help="백테스트를 시작할 원화 기준 초기 자본금입니다."
)

# 3자리 콤마 적용 확인 CAPTION
st.sidebar.caption(f"입력금액 확인: **₩{format_currency(initial_capital_input, digit_group=3)}**")

fee_pct_input = st.sidebar.slider(
    "💸 편도 거래 비용 (%)", 
    min_value=0.0, 
    max_value=2.0, 
    value=0.2, 
    step=0.05,
    help="자산군 매수/매도 시 발생하는 거래 수수료 및 세금 비율입니다."
)
fee_pct = fee_pct_input / 100.0

st.sidebar.subheader("📊 포트폴리오 자산 구성 (최대 8개)")

updated_assets = []
total_weight = 0.0
listing_dates = {}

for idx, asset in enumerate(st.session_state.assets):
    st.sidebar.markdown(f"**📍 자산군 {idx+1} 설정**")
    col1, col2, col3 = st.sidebar.columns([3, 2, 1])
    
    with col1:
        asset_type = st.selectbox(
            "국가 선택", 
            ["미국 (US)", "한국 (KR)"], 
            index=0 if asset.get("type", "미국 (US)") == "미국 (US)" else 1, 
            key=f"type_{idx}"
        )
        
        new_ticker = ""
        kr_input = ""
        
        if asset_type == "미국 (US)":
            new_ticker = st.text_input(
                "티커 입력", 
                value=asset.get("ticker", ""), 
                key=f"ticker_{idx}",
                help="예: SPY, QQQ, TLT, GLD, VNQ 등"
            ).upper().strip()
            st.caption("💡 추천: SPY, QQQ, TLT, GLD")
        else:
            kr_input = st.text_input(
                "종목명 또는 코드", 
                value=asset.get("kr_input", "KODEX 200"), 
                key=f"kr_input_{idx}",
                help="예: 삼성전자, KODEX 200, TIGER 미국S&P500 혹은 6자리 코드(069500)"
            ).strip()
            st.caption("💡 예: 삼성전자, KODEX 200, 069500")
            
            if kr_input.isdigit() and len(kr_input) == 6:
                new_ticker = f"{kr_input}.KS"
            elif kr_input in KR_ASSET_MAPPING:
                new_ticker = KR_ASSET_MAPPING[kr_input]
            else:
                cleaned_code = ''.join(filter(str.isdigit, kr_input))
                if len(cleaned_code) == 6:
                    new_ticker = f"{cleaned_code}.KS"
                else:
                    new_ticker = kr_input

    with col2:
        new_weight = st.number_input(f"비중 (%)", min_value=0.0, max_value=100.0, value=float(asset["weight"]), key=f"weight_{idx}", step=5.0)
        total_weight += new_weight
        
    with col3:
        if idx >= 2:
            st.write("")
            if st.button("❌", key=f"del_{idx}"):
                for prefix in ["type_", "ticker_", "kr_input_", "weight_"]:
                    if f"{prefix}{idx}" in st.session_state:
                        del st.session_state[f"{prefix}{idx}"]
                st.session_state.assets.pop(idx)
                st.rerun()
                
    if new_ticker:
        lst_date = get_listing_date(new_ticker)
        if lst_date:
            col1.caption(f"📅 연동 티커: **{new_ticker}** (상장: {lst_date})")
            listing_dates[new_ticker] = lst_date
        else:
            col1.caption("⚠️ 감지되지 않는 자산입니다. 올바른 티커/명칭인지 확인하세요.")
            
    updated_assets.append({
        "type": asset_type, 
        "ticker": new_ticker, 
        "kr_input": kr_input, 
        "weight": new_weight
    })

st.session_state.assets = updated_assets

if len(st.session_state.assets) < 8:
    if st.sidebar.button("➕ 자산군 추가"):
        st.session_state.assets.append({"type": "미국 (US)", "ticker": "", "kr_input": "", "weight": 0.0})
        st.rerun()
else:
    st.sidebar.warning("⚠️ 자산군은 최대 8개까지만 추가할 수 있습니다.")

st.sidebar.write(f"**현재 설정된 비중 합계:** {total_weight:.1f} %")
if total_weight == 100.0:
    st.sidebar.success("✅ 비중 합계가 100%입니다. 백테스팅을 진행할 수 있습니다.")
else:
    st.sidebar.error("❌ 비중의 합이 반드시 **100%**가 되어야 합니다.")

st.sidebar.subheader("📅 백테스팅 기간")

valid_listing_dates = [lst_date for lst_date in listing_dates.values() if lst_date is not None]
latest_listing_date = max(valid_listing_dates) if valid_listing_dates else date.today() - timedelta(days=365*10)

current_tickers = sorted([a["ticker"] for a in st.session_state.assets if a.get("ticker")])
if 'prev_tickers' not in st.session_state or st.session_state.prev_tickers != current_tickers:
    st.session_state.prev_tickers = current_tickers
    st.session_state.start_date_val = latest_listing_date
elif 'start_date_val' not in st.session_state:
    st.session_state.start_date_val = latest_listing_date

start_date = st.sidebar.date_input(
    "시작일", 
    value=st.session_state.start_date_val,
    min_value=date(1980, 1, 1),
    max_value=date.today()
)
st.session_state.start_date_val = start_date

end_date = st.sidebar.date_input(
    "종료일", 
    value=date.today(),
    min_value=date(1980, 1, 1),
    max_value=date.today()
)

for ticker, lst_date in listing_dates.items():
    if lst_date and lst_date > start_date:
        st.sidebar.warning(f"⚠️ {ticker} 상장일({lst_date})이 설정된 시작일보다 늦습니다. 기간을 조절해 주세요.")

st.sidebar.subheader("🔄 리밸런싱 정책")
rebalance_freq = st.sidebar.selectbox(
    "리밸런싱 주기",
    ["없음 (None)", "일별 (Daily)", "월별 (Monthly)", "분기별 (Quarterly)", "연별 (Annually)"],
    index=2
)

st.sidebar.info("ℹ️ 각 주기의 리밸런싱 거래일은 해당 주기(일/월/분기/년)의 **첫 주식거래일(영업일)** 기준입니다.")

if total_weight == 100.0 and all(a["ticker"] for a in st.session_state.assets):
    if st.sidebar.button("🚀 백테스팅 시작", type="primary"):
        with st.spinner("야후 파이낸스에서 데이터를 불러와 정밀 연산을 수행하고 있습니다..."):
            
            tickers = [a["ticker"] for a in st.session_state.assets]
            target_weights = {a["ticker"]: a["weight"] / 100.0 for a in st.session_state.assets}
            
            download_tickers = list(set(tickers + ["SPY"]))
            
            try:
                raw_data = yf.download(download_tickers, start=start_date, end=end_date, auto_adjust=True)
                
                if isinstance(raw_data.columns, pd.MultiIndex):
                    prices = raw_data['Close']
                else:
                    if 'Close' in raw_data.columns:
                        prices = raw_data[['Close']]
                        prices.columns = download_tickers
                    else:
                        prices = raw_data
                
                if isinstance(prices, pd.Series):
                    prices = prices.to_frame(name=download_tickers[0])
                    
                prices = prices.ffill().bfill()
            except Exception as e:
                st.error(f"데이터를 다운로드하는 중 오류가 발생했습니다: {e}")
                prices = pd.DataFrame()
            
            if not prices.empty:
                available_tickers = [t for t in tickers if t in prices.columns]
                if len(available_tickers) < len(tickers):
                    missing = set(tickers) - set(available_tickers)
                    st.error(f"일부 티커({missing})의 데이터가 존재하지 않아 백테스팅을 진행할 수 없습니다.")
                else:
                    spy_prices = prices["SPY"]
                    port_prices = prices[tickers]
                    
                    rebal_dates = []
                    if rebalance_freq == "일별 (Daily)":
                        rebal_dates = port_prices.index.tolist()
                    elif rebalance_freq == "월별 (Monthly)":
                        monthly_firsts = port_prices.groupby([port_prices.index.year, port_prices.index.month]).apply(lambda x: x.index[0], include_groups=False).values
                        rebal_dates = list(pd.to_datetime(monthly_firsts))
                    elif rebalance_freq == "분기별 (Quarterly)":
                        quarterly_firsts = port_prices.groupby([port_prices.index.year, (port_prices.index.month - 1) // 3]).apply(lambda x: x.index[0], include_groups=False).values
                        rebal_dates = list(pd.to_datetime(quarterly_firsts))
                    elif rebalance_freq == "연별 (Annually)":
                        yearly_firsts = port_prices.groupby(port_prices.index.year).apply(lambda x: x.index[0], include_groups=False).values
                        rebal_dates = list(pd.to_datetime(yearly_firsts))
                    
                    rebal_set = set(rebal_dates)
                    
                    initial_capital = float(initial_capital_input)
                    shares = {}
                    portfolio_values = []
                    
                    t0 = port_prices.index[0]
                    p0 = port_prices.loc[t0]
                    
                    total_initial_fees = 0.0
                    for ticker in tickers:
                        allocated_cash = initial_capital * target_weights[ticker]
                        fee = allocated_cash * fee_pct
                        total_initial_fees += fee
                        shares[ticker] = (allocated_cash - fee) / p0[ticker]
                    
                    portfolio_values.append(initial_capital - total_initial_fees)
                    
                    for t in port_prices.index[1:]:
                        pt = port_prices.loc[t]
                        current_portfolio_value = sum(shares[ticker] * pt[ticker] for ticker in tickers)
                        
                        if t in rebal_set:
                            current_vals = {ticker: shares[ticker] * pt[ticker] for ticker in tickers}
                            target_vals = {ticker: current_portfolio_value * target_weights[ticker] for ticker in tickers}
                            
                            trade_fees = sum(abs(target_vals[ticker] - current_vals[ticker]) * fee_pct for ticker in tickers)
                            rebalanced_portfolio_value = current_portfolio_value - trade_fees
                            
                            for ticker in tickers:
                                shares[ticker] = (rebalanced_portfolio_value * target_weights[ticker]) / pt[ticker]
                                
                            portfolio_values.append(rebalanced_portfolio_value)
                        else:
                            portfolio_values.append(current_portfolio_value)
                    
                    perf_df = pd.DataFrame(index=port_prices.index)
                    perf_df["Portfolio"] = portfolio_values
                    perf_df["SPY_Benchmark"] = (spy_prices / spy_prices.iloc[0]) * initial_capital
                    
                    def compute_metrics(series):
                        returns = series.pct_change().dropna()
                        total_ret = (series.iloc[-1] / series.iloc[0]) - 1
                        
                        days = (series.index[-1] - series.index[0]).days
                        years = days / 365.25
                        cagr = (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
                        
                        cum_max = series.cummax()
                        drawdowns = (series - cum_max) / cum_max
                        mdd = drawdowns.min()
                        
                        volatility = returns.std() * np.sqrt(252)
                        sharpe = (returns.mean() * 252) / volatility if volatility > 0 else 0
                        
                        return {
                            "total_return": total_ret,
                            "cagr": cagr,
                            "mdd": mdd,
                            "sharpe": sharpe,
                            "vol": volatility
                        }
                    
                    p_metrics = compute_metrics(perf_df["Portfolio"])
                    b_metrics = compute_metrics(perf_df["SPY_Benchmark"])
                    
                    st.subheader("📊 주요 성과 비교 대시보드 (vs 벤치마크 SPY)")
                    
                    port_final = perf_df["Portfolio"].iloc[-1]
                    spy_final = perf_df["SPY_Benchmark"].iloc[-1]
                    
                    compare_df = pd.DataFrame({
                        "지표": ["최종 자산", "연평균 수익률 (CAGR)", "최대 낙폭 (MDD)", "위험대비 수익률 (Sharpe)"],
                        "내 포트폴리오": [
                            f"₩{format_currency(port_final, 3)}",
                            f"{p_metrics['cagr']*100:.2f}%",
                            f"{p_metrics['mdd']*100:.2f}%",
                            f"{p_metrics['sharpe']:.2f}"
                        ],
                        "SPY 벤치마크": [
                            f"₩{format_currency(spy_final, 3)}",
                            f"{b_metrics['cagr']*100:.2f}%",
                            f"{b_metrics['mdd']*100:.2f}%",
                            f"{b_metrics['sharpe']:.2f}"
                        ],
                        "차이": [
                            f"₩{format_currency(port_final - spy_final, 3)}",
                            f"{(p_metrics['cagr'] - b_metrics['cagr'])*100:+.2f}%p",
                            f"{(p_metrics['mdd'] - b_metrics['mdd'])*100:+.2f}%p",
                            f"{(p_metrics['sharpe'] - b_metrics['sharpe']):+.2f}"
                        ]
                    })
                    st.table(compare_df.set_index("지표"))
                    
                    st.subheader("📈 누적 수익률 추이 비교")
                    normalized_df = (perf_df / initial_capital - 1) * 100
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=normalized_df.index, 
                        y=normalized_df["Portfolio"], 
                        mode='lines', 
                        name='내 자산배분 포트폴리오',
                        line=dict(color='#1f77b4', width=3)
                    ))
                    fig.add_trace(go.Scatter(
                        x=normalized_df.index, 
                        y=normalized_df["SPY_Benchmark"], 
                        mode='lines', 
                        name='S&P 500 (SPY) 벤치마크',
                        line=dict(color='#ff7f0e', width=1.5, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title="포트폴리오 vs 벤치마크 누적 수익률 추이 (%)",
                        xaxis_title="날짜",
                        yaxis_title="수익률 (%)",
                        hovermode="x unified",
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.subheader("🤝 구성 자산군 상관관계 분석 (Correlation Matrix)")
                    returns_df = port_prices.pct_change().dropna()
                    if not returns_df.empty:
                        corr_matrix = returns_df.corr()
                        
                        display_names = []
                        for asset in st.session_state.assets:
                            if asset["type"] == "한국 (KR)" and asset["kr_input"]:
                                display_names.append(f"{asset['kr_input']} ({asset['ticker']})")
                            else:
                                display_names.append(asset["ticker"])
                                
                        corr_matrix.columns = display_names
                        corr_matrix.index = display_names
                        
                        fig_corr = px.imshow(
                            corr_matrix,
                            text_auto=".2f",
                            color_continuous_scale="RdBu_r",
                            zmin=-1.0, zmax=1.0,
                            labels=dict(color="상관계수")
                        )
                        fig_corr.update_layout(
                            title="포트폴리오 자산군 간 일별 수익률 상관관계",
                            xaxis_title="",
                            yaxis_title="",
                            margin=dict(l=40, r=40, t=40, b=40)
                        )
                        st.plotly_chart(fig_corr, use_container_width=True)
                    else:
                        st.info("상관계수를 계산할 수 있는 거래 데이터가 충분하지 않습니다.")
                    
                    st.subheader("📂 자산군별 세부 지표")
                    raw_info = []
                    for idx, asset in enumerate(st.session_state.assets):
                        ticker = asset["ticker"]
                        t_series = port_prices[ticker]
                        t_ret = (t_series.iloc[-1] / t_series.iloc[0]) - 1
                        
                        label_name = asset["kr_input"] if asset["type"] == "한국 (KR)" and asset["kr_input"] else ticker
                        
                        raw_info.append({
                            "자산 구분": label_name,
                            "국가": asset["type"],
                            "티커 코드": ticker,
                            "목표 비중": f"{target_weights[ticker]*100:.1f}%",
                            "백테스트 기간 누적수익률": f"{t_ret*100:.2f}%",
                            "시작일 종가": f"${t_series.iloc[0]:.2f}" if asset["type"] == "미국 (US)" else f"₩{format_currency(t_series.iloc[0], 3)}",
                            "종료일 종가": f"${t_series.iloc[-1]:.2f}" if asset["type"] == "미국 (US)" else f"₩{format_currency(t_series.iloc[-1], 3)}"
                        })
                    st.table(pd.DataFrame(raw_info))
else:
    st.info("👈 왼쪽 사이드바에서 자산군을 구성하고 비중의 합을 **100%**로 맞춘 후 **🚀 백테스팅 시작** 버튼을 눌러주세요.")

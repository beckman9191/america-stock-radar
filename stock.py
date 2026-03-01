import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data(ttl=86400)
def fetch_all_us_tickers():
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return {f"{item['ticker']} - {item['title'].title()}": item['ticker'] for item in data.values()}
    except:
        return {f"{t}": t for t in ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "COIN", "CRCL", "UPST", "RDDT"]}

@st.cache_data(ttl=3600)
def load_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df

def process_us_strategy(df, ticker, display_days):
    # 保护性拦截：只有少于20天的数据连基础波幅都算不出，才直接跳过
    if len(df) <= 20:
        return df, [], [], [], []

    # 1. 核心指标流水线计算
    delta = df['Close'].diff()
    rs = delta.clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI_14'] = 100 - (100 / (1 + rs))

    high_14 = df['High'].rolling(14).max()
    low_14 = df['Low'].rolling(14).min()
    df['WMSR_14'] = -100 * (high_14 - df['Close']) / (high_14 - low_14)

    df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / df['Vol_SMA_20']

    # 🌟 双均线计算 (次新股自适应) 🌟
    df['SMA_20'] = df['Close'].rolling(20).mean()
    if len(df) < 200:
        df['SMA_200'] = df['Close'].expanding().mean() # 不满200天用上市至今均线
    else:
        df['SMA_200'] = df['Close'].rolling(200).mean()

    # 🌟 ATR动态波幅计算 🌟
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift(1))
    low_close = np.abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR_20'] = tr.rolling(20).mean()
    df['ATR_Ratio'] = (df['Close'] - df['SMA_20']) / df['ATR_20']

    # ==========================================
    # 🟢 基础左侧买入信号判定
    # ==========================================
    bull_dip = (df['Close'] >= df['SMA_200']) & (df['ATR_Ratio'] < -2.0)
    bear_plunge = (df['Close'] < df['SMA_200']) & (df['ATR_Ratio'] < -3.0)

    df['Buy_Base_Signal'] = (
        (df['RSI_14'] < 30) &
        (df['WMSR_14'] < -90) &
        (df['Vol_Spike'] > 1.2) &
        (bull_dip | bear_plunge)
    ).astype(int)

    valid_buy_indices = []
    last_buy_price = None
    last_buy_idx = None
    PRICE_STEP = 0.90
    RESET_DAYS = 30

    for i in range(len(df)):
        if df['Buy_Base_Signal'].iloc[i] == 1:
            current_price = df['Close'].iloc[i]
            if last_buy_idx is not None and (i - last_buy_idx) > RESET_DAYS:
                last_buy_price = None

            if last_buy_price is None:
                valid_buy_indices.append(i)
                last_buy_price = current_price
                last_buy_idx = i
            else:
                if current_price <= last_buy_price * PRICE_STEP:
                    valid_buy_indices.append(i)
                    last_buy_price = current_price
                    last_buy_idx = i

    # ==========================================
    # 🔴 卖出逃顶信号判定
    # ==========================================
    RSI_SELL_THRESHOLD = 75
    VOL_SPIKE_SELL = 2.0
    ATR_SELL_THRESHOLD = 2.0
    WMSR_SELL_THRESHOLD = -15

    df['Sell_Base_Signal'] = (
        (df['RSI_14'] > RSI_SELL_THRESHOLD) &
        (df['Vol_Spike'] > VOL_SPIKE_SELL) &
        (df['ATR_Ratio'] > ATR_SELL_THRESHOLD) &
        (df['WMSR_14'] > WMSR_SELL_THRESHOLD)
    ).astype(int)

    valid_sell_indices = []
    last_sell_price = None
    last_sell_idx = None
    SELL_PRICE_STEP = 1.10
    SELL_RESET_DAYS = 20

    for i in range(len(df)):
        if df['Sell_Base_Signal'].iloc[i] == 1:
            current_price = df['Close'].iloc[i]
            if last_sell_idx is not None and (i - last_sell_idx) > SELL_RESET_DAYS:
                last_sell_price = None
            if last_sell_price is None:
                valid_sell_indices.append(i)
                last_sell_price = current_price
                last_sell_idx = i
            else:
                if current_price >= last_sell_price * SELL_PRICE_STEP:
                    valid_sell_indices.append(i)
                    last_sell_price = current_price
                    last_sell_idx = i

    # ==========================================
    # 提取信号与打标签
    # ==========================================
    cutoff_date = datetime.today().date() - timedelta(days=display_days)
    buy_records, sell_records = [], []
    is_new_stock = len(df) < 200
    
    for idx in valid_buy_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            phase = "Uptrend" if row['Close'] >= row['SMA_200'] else "Downtrend"
            if is_new_stock:
                phase += " (不满200天)"
            buy_records.append({'Date': date.date(), 'Ticker': ticker, 'Action': 'BUY', 'Phase': phase, 'Close': round(row['Close'], 2), 'RSI': round(row['RSI_14'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})
            
    for idx in valid_sell_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            sell_records.append({'Date': date.date(), 'Ticker': ticker, 'Action': 'SELL', 'Close': round(row['Close'], 2), 'RSI': round(row['RSI_14'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})

    return df, valid_buy_indices, valid_sell_indices, buy_records, sell_records

def plot_candlestick_plotly(df, ticker, valid_buy_indices, valid_sell_indices, display_days):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='K线', increasing_line_color='green', decreasing_line_color='red'
    ), row=1, col=1)
    
    if 'SMA_20' in df.columns: 
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA20'), row=1, col=1)
    
    is_new_stock = len(df) < 200
    sma200_name = f"均线_上市至今({len(df)}天)" if is_new_stock else "SMA200"
    if 'SMA_200' in df.columns: 
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='orange', width=2), name=sma200_name), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)

    if valid_buy_indices:
        buy_dates = df.iloc[valid_buy_indices].index
        buy_prices = df['Low'].iloc[valid_buy_indices] * 0.95
        fig.add_trace(go.Scatter(x=buy_dates, y=buy_prices, mode='markers', marker=dict(symbol='triangle-up', color='magenta', size=16, line=dict(color='black', width=1.5)), name='BUY (买入)'), row=1, col=1)
        
    if valid_sell_indices:
        sell_dates = df.iloc[valid_sell_indices].index
        sell_prices = df['High'].iloc[valid_sell_indices] * 1.05
        fig.add_trace(go.Scatter(x=sell_dates, y=sell_prices, mode='markers', marker=dict(symbol='triangle-down', color='cyan', size=16, line=dict(color='black', width=1.5)), name='SELL (卖出)'), row=1, col=1)

    # 动态 Y 轴缩放
    zoom_start = pd.Timestamp.today() - pd.Timedelta(days=display_days)
    fig.update_xaxes(range=[zoom_start, df.index[-1]])
    
    visible_df = df[df.index >= zoom_start]
    if not visible_df.empty:
        y_max, y_min = visible_df['High'].max(), visible_df['Low'].min()
        if 'SMA_20' in visible_df.columns and not visible_df['SMA_20'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_20'].dropna().max()), min(y_min, visible_df['SMA_20'].dropna().min())
        if 'SMA_200' in visible_df.columns and not visible_df['SMA_200'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_200'].dropna().max()), min(y_min, visible_df['SMA_200'].dropna().min())
        padding = (y_max - y_min) * 0.05
        if padding == 0: padding = y_max * 0.05
        fig.update_yaxes(range=[y_min - padding, y_max + padding], row=1, col=1)

    title_suffix = f" (⚠️上市仅 {len(df)} 天，大势过滤降级为上市至今全局均线)" if is_new_stock else ""
    fig.update_layout(title=f"{ticker} 走势与信号{title_suffix}", xaxis_rangeslider_visible=False, height=600, template="plotly_white")
    return fig

def render_stock_page():
    st.title("📡 美股：双均线大势过滤 + ATR动态波幅")
    ticker_dict = fetch_all_us_tickers()
    
    st.sidebar.header("参数配置 (美股)")
    default_selections = [k for k, v in ticker_dict.items() if v in ["COIN", "CRCL", "UNH", "UPST", "RDDT", "CRWV", "NVDA", "TSLA"]]
    selected_display = st.sidebar.multiselect("🔎 搜索美股标的", options=list(ticker_dict.keys()), default=default_selections)
    selected_stocks = [ticker_dict[k] for k in selected_display]

    custom_tickers = st.sidebar.text_input("➕ 手动添加美股代码 (用逗号分隔)", "")
    if custom_tickers:
        selected_stocks.extend([t.strip().upper() for t in custom_tickers.split(",") if t.strip()])
        selected_stocks = list(set(selected_stocks))

    display_days = st.sidebar.number_input("📉 图表展示与信号提取天数", min_value=7, max_value=2000, value=300, step=10)

    if st.button("🚀 开始执行美股扫描", type="primary"):
        if not selected_stocks: 
            st.warning("⚠️ 请至少选择一只股票进行扫描！")
            st.stop()
            
        start_date = (datetime.today() - timedelta(days=max(730, display_days + 300))).strftime('%Y-%m-%d')
        end_date = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        all_buys, all_sells, charts_rendered = [], [], []
        my_bar = st.progress(0, text="正在初始化雷达...")
        tab1, tab2 = st.tabs(["📋 交易信号汇总", "📈 K线走势图表"])

        for i, ticker in enumerate(selected_stocks):
            my_bar.progress((i + 1) / len(selected_stocks), text=f"正在分析 {ticker} ...")
            try:
                df = load_data(ticker, start_date, end_date)
                if len(df) <= 20: 
                    st.toast(f"⚠️ {ticker} 数据不足20天，已跳过。", icon='⚠️')
                    continue
                df, v_buy, v_sell, buys, sells = process_us_strategy(df, ticker, display_days)
                all_buys.extend(buys); all_sells.extend(sells)
                charts_rendered.append(plot_candlestick_plotly(df, ticker, v_buy, v_sell, display_days))
            except Exception as e: 
                st.error(f"处理 {ticker} 时出错: {e}")
                
        my_bar.empty()

        with tab1:
            st.subheader("🚨 指定展示期内【大底买入】信号")
            if all_buys: 
                st.dataframe(pd.DataFrame(all_buys).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info("展示期内未触发买入信号。")
                
            st.subheader("🎯 指定展示期内【高位逃顶】信号")
            if all_sells: 
                st.dataframe(pd.DataFrame(all_sells).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info("展示期内未触发卖出信号。")

        with tab2:
            for fig in charts_rendered: 
                st.plotly_chart(fig, use_container_width=True)
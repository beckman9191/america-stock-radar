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
    # 🛡️ 第一重防御：尝试读取你上传的 JSON 文件（全量 10000+ 只）
    try:
        import json
        import os
        if os.path.exists('company_tickers.json'):
            with open('company_tickers.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {f"{item['ticker']} - {item['title'].title()}": item['ticker'] for item in data.values()}
    except Exception:
        pass

    # 🛡️ 终极兜底：如果没有 JSON 文件，直接返回备用精选池
    st.sidebar.warning("⚠️ 未检测到全市场股票字典(company_tickers.json)，已降级为精选备用池。")
    fallback = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "COIN", "CRCL", "UPST", "RDDT", "CRWV"]
    return {f"{t}": t for t in fallback}

@st.cache_data(ttl=3600)
def load_data(ticker, start_date, end_date):
    # 强制让 yfinance 不要保留无关的时区信息和空行
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, ignore_tz=True)
    
    # 防御 1：如果雅虎抽风返回空数据，不要犹豫，直接返回空DF，后面会拦截
    if df.empty:
        return df
        
    # 处理多层表头
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df.index = pd.to_datetime(df.index)
    
    # 🌟 防御 2：彻底剔除雅虎给次新股填充的无聊 NaN 空行！
    # 如果某一天这只股票根本没收盘价（比如还没上市），直接把这行砍掉
    df = df.dropna(subset=['Close'])
    
    return df

def process_us_strategy(df, ticker, display_days):
    if len(df) <= 20:
        return df, [], [], [], []

    delta = df['Close'].diff()
    rs = delta.clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI_14'] = 100 - (100 / (1 + rs))

    high_14 = df['High'].rolling(14).max()
    low_14 = df['Low'].rolling(14).min()
    df['WMSR_14'] = -100 * (high_14 - df['Close']) / (high_14 - low_14)

    df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / df['Vol_SMA_20']

    df['SMA_20'] = df['Close'].rolling(20).mean()
    if len(df) < 200:
        df['SMA_200'] = df['Close'].expanding().mean()
    else:
        df['SMA_200'] = df['Close'].rolling(200).mean()

    tr = pd.concat([df['High']-df['Low'], np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
    df['ATR_20'] = tr.rolling(20).mean()
    df['ATR_Ratio'] = (df['Close'] - df['SMA_20']) / df['ATR_20']

    bull_dip = (df['Close'] >= df['SMA_200']) & (df['ATR_Ratio'] < -2.0)
    bear_plunge = (df['Close'] < df['SMA_200']) & (df['ATR_Ratio'] < -3.0)

    RSI_BUY_THRESHOLD = 30
    VOL_SPIKE_BUY = 1.2
    WMSR_BUY_THRESHOLD = -90

    df['Buy_Base_Signal'] = (
        (df['RSI_14'] < RSI_BUY_THRESHOLD) &
        (df['WMSR_14'] < WMSR_BUY_THRESHOLD) &
        (df['Vol_Spike'] > VOL_SPIKE_BUY) &
        (bull_dip | bear_plunge)
    ).astype(int)

    valid_buy_indices, last_buy_price, last_buy_idx = [], None, None
    for i in range(len(df)):
        if df['Buy_Base_Signal'].iloc[i] == 1:
            curr_p = df['Close'].iloc[i]
            if last_buy_idx is not None and (i - last_buy_idx) > 30: last_buy_price = None
            if last_buy_price is None or curr_p <= last_buy_price * 0.90:
                valid_buy_indices.append(i); last_buy_price, last_buy_idx = curr_p, i

    RSI_SELL_THRESHOLD = 75
    VOL_SPIKE_SELL = 2.0
    ATR_SELL_THRESHOLD = 2.0
    WMSR_SELL_THRESHOLD = -10

    df['Sell_Base_Signal'] = (
        (df['RSI_14'] > RSI_SELL_THRESHOLD) & 
        (df['Vol_Spike'] > VOL_SPIKE_SELL) & 
        (df['ATR_Ratio'] > ATR_SELL_THRESHOLD) & 
        (df['WMSR_14'] > WMSR_SELL_THRESHOLD)
        ).astype(int)
    
    valid_sell_indices, last_sell_price, last_sell_idx = [], None, None
    for i in range(len(df)):
        if df['Sell_Base_Signal'].iloc[i] == 1:
            curr_p = df['Close'].iloc[i]
            if last_sell_idx is not None and (i - last_sell_idx) > 20: last_sell_price = None
            if last_sell_price is None or curr_p >= last_sell_price * 1.10:
                valid_sell_indices.append(i); last_sell_price, last_sell_idx = curr_p, i

    cutoff_date = datetime.today().date() - timedelta(days=display_days)
    buy_records, sell_records = [], []
    is_new_stock = len(df) < 200
    
    for idx in valid_buy_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            phase = "Uptrend" if row['Close'] >= row['SMA_200'] else "Downtrend"
            if is_new_stock: phase += " (不满200天)"
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
        buy_draw_prices = df['Low'].iloc[valid_buy_indices] * 0.95 # 画图的视觉 Y 坐标（防遮挡）
        real_buy_prices = df['Close'].iloc[valid_buy_indices]      # 悬停显示的真实收盘价
        
        fig.add_trace(go.Scatter(
            x=buy_dates, 
            y=buy_draw_prices, 
            mode='markers', 
            marker=dict(symbol='triangle-up', color='magenta', size=16, line=dict(color='black', width=1.5)), 
            name='BUY (买入)',
            customdata=real_buy_prices, # 把真实价格传给底层
            hovertemplate='<b>大底买入</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>'
        ), row=1, col=1)
        
    if valid_sell_indices:
        sell_dates = df.iloc[valid_sell_indices].index
        sell_draw_prices = df['High'].iloc[valid_sell_indices] * 1.05 # 画图的视觉 Y 坐标（防遮挡）
        real_sell_prices = df['Close'].iloc[valid_sell_indices]       # 悬停显示的真实收盘价
        
        fig.add_trace(go.Scatter(
            x=sell_dates, 
            y=sell_draw_prices, 
            mode='markers', 
            marker=dict(symbol='triangle-down', color='cyan', size=16, line=dict(color='black', width=1.5)), 
            name='SELL (卖出)',
            customdata=real_sell_prices, # 把真实价格传给底层
            hovertemplate='<b>高位逃顶</b><br>日期: %{x|%Y-%m-%d}<br>真实逃顶价(收盘): %{customdata:.2f}<extra></extra>'
        ), row=1, col=1)

    zoom_start = pd.Timestamp.today() - pd.Timedelta(days=display_days)
    # 🌟 核心修复：给右侧强制留出 5 天的空白缓冲区，防止今天的信号被切掉
    zoom_end = df.index[-1] + pd.Timedelta(days=5)
    fig.update_xaxes(range=[zoom_start, zoom_end])
    
    visible_df = df[df.index >= zoom_start]
    if not visible_df.empty:
        y_max, y_min = visible_df['High'].max(), visible_df['Low'].min()
        
        # 1. 包容均线
        if 'SMA_20' in visible_df.columns and not visible_df['SMA_20'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_20'].dropna().max()), min(y_min, visible_df['SMA_20'].dropna().min())
        if 'SMA_200' in visible_df.columns and not visible_df['SMA_200'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_200'].dropna().max()), min(y_min, visible_df['SMA_200'].dropna().min())
            
        # 🌟 2. 核心修复：包容那些被偏移了 5% 的买卖点三角形
        visible_buys = [idx for idx in valid_buy_indices if df.index[idx] >= zoom_start]
        if visible_buys:
            # 找到可视范围内最低的那个买点三角形的 y 坐标
            min_buy_marker = (df['Low'].iloc[visible_buys] * 0.95).min()
            y_min = min(y_min, min_buy_marker) # 如果它更低，就把它设为 y 轴下限
            
        visible_sells = [idx for idx in valid_sell_indices if df.index[idx] >= zoom_start]
        if visible_sells:
            # 找到可视范围内最高的那个卖点三角形的 y 坐标
            max_sell_marker = (df['High'].iloc[visible_sells] * 1.05).max()
            y_max = max(y_max, max_sell_marker) # 如果它更高，就把它设为 y 轴上限

        # 3. 再加上少许边界留白，防止紧贴边缘
        padding = (y_max - y_min) * 0.05
        if padding == 0: padding = y_max * 0.05
        fig.update_yaxes(range=[y_min - padding, y_max + padding], row=1, col=1)

    title_suffix = f" (⚠️上市仅 {len(df)} 天，大势过滤降级为上市至今全局均线)" if is_new_stock else ""
    fig.update_layout(title=f"{ticker} 走势与信号{title_suffix}", xaxis_rangeslider_visible=False, height=600, template="plotly_white")
    return fig


def render_stock_page():
    st.title("📡 美股量化雷达：双均线过滤 + 全市场寻宝")
    
    ticker_dict = fetch_all_us_tickers()
    
    # ========================================================
    # 🌟 修复：直接初始化并严格绑定 multi_select_ui 到 session_state
    # ========================================================
    if "multi_select_ui" not in st.session_state:
        # 初次加载时的默认精选股
        st.session_state["multi_select_ui"] = [k for k, v in ticker_dict.items() if v in ["COIN", "CRCL", "UNH", "UPST", "RDDT", "CRWV", "NVDA", "TSLA"]]
    
    # ------------------ 左侧边栏：一键寻宝区 ------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔮 一键全市场寻宝")
    st.sidebar.caption("自动扫描字典内股票，把近期出现【大底买入】信号的标的追加到搜索框。")
    
    scan_days = st.sidebar.number_input("寻找最近 N 天内的买点", min_value=1, max_value=60, value=15)
    scan_limit = st.sidebar.number_input("最大扫描数量 (按首字母顺序)", min_value=100, max_value=20000, value=1000, step=500)

    if st.sidebar.button("⚡ 开始自动全市场扫雷", type="secondary"):
        with st.spinner(f"正在启动雅虎财经批量下载核心，准备扫描 {scan_limit} 只股票..."):
            found_keys = []
            scan_items = list(ticker_dict.items())[:scan_limit]
            
            start_scan = (datetime.today() - timedelta(days=500)).strftime('%Y-%m-%d')
            end_scan = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            tickers_to_dl = [v for k, v in scan_items]
            
            try:
                bulk_df = yf.download(tickers_to_dl, start=start_scan, end=end_scan, group_by='ticker', threads=True, progress=False)
                
                my_bar = st.sidebar.progress(0)
                status_text = st.sidebar.empty()
                
                for i, (key, ticker) in enumerate(scan_items):
                    my_bar.progress((i + 1) / len(scan_items))
                    status_text.text(f"正在研判: {i+1}/{len(scan_items)} ({ticker})")
                    
                    try:
                        if len(tickers_to_dl) == 1:
                            df_single = bulk_df.copy()
                        else:
                            df_single = bulk_df[ticker].copy()
                            
                        df_single.dropna(how='all', inplace=True)
                        
                        if len(df_single) > 200: 
                            _, _, _, buy_records, _ = process_us_strategy(df_single, ticker, scan_days)
                            if buy_records:
                                found_keys.append(key)
                    except Exception:
                        continue
                        
                my_bar.empty()
                status_text.empty()
                
                if found_keys:
                    # 🌟 修复逻辑：将新发现的股票【追加】到当前的搜索框中，并利用字典特性去重，保持插入顺序
                    current_selections = st.session_state["multi_select_ui"]
                    new_selections = list(dict.fromkeys(current_selections + found_keys))
                    
                    # 直接修改绑定的 key
                    st.session_state["multi_select_ui"] = new_selections
                    st.sidebar.success(f"🎉 寻宝完成！共发现 {len(found_keys)} 只标的，已自动追加至下方搜索框！")
                    st.rerun() # 强制刷新页面，让 UI 组件重绘
                else:
                    st.sidebar.info("未发现符合条件的标的，可能近期无底可抄，或请尝试加大扫描数量。")
                    
            except Exception as e:
                st.sidebar.error(f"批量下载失败: {e}")

    st.sidebar.markdown("---")
    
    # ------------------ 左侧边栏：常规分析区 ------------------
    st.sidebar.header("🎯 图表分析配置")
    
    # 🌟 修复逻辑：干掉 default，直接绑定 key。Streamlit 会自动拿 session_state["multi_select_ui"] 的值作为填充内容
    selected_display = st.sidebar.multiselect(
        "🔎 搜索美股标的 (支持全市场动态搜索)", 
        options=list(ticker_dict.keys()), 
        key="multi_select_ui", 
        help="请点击输入框，直接打字输入你要找的股票代码或公司名称进行动态筛选。"
    )
    
    selected_stocks = [ticker_dict[k] for k in selected_display]

    custom_tickers = st.sidebar.text_input("➕ 找不到？手动添加美股代码 (用逗号分隔)", "")
    if custom_tickers:
        selected_stocks.extend([t.strip().upper() for t in custom_tickers.split(",") if t.strip()])
        selected_stocks = list(set(selected_stocks))

    display_days = st.sidebar.number_input("📉 图表展示与信号提取天数", min_value=7, max_value=3000, value=300, step=10)

    # ------------------ 右侧主内容区 ------------------
    if st.button("🚀 开始生成图表与信号流水", type="primary"):
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






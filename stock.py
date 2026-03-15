import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 🌐 多语言翻译字典 (i18n)
# ==========================================
LANG_DICT = {
    "CN": {
        "title": "📡 美股量化雷达：双均线过滤 + 全市场寻宝",
        "dict_warning": "⚠️ 未检测到全市场股票字典(company_tickers.json)，已降级为精选备用池。",
        "less_than_200": " (不满200天)",
        "trend_up": "Uptrend",
        "trend_down": "Downtrend",
        "chart_title_suffix": " (⚠️上市仅 {days} 天，大势过滤降级为上市至今全局均线)",
        "trend_signals": "{ticker} 走势与信号",
        #"buy": "BUY (买入)",
        "sell": "SELL (卖出)",
        #"hover_buy": "<b>大底买入</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>",
        "hover_sell": "<b>高位逃顶</b><br>日期: %{x|%Y-%m-%d}<br>真实逃顶价(收盘): %{customdata:.2f}<extra></extra>",
        "buy_bull": "BUY (牛市回调)",
        "buy_bear": "BUY (熊市暴跌)",
        "hover_buy_bull": "<b>牛市回调买入</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>",
        "hover_buy_bear": "<b>熊市暴跌接刀</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>",
        "scanner_header": "🔮 一键全市场寻宝",
        "scanner_cap": "自动扫描字典内股票，把近期出现【大底买入】信号的标的追加到搜索框。",
        "scan_days": "寻找最近 N 天内的买点",
        "scan_limit": "最大扫描数量 (按首字母顺序)",
        "btn_scan": "⚡ 开始自动全市场扫雷",
        "spin_scan": "正在启动雅虎财经批量下载核心，准备扫描 {limit} 只股票...",
        "status_eval": "正在研判: {current}/{total} ({ticker})",
        "scan_success": "🎉 寻宝完成！共发现 {count} 只标的，已自动追加至下方搜索框！",
        "scan_fail": "未发现符合条件的标的，可能近期无底可抄，或请尝试加大扫描数量。",
        "err_dl": "批量下载失败: {e}",
        "config_header": "🎯 图表分析配置",
        "search_label": "🔎 搜索美股标的 (支持全市场动态搜索)",
        "search_help": "请点击输入框，直接打字输入你要找的股票代码或公司名称进行动态筛选。",
        "manual_add": "➕ 找不到？手动添加美股代码 (用逗号分隔)",
        "display_days": "📉 图表展示与信号提取天数",
        "btn_generate": "🚀 开始生成图表与信号流水",
        "warn_empty": "⚠️ 请至少选择一只股票进行扫描！",
        "prog_init": "正在初始化雷达...",
        "prog_analyze": "正在分析 {ticker} ...",
        "toast_skip": "⚠️ {ticker} 数据不足20天，已跳过。",
        "err_process": "处理 {ticker} 时出错: {e}",
        "tab_logs": "📋 交易信号汇总",
        "tab_charts": "📈 K线走势图表",
        "sub_buy": "🚨 指定展示期内【大底买入】信号",
        "info_no_buy": "展示期内未触发买入信号。",
        "sub_sell": "🎯 指定展示期内【高位逃顶】信号",
        "info_no_sell": "展示期内未触发卖出信号。"
    },
    "EN": {
        "title": "📡 US Stocks Quant Radar: Dual MA + Scanner",
        "dict_warning": "⚠️ Dictionary 'company_tickers.json' not found. Downgraded to fallback pool.",
        "less_than_200": " (<200 Days)",
        "trend_up": "Uptrend",
        "trend_down": "Downtrend",
        "chart_title_suffix": " (⚠️Listed only {days} days, SMA downgraded to Since-IPO)",
        "trend_signals": "{ticker} Trend & Signals",
        #"buy": "BUY",
        "sell": "SELL",
        #"hover_buy": "<b>Bottom Buy</b><br>Date: %{x|%Y-%m-%d}<br>Trigger Price (Close): %{customdata:.2f}<extra></extra>",
        "hover_sell": "<b>Top Sell</b><br>Date: %{x|%Y-%m-%d}<br>Escape Price (Close): %{customdata:.2f}<extra></extra>",
        "buy_bull": "BUY (Bull Dip)",
        "buy_bear": "BUY (Bear Plunge)",
        "hover_buy_bull": "<b>Bull Market Dip Buy</b><br>Date: %{x|%Y-%m-%d}<br>Trigger Price: %{customdata:.2f}<extra></extra>",
        "hover_buy_bear": "<b>Bear Market Plunge Buy</b><br>Date: %{x|%Y-%m-%d}<br>Trigger Price: %{customdata:.2f}<extra></extra>",
        "scanner_header": "🔮 One-Click Market Scanner",
        "scanner_cap": "Auto-scan dictionary and append stocks with recent 'Bottom Buy' signals to the search box.",
        "scan_days": "Scan for buys within last N days",
        "scan_limit": "Max scan limit (Alphabetical)",
        "btn_scan": "⚡ Start Auto Market Scanner",
        "spin_scan": "Starting Yahoo Finance bulk download for {limit} stocks...",
        "status_eval": "Analyzing: {current}/{total} ({ticker})",
        "scan_success": "🎉 Scan complete! Found {count} targets, auto-appended to the search box below!",
        "scan_fail": "No matching targets found. Market might be hot, or try increasing the scan limit.",
        "err_dl": "Bulk download failed: {e}",
        "config_header": "🎯 Chart Configurations",
        "search_label": "🔎 Search US Stocks (Dynamic market search)",
        "search_help": "Click the input box and type a ticker or company name to filter dynamically.",
        "manual_add": "➕ Not found? Add tickers manually (comma separated)",
        "display_days": "📉 Chart Display & Signal Extraction Days",
        "btn_generate": "🚀 Generate Charts & Signal Logs",
        "warn_empty": "⚠️ Please select at least one stock to scan!",
        "prog_init": "Initializing Radar...",
        "prog_analyze": "Analyzing {ticker}...",
        "toast_skip": "⚠️ {ticker} has less than 20 days of data, skipped.",
        "err_process": "Error processing {ticker}: {e}",
        "tab_logs": "📋 Trading Signals Summary",
        "tab_charts": "📈 Candlestick Charts",
        "sub_buy": "🚨 'Bottom Buy' Signals in Range",
        "info_no_buy": "No buy signals triggered in range.",
        "sub_sell": "🎯 'Top Sell' Signals in Range",
        "info_no_sell": "No sell signals triggered in range."
    }
}

def get_t():
    """获取当前语言包"""
    lang = st.session_state.get('lang', 'CN')
    return LANG_DICT.get(lang, LANG_DICT['CN'])

@st.cache_data(ttl=86400)
def fetch_all_us_tickers(lang):
    t = LANG_DICT.get(lang, LANG_DICT['CN'])
    try:
        import json
        import os
        if os.path.exists('company_tickers.json'):
            with open('company_tickers.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {f"{item['ticker']} - {item['title'].title()}": item['ticker'] for item in data.values()}
    except Exception:
        pass

    st.sidebar.warning(t["dict_warning"])
    fallback = ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "COIN", "CRCL", "UPST", "RDDT", "CRWV"]
    return {f"{t}": t for t in fallback}

@st.cache_data(ttl=3600)
def load_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, ignore_tz=True)
    
    # 🌟 终极防御：如果雅虎返回空数据或数据太少，直接“掀桌子”抛出异常！
    # 这样 Streamlit 就【绝对不会】把这个失败的空结果存进缓存里！
    if df is None or df.empty or len(df) <= 20:
        raise ValueError("雅虎财经暂时未返回有效数据 (可能遭遇网络波动或限流)")
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    df.index = pd.to_datetime(df.index)
    df = df.dropna(subset=['Close'])
    
    return df

def process_us_strategy(df, ticker, display_days):
    t = get_t()
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
            phase = t["trend_up"] if row['Close'] >= row['SMA_200'] else t["trend_down"]
            if is_new_stock: phase += t["less_than_200"]
            buy_records.append({'Date': date.date(), 'Ticker': ticker, 'Action': 'BUY', 'Phase': phase, 'Close': round(row['Close'], 2), 'RSI': round(row['RSI_14'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})
            
    for idx in valid_sell_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            sell_records.append({'Date': date.date(), 'Ticker': ticker, 'Action': 'SELL', 'Close': round(row['Close'], 2), 'RSI': round(row['RSI_14'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})

    return df, valid_buy_indices, valid_sell_indices, buy_records, sell_records

def plot_candlestick_plotly(df, ticker, valid_buy_indices, valid_sell_indices, display_days):
    t = get_t()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='Candle', increasing_line_color='green', decreasing_line_color='red'
    ), row=1, col=1)
    
    if 'SMA_20' in df.columns: 
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA20'), row=1, col=1)
    
    is_new_stock = len(df) < 200
    sma200_name = f"SMA_ALL({len(df)}d)" if is_new_stock else "SMA200"
    if 'SMA_200' in df.columns: 
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='orange', width=2), name=sma200_name), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)

    # =========================================================
    # 🌟 核心升级：拆分牛熊买点，使用不同颜色和提示语
    # =========================================================
    if valid_buy_indices:
        # 分离牛市和熊市的买点索引
        bull_buys = [idx for idx in valid_buy_indices if df['Close'].iloc[idx] >= df['SMA_200'].iloc[idx]]
        bear_buys = [idx for idx in valid_buy_indices if df['Close'].iloc[idx] < df['SMA_200'].iloc[idx]]
        
        # 1. 绘制牛市回调买点 (洋红色)
        if bull_buys:
            buy_dates_bull = df.iloc[bull_buys].index
            buy_draw_prices_bull = df['Low'].iloc[bull_buys] * 0.95 
            real_buy_prices_bull = df['Close'].iloc[bull_buys]      
            
            fig.add_trace(go.Scatter(
                x=buy_dates_bull, 
                y=buy_draw_prices_bull, 
                mode='markers', 
                marker=dict(symbol='triangle-up', color='magenta', size=16, line=dict(color='black', width=1.5)), 
                name=t.get("buy_bull", "BUY (Bull)"),
                customdata=real_buy_prices_bull,
                hovertemplate=t.get("hover_buy_bull", "<b>Bull Buy</b><br>Date: %{x|%Y-%m-%d}<br>Price: %{customdata:.2f}<extra></extra>")
            ), row=1, col=1)
            
        # 2. 绘制熊市暴跌买点 (显眼的暗金/橙色，警示风险)
        if bear_buys:
            buy_dates_bear = df.iloc[bear_buys].index
            buy_draw_prices_bear = df['Low'].iloc[bear_buys] * 0.95 
            real_buy_prices_bear = df['Close'].iloc[bear_buys]      
            
            fig.add_trace(go.Scatter(
                x=buy_dates_bear, 
                y=buy_draw_prices_bear, 
                mode='markers', 
                marker=dict(symbol='triangle-up', color='darkorange', size=16, line=dict(color='black', width=1.5)), 
                name=t.get("buy_bear", "BUY (Bear)"),
                customdata=real_buy_prices_bear,
                hovertemplate=t.get("hover_buy_bear", "<b>Bear Buy</b><br>Date: %{x|%Y-%m-%d}<br>Price: %{customdata:.2f}<extra></extra>")
            ), row=1, col=1)
            
    # 卖出点保持原样 (青色向下箭头)
    if valid_sell_indices:
        sell_dates = df.iloc[valid_sell_indices].index
        sell_draw_prices = df['High'].iloc[valid_sell_indices] * 1.05 
        real_sell_prices = df['Close'].iloc[valid_sell_indices]       
        
        fig.add_trace(go.Scatter(
            x=sell_dates, 
            y=sell_draw_prices, 
            mode='markers', 
            marker=dict(symbol='triangle-down', color='cyan', size=16, line=dict(color='black', width=1.5)), 
            name=t["sell"],
            customdata=real_sell_prices,
            hovertemplate=t["hover_sell"]
        ), row=1, col=1)

    zoom_start = pd.Timestamp.today() - pd.Timedelta(days=display_days)
    zoom_end = df.index[-1] + pd.Timedelta(days=5)
    fig.update_xaxes(range=[zoom_start, zoom_end])
    
    visible_df = df[df.index >= zoom_start]
    if not visible_df.empty:
        y_max, y_min = visible_df['High'].max(), visible_df['Low'].min()
        
        if 'SMA_20' in visible_df.columns and not visible_df['SMA_20'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_20'].dropna().max()), min(y_min, visible_df['SMA_20'].dropna().min())
        if 'SMA_200' in visible_df.columns and not visible_df['SMA_200'].dropna().empty:
            y_max, y_min = max(y_max, visible_df['SMA_200'].dropna().max()), min(y_min, visible_df['SMA_200'].dropna().min())
            
        visible_buys = [idx for idx in valid_buy_indices if df.index[idx] >= zoom_start]
        if visible_buys:
            min_buy_marker = (df['Low'].iloc[visible_buys] * 0.95).min()
            y_min = min(y_min, min_buy_marker) 
            
        visible_sells = [idx for idx in valid_sell_indices if df.index[idx] >= zoom_start]
        if visible_sells:
            max_sell_marker = (df['High'].iloc[visible_sells] * 1.05).max()
            y_max = max(y_max, max_sell_marker) 

        padding = (y_max - y_min) * 0.05
        if padding == 0: padding = y_max * 0.05
        fig.update_yaxes(range=[y_min - padding, y_max + padding], row=1, col=1)

    title_suffix = t["chart_title_suffix"].format(days=len(df)) if is_new_stock else ""
    chart_title = t["trend_signals"].format(ticker=ticker) + title_suffix
    fig.update_layout(title=chart_title, xaxis_rangeslider_visible=False, height=600, template="plotly_white")
    return fig


def render_stock_page():
    t = get_t()
    lang = st.session_state.get('lang', 'CN')
    
    st.title(t["title"])
    
    # 获取数据源（强制传入当前语言用于报错提示的翻译）
    ticker_dict = fetch_all_us_tickers(lang)
    
    if "multi_select_ui" not in st.session_state:
        st.session_state["multi_select_ui"] = [k for k, v in ticker_dict.items() if v in ["COIN", "CRCL", "UNH", "UPST", "RDDT", "CRWV", "NVDA", "TSLA"]]
    
    # ------------------ 左侧边栏：一键寻宝区 ------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader(t["scanner_header"])
    st.sidebar.caption(t["scanner_cap"])
    
    scan_days = st.sidebar.number_input(t["scan_days"], min_value=1, max_value=60, value=15)
    scan_limit = st.sidebar.number_input(t["scan_limit"], min_value=100, max_value=20000, value=1000, step=500)

    if st.sidebar.button(t["btn_scan"], type="secondary"):
        with st.spinner(t["spin_scan"].format(limit=scan_limit)):
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
                    status_text.text(t["status_eval"].format(current=i+1, total=len(scan_items), ticker=ticker))
                    
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
                    current_selections = st.session_state["multi_select_ui"]
                    new_selections = list(dict.fromkeys(current_selections + found_keys))
                    st.session_state["multi_select_ui"] = new_selections
                    st.sidebar.success(t["scan_success"].format(count=len(found_keys)))
                    st.rerun()
                else:
                    st.sidebar.info(t["scan_fail"])
                    
            except Exception as e:
                st.sidebar.error(t["err_dl"].format(e=e))

    st.sidebar.markdown("---")
    
    # ------------------ 左侧边栏：常规分析区 ------------------
    st.sidebar.header(t["config_header"])
    
    selected_display = st.sidebar.multiselect(
        t["search_label"], 
        options=list(ticker_dict.keys()), 
        key="multi_select_ui", 
        help=t["search_help"]
    )
    
    selected_stocks = [ticker_dict[k] for k in selected_display]

    custom_tickers = st.sidebar.text_input(t["manual_add"], "")
    if custom_tickers:
        selected_stocks.extend([tkr.strip().upper() for tkr in custom_tickers.split(",") if tkr.strip()])
        selected_stocks = list(set(selected_stocks))

    display_days = st.sidebar.number_input(t["display_days"], min_value=7, max_value=3000, value=300, step=10)

    # ------------------ 右侧主内容区 ------------------
    if st.button(t["btn_generate"], type="primary"):
        if not selected_stocks: 
            st.warning(t["warn_empty"])
            st.stop()
            
        start_date = (datetime.today() - timedelta(days=max(730, display_days + 300))).strftime('%Y-%m-%d')
        end_date = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        all_buys, all_sells, charts_rendered = [], [], []
        my_bar = st.progress(0, text=t["prog_init"])
        tab1, tab2 = st.tabs([t["tab_logs"], t["tab_charts"]])

        for i, ticker in enumerate(selected_stocks):
            my_bar.progress((i + 1) / len(selected_stocks), text=t["prog_analyze"].format(ticker=ticker))
            try:
                df = load_data(ticker, start_date, end_date)
                if len(df) <= 20: 
                    st.toast(t["toast_skip"].format(ticker=ticker), icon='⚠️')
                    continue
                df, v_buy, v_sell, buys, sells = process_us_strategy(df, ticker, display_days)
                all_buys.extend(buys); all_sells.extend(sells)
                charts_rendered.append(plot_candlestick_plotly(df, ticker, v_buy, v_sell, display_days))
            except Exception as e: 
                st.error(t["err_process"].format(ticker=ticker, e=e))
                
        my_bar.empty()

        with tab1:
            st.subheader(t["sub_buy"])
            if all_buys: 
                st.dataframe(pd.DataFrame(all_buys).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info(t["info_no_buy"])
                
            st.subheader(t["sub_sell"])
            if all_sells: 
                st.dataframe(pd.DataFrame(all_sells).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info(t["info_no_sell"])

        with tab2:
            for fig in charts_rendered: 
                st.plotly_chart(fig, use_container_width=True)

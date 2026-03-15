import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 🌐 多语言翻译字典 (i18n)
# ==========================================
LANG_DICT = {
    "CN": {
        "title": "🪙 Crypto: V3 终极摸顶融合版 + 真实回测系统",
        "sidebar_header": "🎯 参数配置 (Crypto)",
        "select_crypto": "🔎 选择加密货币对",
        "custom_crypto": "➕ 手动添加币种对 (如 XRP-USD)",
        "display_days": "📉 图表展示天数",
        "btn_scan": "🚀 开始执行 Crypto 扫描与回测",
        "prog_init": "正在初始化牛熊雷达...",
        "prog_calc": "深度运算 {ticker} 过去四年数据...",
        "err_process": "{ticker} 出错: {e}",
        "tab_sig": "📋 近期交易信号",
        "tab_bt": "🏆 V3 模拟回测体检报告",
        "tab_chart": "📈 K线走势图表",
        "sub_buy": "🚨 过去 {days} 天内【抄底买入】信号",
        "info_no_buy": "无买入信号。",
        "sub_sell": "🎯 过去 {days} 天内【摸顶逃顶】信号",
        "info_no_sell": "无逃顶信号。",
        "bt_stats": "📊 过去四年闭环表现统计",
        "met_trades": "闭环交易总次数",
        "met_trades_unit": "次",
        "met_winrate": "策略真实胜率",
        "met_pnl": "盈亏比 (赢/亏)",
        "met_avgwin": "盈利单均赚",
        "bt_history": "📝 完整历史交易流水 (基于 1460 天数据)",
        "warn_no_trades": "⚠️ 过去四年内未跑出任何完整的买卖闭环交易。",
        "phase_bull": "牛市回调",
        "phase_bear": "熊市暴跌",
        "candle": "K线",
        "sma200_new": "均线_上市至今({days}天)",
        # 🌟 新增：牛熊买点分离的翻译
        "buy_bull": "BUY (牛市回调)",
        "buy_bear": "BUY (熊市接刀)",
        "sell_marker": "SELL (卖出)",
        "hover_buy_bull": "<b>牛市回调买入</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>",
        "hover_buy_bear": "<b>熊市暴跌接刀</b><br>日期: %{x|%Y-%m-%d}<br>真实触发价(收盘): %{customdata:.2f}<extra></extra>",
        "chart_title": "{ticker} Crypto Radar V3",
        "chart_title_suffix": " (⚠️数据仅 {days} 天)"
    },
    "EN": {
        "title": "🪙 Crypto Radar V3: Top/Bottom Sniper & Backtest",
        "sidebar_header": "🎯 Configurations (Crypto)",
        "select_crypto": "🔎 Select Crypto Pairs",
        "custom_crypto": "➕ Add Custom Pairs (e.g., XRP-USD)",
        "display_days": "📉 Chart Display Days",
        "btn_scan": "🚀 Start Crypto Scan & Backtest",
        "prog_init": "Initializing Bull/Bear Radar...",
        "prog_calc": "Deep computing {ticker} 4-year data...",
        "err_process": "Error on {ticker}: {e}",
        "tab_sig": "📋 Recent Signals",
        "tab_bt": "🏆 V3 Backtest Report",
        "tab_chart": "📈 Candlestick Charts",
        "sub_buy": "🚨 'Bottom Buy' Signals (Last {days} Days)",
        "info_no_buy": "No buy signals found.",
        "sub_sell": "🎯 'Top Sell' Signals (Last {days} Days)",
        "info_no_sell": "No sell signals found.",
        "bt_stats": "📊 4-Year Closed-Loop Stats",
        "met_trades": "Total Trades",
        "met_trades_unit": "",
        "met_winrate": "True Win Rate",
        "met_pnl": "PnL Ratio (Win/Loss)",
        "met_avgwin": "Avg Win",
        "bt_history": "📝 Full Trade History (Based on 1460 days)",
        "warn_no_trades": "⚠️ No closed-loop trades found in the last 4 years.",
        "phase_bull": "Bull Market Dip",
        "phase_bear": "Bear Market Plunge",
        "candle": "Candle",
        "sma200_new": "SMA_ALL({days}d)",
        # 🌟 新增：牛熊买点分离的翻译
        "buy_bull": "BUY (Bull Dip)",
        "buy_bear": "BUY (Bear Plunge)",
        "sell_marker": "SELL",
        "hover_buy_bull": "<b>Bull Market Dip Buy</b><br>Date: %{x|%Y-%m-%d}<br>Trigger Price: %{customdata:.2f}<extra></extra>",
        "hover_buy_bear": "<b>Bear Market Plunge Buy</b><br>Date: %{x|%Y-%m-%d}<br>Trigger Price: %{customdata:.2f}<extra></extra>",
        "chart_title": "{ticker} Crypto Radar V3",
        "chart_title_suffix": " (⚠️Only {days} days of data)"
    }
}

def get_t():
    """获取当前语言包"""
    lang = st.session_state.get('lang', 'CN')
    return LANG_DICT.get(lang, LANG_DICT['CN'])


@st.cache_data(ttl=3600)
def load_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, progress=False, ignore_tz=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df

def process_crypto_strategy(df, ticker, display_days):
    t = get_t()
    if len(df) < 200:
        if len(df) > 20: df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_200'] = df['Close'].expanding().mean()
        return df, [], [], [], [], []

    delta = df['Close'].diff()
    rs = delta.clip(lower=0).ewm(com=13, adjust=False).mean() / (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
    df['RSI_14'] = 100 - (100 / (1 + rs))
    high_14, low_14 = df['High'].rolling(14).max(), df['Low'].rolling(14).min()
    df['WMSR_14'] = -100 * (high_14 - df['Close']) / (high_14 - low_14)
    df['Vol_SMA_20'] = df['Volume'].rolling(20).mean()
    df['Vol_Spike'] = df['Volume'] / df['Vol_SMA_20']
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()

    tr = pd.concat([df['High']-df['Low'], np.abs(df['High']-df['Close'].shift(1)), np.abs(df['Low']-df['Close'].shift(1))], axis=1).max(axis=1)
    df['ATR_20'] = tr.rolling(20).mean()
    df['ATR_Ratio'] = (df['Close'] - df['SMA_20']) / df['ATR_20']

    bull_dip = (df['Close'] >= df['SMA_200']) & (df['ATR_Ratio'] < -1.8)
    bear_plunge = (df['Close'] < df['SMA_200']) & (df['ATR_Ratio'] < -2.5)
    df['Buy_Base_Signal'] = ((df['RSI_14'] < 30) & (df['WMSR_14'] < -85) & (df['Vol_Spike'] > 1.1) & (bull_dip | bear_plunge)).astype(int)

    df['High_50'] = df['High'].rolling(50).max().shift(1)
    daily_range = df['High'] - df['Low'] + 1e-8
    price_new_high_20 = df['High'] >= df['High'].shift(1).rolling(20).max()

    blow_off_top = (df['High'] >= df['High_50']) & (df['ATR_Ratio'] > 2.5) & (df['Vol_Spike'] > 1.5) & (((df['High'] - df['Close']) / daily_range) > 0.6)
    rsi_divergence = price_new_high_20 & (df['RSI_14'] < df['RSI_14'].shift(1).rolling(20).max() - 10) & (df['ATR_Ratio'] > 2.2)
    extreme_fomo = (df['RSI_14'] > 85) & (df['ATR_Ratio'] > 3.8)
    df['Sell_Base_Signal'] = (blow_off_top | rsi_divergence | extreme_fomo).astype(int)

    valid_buy_indices, valid_sell_indices = [], []
    last_buy_price, last_buy_idx = None, None
    last_sell_price, last_sell_idx = None, None

    for i in range(len(df)):
        if df['Buy_Base_Signal'].iloc[i] == 1:
            curr_p = df['Close'].iloc[i]
            if last_buy_idx is not None and (i - last_buy_idx) > 30: last_buy_price = None
            if last_buy_price is None or curr_p <= last_buy_price * 0.85:
                valid_buy_indices.append(i); last_buy_price, last_buy_idx = curr_p, i

        if df['Sell_Base_Signal'].iloc[i] == 1:
            curr_p = df['Close'].iloc[i]
            if last_sell_idx is not None and (i - last_sell_idx) > 15: last_sell_price = None
            if last_sell_price is None or curr_p >= last_sell_price * 1.15:
                valid_sell_indices.append(i); last_sell_price, last_sell_idx = curr_p, i

    position = None
    trade_records = []
    for i in range(len(df)):
        if position is None:
            if i in valid_buy_indices:
                position = {'buy_idx': i, 'buy_date': df.index[i], 'buy_price': df['Close'].iloc[i]}
        else:
            if i in valid_sell_indices:
                sell_date, sell_price = df.index[i], df['Close'].iloc[i]
                trade_records.append({
                    'Ticker': ticker, 'Buy Date': position['buy_date'].date(), 'Buy Price': round(position['buy_price'], 2),
                    'Sell Date': sell_date.date(), 'Sell Price': round(sell_price, 2),
                    'Return(%)': round((sell_price - position['buy_price']) / position['buy_price'] * 100, 2),
                    'Max Drawdown(%)': round((df['Low'].iloc[position['buy_idx']:i+1].min() - position['buy_price']) / position['buy_price'] * 100, 2),
                    'Hold Days': (sell_date - position['buy_date']).days
                })
                position = None

    cutoff_date = datetime.today().date() - timedelta(days=display_days)
    buy_records, sell_records = [], []
    for idx in valid_buy_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            phase = t["phase_bull"] if row['Close'] >= row['SMA_200'] else t["phase_bear"]
            buy_records.append({'Date': date.date(), 'Ticker': ticker, 'Phase': phase, 'Close': round(row['Close'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})
    for idx in valid_sell_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            sell_records.append({'Date': date.date(), 'Ticker': ticker, 'Close': round(row['Close'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})

    return df, valid_buy_indices, valid_sell_indices, buy_records, sell_records, trade_records

def plot_candlestick_plotly(df, ticker, valid_buy_indices, valid_sell_indices, display_days):
    t = get_t()
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name=t["candle"], increasing_line_color='green', decreasing_line_color='red'), row=1, col=1)
    
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA20'), row=1, col=1)
    is_new_stock = len(df) < 200
    sma200_name = t["sma200_new"].format(days=len(df)) if is_new_stock else "SMA200"
    if 'SMA_200' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='orange', width=2), name=sma200_name), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)

    # =========================================================
    # 🌟 核心升级：拆分牛熊买点，使用不同颜色和提示语
    # =========================================================
    if valid_buy_indices:
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
                name=t["buy_bull"],
                customdata=real_buy_prices_bull,
                hovertemplate=t["hover_buy_bull"]
            ), row=1, col=1)
            
        # 2. 绘制熊市暴跌买点 (暗金/橙色)
        if bear_buys:
            buy_dates_bear = df.iloc[bear_buys].index
            buy_draw_prices_bear = df['Low'].iloc[bear_buys] * 0.95 
            real_buy_prices_bear = df['Close'].iloc[bear_buys]      
            
            fig.add_trace(go.Scatter(
                x=buy_dates_bear, 
                y=buy_draw_prices_bear, 
                mode='markers', 
                marker=dict(symbol='triangle-up', color='darkorange', size=16, line=dict(color='black', width=1.5)), 
                name=t["buy_bear"],
                customdata=real_buy_prices_bear,
                hovertemplate=t["hover_buy_bear"]
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
            name=t["sell_marker"],
            customdata=real_sell_prices,
            # Crypto 借用美股的卖点提示模板，稍微简化一下
            hovertemplate='<b>Top Sell</b><br>Date: %{x|%Y-%m-%d}<br>Price: %{customdata:.2f}<extra></extra>' if st.session_state.get('lang') == 'EN' else '<b>高位逃顶</b><br>日期: %{x|%Y-%m-%d}<br>真实逃顶价(收盘): %{customdata:.2f}<extra></extra>'
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
    chart_title = t["chart_title"].format(ticker=ticker) + title_suffix
    fig.update_layout(title=chart_title, xaxis_rangeslider_visible=False, height=600, template="plotly_white")
    return fig

def render_crypto_page():
    t = get_t()
    
    st.title(t["title"])
    st.sidebar.header(t["sidebar_header"])
    
    crypto_options = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
    selected_crypto = st.sidebar.multiselect(t["select_crypto"], options=crypto_options, default=["BTC-USD", "ETH-USD"])
    
    custom_crypto = st.sidebar.text_input(t["custom_crypto"], "")
    if custom_crypto:
        selected_crypto.extend([t_name.strip().upper() for t_name in custom_crypto.split(",") if t_name.strip()])
        selected_crypto = list(set(selected_crypto))

    display_days_crypto = st.sidebar.number_input(t["display_days"], min_value=7, max_value=3000, value=365, step=10)

    if st.button(t["btn_scan"], type="primary"):
        if not selected_crypto: st.stop()
        
        fetch_days = 1460
        start_date = (datetime.today() - timedelta(days=fetch_days)).strftime('%Y-%m-%d')
        end_date = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        all_buys, all_sells, all_trades, charts_rendered = [], [], [], []
        my_bar = st.progress(0, text=t["prog_init"])
        
        tab_sig, tab_backtest, tab_chart = st.tabs([t["tab_sig"], t["tab_bt"], t["tab_chart"]])

        for i, ticker in enumerate(selected_crypto):
            my_bar.progress((i + 1) / len(selected_crypto), text=t["prog_calc"].format(ticker=ticker))
            try:
                df = load_data(ticker, start_date, end_date)
                if len(df) == 0: continue
                df, v_buy, v_sell, buys, sells, trades = process_crypto_strategy(df, ticker, display_days_crypto)
                all_buys.extend(buys); all_sells.extend(sells); all_trades.extend(trades)
                charts_rendered.append(plot_candlestick_plotly(df, ticker, v_buy, v_sell, display_days_crypto))
            except Exception as e: 
                st.error(t["err_process"].format(ticker=ticker, e=e))
                
        my_bar.empty()

        with tab_sig:
            st.subheader(t["sub_buy"].format(days=display_days_crypto))
            if all_buys: 
                st.dataframe(pd.DataFrame(all_buys).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info(t["info_no_buy"])
                
            st.subheader(t["sub_sell"].format(days=display_days_crypto))
            if all_sells: 
                st.dataframe(pd.DataFrame(all_sells).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: 
                st.info(t["info_no_sell"])

        with tab_backtest:
            trades_df = pd.DataFrame(all_trades)
            if not trades_df.empty:
                total_trades = len(trades_df)
                winning_trades = len(trades_df[trades_df['Return(%)'] > 0])
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                avg_win = trades_df[trades_df['Return(%)'] > 0]['Return(%)'].mean() if winning_trades > 0 else 0
                avg_loss = trades_df[trades_df['Return(%)'] <= 0]['Return(%)'].mean() if (total_trades - winning_trades) > 0 else 0
                pnl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

                st.subheader(t["bt_stats"])
                col1, col2, col3, col4 = st.columns(4)
                
                # 处理附带单位的指标，英文环境下省略“次”
                unit_str = f" {t['met_trades_unit']}" if t['met_trades_unit'] else ""
                col1.metric(t["met_trades"], f"{total_trades}{unit_str}")
                
                col2.metric(t["met_winrate"], f"{win_rate:.2%}")
                col3.metric(t["met_pnl"], f"{pnl_ratio:.2f}")
                col4.metric(t["met_avgwin"], f"+{avg_win:.2f}%")
                
                st.markdown("---")
                st.subheader(t["bt_history"])
                st.dataframe(trades_df.sort_values(by=['Sell Date'], ascending=False), use_container_width=True)
            else:
                st.warning(t["warn_no_trades"])

        with tab_chart:
            for fig in charts_rendered: 
                st.plotly_chart(fig, use_container_width=True)
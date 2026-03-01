import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

@st.cache_data(ttl=3600)
def load_data(ticker, start_date, end_date):
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    return df

def process_crypto_strategy(df, ticker, display_days):
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
            phase = "牛市回调" if row['Close'] >= row['SMA_200'] else "熊市暴跌"
            buy_records.append({'Date': date.date(), 'Ticker': ticker, 'Phase': phase, 'Close': round(row['Close'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})
    for idx in valid_sell_indices:
        row, date = df.iloc[idx], df.index[idx]
        if date.date() >= cutoff_date:
            sell_records.append({'Date': date.date(), 'Ticker': ticker, 'Close': round(row['Close'], 2), 'ATR_Ratio': f"{row['ATR_Ratio']:.2f}x"})

    return df, valid_buy_indices, valid_sell_indices, buy_records, sell_records, trade_records

def plot_candlestick_plotly(df, ticker, valid_buy_indices, valid_sell_indices, display_days):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='K线', increasing_line_color='green', decreasing_line_color='red'), row=1, col=1)
    
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='blue', width=1), name='SMA20'), row=1, col=1)
    is_new_stock = len(df) < 200
    sma200_name = f"均线_上市至今({len(df)}天)" if is_new_stock else "SMA200"
    if 'SMA_200' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='orange', width=2), name=sma200_name), row=1, col=1)
        
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color='gray'), row=2, col=1)

    if valid_buy_indices:
        buy_dates, buy_prices = df.iloc[valid_buy_indices].index, df['Low'].iloc[valid_buy_indices] * 0.95
        fig.add_trace(go.Scatter(x=buy_dates, y=buy_prices, mode='markers', marker=dict(symbol='triangle-up', color='magenta', size=16, line=dict(color='black', width=1.5)), name='BUY (买入)'), row=1, col=1)
    if valid_sell_indices:
        sell_dates, sell_prices = df.iloc[valid_sell_indices].index, df['High'].iloc[valid_sell_indices] * 1.05
        fig.add_trace(go.Scatter(x=sell_dates, y=sell_prices, mode='markers', marker=dict(symbol='triangle-down', color='cyan', size=16, line=dict(color='black', width=1.5)), name='SELL (卖出)'), row=1, col=1)

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

    title_suffix = f" (⚠️数据仅 {len(df)} 天)" if is_new_stock else ""
    fig.update_layout(title=f"{ticker} Crypto Radar V3{title_suffix}", xaxis_rangeslider_visible=False, height=600, template="plotly_white")
    return fig

def render_crypto_page():
    st.title("🪙 Crypto: V3 终极摸顶融合版 + 真实回测系统")
    st.sidebar.header("参数配置 (Crypto)")
    crypto_options = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "DOGE-USD"]
    selected_crypto = st.sidebar.multiselect("🔎 选择加密货币对", options=crypto_options, default=["BTC-USD", "ETH-USD"])
    
    custom_crypto = st.sidebar.text_input("➕ 手动添加币种对 (如 XRP-USD)", "")
    if custom_crypto:
        selected_crypto.extend([t.strip().upper() for t in custom_crypto.split(",") if t.strip()])
        selected_crypto = list(set(selected_crypto))

    display_days_crypto = st.sidebar.number_input("📉 图表展示天数", min_value=7, max_value=2000, value=365, step=10)

    if st.button("🚀 开始执行 Crypto 扫描与回测", type="primary"):
        if not selected_crypto: st.stop()
        
        fetch_days = 1460
        start_date = (datetime.today() - timedelta(days=fetch_days)).strftime('%Y-%m-%d')
        end_date = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        all_buys, all_sells, all_trades, charts_rendered = [], [], [], []
        my_bar = st.progress(0, text="正在初始化牛熊雷达...")
        
        tab_sig, tab_backtest, tab_chart = st.tabs(["📋 近期交易信号", "🏆 V3 模拟回测体检报告", "📈 K线走势图表"])

        for i, ticker in enumerate(selected_crypto):
            my_bar.progress((i + 1) / len(selected_crypto), text=f"深度运算 {ticker} 过去四年数据...")
            try:
                df = load_data(ticker, start_date, end_date)
                if len(df) == 0: continue
                df, v_buy, v_sell, buys, sells, trades = process_crypto_strategy(df, ticker, display_days_crypto)
                all_buys.extend(buys); all_sells.extend(sells); all_trades.extend(trades)
                charts_rendered.append(plot_candlestick_plotly(df, ticker, v_buy, v_sell, display_days_crypto))
            except Exception as e: st.error(f"{ticker} 出错: {e}")
        my_bar.empty()

        with tab_sig:
            st.subheader(f"🚨 过去 {display_days_crypto} 天内【抄底买入】信号")
            if all_buys: st.dataframe(pd.DataFrame(all_buys).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: st.info("无买入信号。")
            st.subheader(f"🎯 过去 {display_days_crypto} 天内【摸顶逃顶】信号")
            if all_sells: st.dataframe(pd.DataFrame(all_sells).sort_values(by=['Date', 'Ticker'], ascending=[False, True]), use_container_width=True)
            else: st.info("无逃顶信号。")

        with tab_backtest:
            trades_df = pd.DataFrame(all_trades)
            if not trades_df.empty:
                total_trades = len(trades_df)
                winning_trades = len(trades_df[trades_df['Return(%)'] > 0])
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
                avg_win = trades_df[trades_df['Return(%)'] > 0]['Return(%)'].mean() if winning_trades > 0 else 0
                avg_loss = trades_df[trades_df['Return(%)'] <= 0]['Return(%)'].mean() if (total_trades - winning_trades) > 0 else 0
                pnl_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

                st.subheader("📊 过去四年闭环表现统计")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("闭环交易总次数", f"{total_trades} 次")
                col2.metric("策略真实胜率", f"{win_rate:.2%}")
                col3.metric("盈亏比 (赢/亏)", f"{pnl_ratio:.2f}")
                col4.metric("盈利单均赚", f"+{avg_win:.2f}%")
                
                st.markdown("---")
                st.subheader("📝 完整历史交易流水 (基于 1460 天数据)")
                st.dataframe(trades_df.sort_values(by=['Sell Date'], ascending=False), use_container_width=True)
            else:
                st.warning("⚠️ 过去四年内未跑出任何完整的买卖闭环交易。")

        with tab_chart:
            for fig in charts_rendered: st.plotly_chart(fig, use_container_width=True)
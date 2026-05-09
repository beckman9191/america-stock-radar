import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import fear_and_greed

# ==========================================
# 辅助函数：计算 RSI
# ==========================================
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/window, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# ==========================================
# 1. 数据获取与缓存机制 (缓存15分钟)
# ==========================================
@st.cache_data(ttl=900)
def fetch_market_data():
    tickers = {"SP500": "^GSPC", "NDX": "^NDX", "VIX": "^VIX", "VXN": "^VXN", "GOLD": "GC=F", "UST10": "^TNX"}
    market_data = {}
    
    for name, symbol in tickers.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="1y") 
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                
                # 美债收益率的变动按基点 (pp) 计算，其他按百分比计算
                if name == "UST10":
                    pct_change = current_price - prev_price
                else:
                    pct_change = ((current_price - prev_price) / prev_price) * 100
                
                market_data[name] = {"current": current_price, "change": pct_change, "history": hist['Close']}
                
                # 计算 RSI (仅针对股票指数)
                if name in ["SP500", "NDX"]:
                    rsi_series = calculate_rsi(hist['Close'])
                    market_data[name]["rsi_current"] = rsi_series.iloc[-1]
                    market_data[name]["rsi_change"] = rsi_series.iloc[-1] - rsi_series.iloc[-2]
                    
        except Exception as e:
            st.error(f"无法获取 {symbol} 的数据: {e}")
            
    try:
        spy_pe = yf.Ticker("SPY").info.get('trailingPE', 25.2)
        market_data["SP500"]["pe"] = spy_pe
    except:
        market_data["SP500"]["pe"] = 25.0
        
    try:
        qqq_pe = yf.Ticker("QQQ").info.get('trailingPE', 36.4)
        market_data["NDX"]["pe"] = qqq_pe
    except:
        market_data["NDX"]["pe"] = 36.0
    
    try:
        fgi_res = fear_and_greed.get()
        fgi_value = int(fgi_res.value)
        fgi_desc_en = fgi_res.description
        fgi_trans = {
            "extreme fear": "极度恐慌", "fear": "恐慌", "neutral": "中性", 
            "greed": "贪婪", "extreme greed": "极度贪婪"
        }
        market_data["FGI"] = {
            "current": fgi_value, "change": "LIVE", 
            "status_cn": fgi_trans.get(fgi_desc_en.lower(), "未知"),
            "status_en": fgi_desc_en.upper()
        }
    except Exception as e:
        market_data["FGI"] = {"current": 50, "change": "ERR", "status_cn": "连接异常", "status_en": "ERROR"}
        
    return market_data

# ==========================================
# 2. 极简折线图渲染器 (已修复 fillcolor 报错)
# ==========================================
def hex_to_rgba(hex_color, alpha=0.2):
    """辅助函数：将 #RRGGBB 转换为 Plotly 支持的 rgba 格式"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f'rgba({r}, {g}, {b}, {alpha})'
    return hex_color

def create_sparkline(data_series, color="#27ae60", fill=False):
    # 动态计算带 20% 透明度的 rgba 填充色
    fill_color = hex_to_rgba(color, alpha=0.2) if fill else None
    
    fig = go.Figure(go.Scatter(
        x=data_series.index, y=data_series.values, mode='lines',
        line=dict(color=color, width=3), hoverinfo='skip',
        fill='tozeroy' if fill else 'none', 
        fillcolor=fill_color  # 使用 rgba 格式传入
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0), height=60, 
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        dragmode=False 
    )
    return fig

# ==========================================
# 3. UI 助手函数：波动率、RSI、Playbook 表格 & 动态策略卡片
# ==========================================
def generate_vol_scale_html(val, vol_type="VIX"):
    if vol_type == "VIX":
        zones, labels = [12, 20, 30, 50], ["<12", "12-20", "20-30", "30-50", ">50"]
    else: 
        zones, labels = [15, 22, 32, 55], ["<15", "15-22", "22-32", "32-55", ">55"]

    if val < zones[0]:   idx, stat, col, pos = 0, "极度乐观 OPTIMISTIC", "#27ae60", 10
    elif val < zones[1]: idx, stat, col, pos = 1, "正常波动 NORMAL", "#27ae60", 30
    elif val < zones[2]: idx, stat, col, pos = 2, "略升 ELEVATED", "#8e44ad", 50
    elif val < zones[3]: idx, stat, col, pos = 3, "市场恐慌 FEAR", "#e67e22", 70
    else:                idx, stat, col, pos = 4, "极度恐慌 EXTREME", "#e74c3c", 90

    base_colors = ["#e8f8f5", "#e8f8f5", "#f5eef8", "#fdebd0", "#fadbd8"]
    active_colors = ["#27ae60", "#27ae60", "#8e44ad", "#e67e22", "#e74c3c"]
    
    segments_html = "".join([
        f'<div style="width: 20%; background-color: {active_colors[i] if i == idx else base_colors[i]}; '
        f'color: {"white" if i == idx else "gray"}; font-weight: {"bold" if i == idx else "normal"}; '
        f'display: flex; align-items: center; justify-content: center; font-size: 10px;">{labels[i]}</div>'
        for i in range(5)
    ])

    html = (
        f'<div style="text-align: center; margin-top: 10px;">'
        f'<span style="border: 2px solid {col}; color: {col}; border-radius: 20px; padding: 2px 12px; font-size: 12px; font-weight: bold; display: inline-block;">{stat}</span>'
        f'</div>'
        f'<div style="position: relative; width: 100%; margin-top: 20px;">'
        f'<div style="position: absolute; top: -10px; left: calc({pos}% - 8px); width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 10px solid {col};"></div>'
        f'<div style="display: flex; width: 100%; height: 12px; border-radius: 4px; overflow: hidden;">{segments_html}</div>'
        f'</div>'
    )
    return html

def generate_playbook_html(val, metric_type, lang, t):
    # 根据指标类型定义区间和策略
    if metric_type == "VIX":
        ranges, thresholds = ["< 12", "12 — 20", "20 — 30", "30 — 50", "> 50"], [12, 20, 30, 50]
        sents = ["极度乐观", "正常区间", "恐慌上升", "市场恐慌", "极度恐慌"] if lang == "CN" else ["Optimism", "Normal", "Elevated Fear", "Market Fear", "Extreme Fear"]
        strats = ["谨慎追高", "常规定投", "加大定投", "加倍定投", "大胆抄底"] if lang == "CN" else ["Cautious", "Regular DCA", "Increase DCA", "Double DCA", "Bold Buying"]
        scale_colors = ["#27ae60", "#27ae60", "#8e44ad", "#e67e22", "#e74c3c"]
        
    elif metric_type == "VXN":
        ranges, thresholds = ["< 15", "15 — 22", "22 — 32", "32 — 55", "> 55"], [15, 22, 32, 55]
        sents = ["极度乐观", "正常区间", "恐慌上升", "市场恐慌", "极度恐慌"] if lang == "CN" else ["Optimism", "Normal", "Elevated Fear", "Market Fear", "Extreme Fear"]
        strats = ["谨慎追高", "常规定投", "加大定投", "加倍定投", "大胆抄底"] if lang == "CN" else ["Cautious", "Regular DCA", "Increase DCA", "Double DCA", "Bold Buying"]
        scale_colors = ["#27ae60", "#27ae60", "#8e44ad", "#e67e22", "#e74c3c"]
        
    elif "RSI" in metric_type:
        ranges, thresholds = ["< 30", "30 — 50", "50 — 70", "70 — 80", "> 80"], [30, 50, 70, 80]
        sents = ["超卖", "偏弱", "中性", "偏强", "超买"] if lang == "CN" else ["Oversold", "Weak", "Neutral", "Strong", "Overbought"]
        strats = ["黄金机会", "加大定投", "常规定投", "谨慎追高", "部分止盈"] if lang == "CN" else ["Golden Chance", "Increase DCA", "Regular DCA", "Cautious", "Take Profit"]
        # NDX 使用紫色系风格，S&P 使用绿色系风格
        theme_color = "#8e44ad" if "NDX" in metric_type else "#27ae60"
        scale_colors = ["#27ae60", "#2ecc71", "#f1c40f", theme_color, "#e74c3c"]

    active_idx = 4
    for i, th in enumerate(thresholds):
        if val < th:
            active_idx = i
            break

    rows_html = ""
    for i in range(5):
        is_active = (i == active_idx)
        current_color = scale_colors[i]
        
        tr_bg = f"background-color: {current_color}22;" if is_active else ""
        td_style = "padding: 10px 8px; border-bottom: 1px solid rgba(128,128,128,0.1);"
        border_left = f"border-left: 4px solid {current_color};" if is_active else "border-left: 4px solid transparent;"
        
        td_range = f"{td_style} color: {current_color}; font-weight: bold; {border_left} padding-left: 12px;"
        td_text = f"{td_style} font-weight: {'bold' if is_active else 'normal'};"
        now_badge = f"<span style='background-color: {current_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; float: right; margin-top: -2px;'>NOW</span>" if is_active else ""

        rows_html += f"<tr style='{tr_bg}'><td style='{td_range}'>{ranges[i]}</td><td style='{td_text}'>{sents[i]}</td><td style='{td_text}'>{strats[i]} {now_badge}</td></tr>"

    table_html = (
        f"<table style='width: 100%; border-collapse: collapse; font-size: 14px; color: var(--text-color); margin-top: 15px;'>"
        f"<tr style='color: gray; border-bottom: 1px solid #ddd; text-align: left;'>"
        f"<th style='padding: 8px 8px 8px 16px;'>{t['zone']}</th>"
        f"<th style='padding: 8px;'>{t['sentiment']}</th>"
        f"<th style='padding: 8px;'>{t['strategy']}</th>"
        f"</tr>{rows_html}</table>"
    )
    return table_html

def get_dynamic_strategy(val, stype, lang):
    if stype == "VIX":
        thresholds = [12, 20, 30, 50]
        colors = ["#27ae60", "#27ae60", "#8e44ad", "#e67e22", "#e74c3c"]
        if lang == "CN":
            titles = ["谨慎追高", "定投不停", "加大定投", "加倍定投", "大胆抄底"]
            subs = ["VIX极度乐观，控制节奏", "VIX波动正常，保持定投", "VIX恐慌上升，逢低吸筹", "VIX市场恐慌，加大力度", "VIX极度恐慌，绝佳机会"]
        else:
            titles = ["Cautious", "Keep DCAing", "Increase DCA", "Double DCA", "Bold Buying"]
            subs = ["VIX optimism, pace yourself", "VIX normal, keep DCA", "VIX fear elevated, buy dips", "VIX market fear, buy more", "VIX extreme fear, best chance"]
            
    elif stype == "RSI":
        thresholds = [30, 50, 70, 80]
        colors = ["#27ae60", "#2ecc71", "#f1c40f", "#8e44ad", "#e74c3c"]
        if lang == "CN":
            titles = ["大胆抄底", "加大定投", "留好子弹", "谨慎追高", "部分止盈"]
            subs = ["RSI超卖，黄金机会", "RSI偏弱，加大力度", "RSI中性，等待回调", "RSI偏强，切勿上头", "RSI超买，落袋为安"]
        else:
            titles = ["Golden Chance", "Increase DCA", "Keep Bullets", "Cautious", "Take Profit"]
            subs = ["RSI oversold", "RSI weak, buy more", "RSI neutral, wait", "RSI strong, cautious", "RSI overbought"]
            
    else: # FGI
        thresholds = [25, 45, 56, 76]
        colors = ["#e74c3c", "#f39c12", "#3498db", "#f1c40f", "#e74c3c"]
        if lang == "CN":
            titles = ["黄金机会", "加大定投", "定投不停", "留好子弹", "警惕回调"]
            subs = ["极度恐慌，加倍买入", "市场恐慌，分批布局", "情绪中性，保持节奏", "市场贪婪，等更深回调", "极度贪婪，部分止盈"]
        else:
            titles = ["Golden Chance", "Increase DCA", "Keep DCAing", "Keep Bullets", "Take Profit"]
            subs = ["Extreme Fear, buy double", "Fear, batch layout", "Neutral, keep pace", "Greed, wait deeper dip", "Extreme Greed, watch out"]

    idx = 4
    for i, th in enumerate(thresholds):
        if val < th:
            idx = i
            break
            
    return titles[idx], subs[idx], colors[idx]

# ==========================================
# 4. 页面专属多语言字典
# ==========================================
PULSE_TEXTS = {
    "CN": {
        "page_title": "今日美股情绪观察",
        "sp500_title": "标普500", "ndx_title": "纳指100", 
        "vix_title": "标普500波动率", "vxn_title": "纳指100波动率",
        "sp_rsi_title": "标普500相对强弱", "ndx_rsi_title": "纳指100相对强弱",
        "fgi_title": "FEAR & GREED", "fgi_sub": "恐惧与贪婪指数",
        "playbook": "PLAYBOOK", "zone": "区间", "sentiment": "情绪", "strategy": "策略",
        "fgi_playbook": "F&G PLAYBOOK", "fgi_pb_sub": "针对标普500",
        "today_strategy": "TODAY'S STRATEGY · 今日策略",
        "lbl_sp500": "节奏继续保持", "lbl_ndx": "RSI仍偏强", "lbl_fgi": "等更深回调点"
    },
    "EN": {
        "page_title": "DAILY MARKET PULSE",
        "sp500_title": "S&P 500", "ndx_title": "NASDAQ 100", 
        "vix_title": "S&P 500 Volatility", "vxn_title": "Nasdaq 100 Volatility",
        "sp_rsi_title": "S&P 500 Rel. Strength", "ndx_rsi_title": "NDX 100 Rel. Strength",
        "fgi_title": "FEAR & GREED", "fgi_sub": "Fear & Greed Index",
        "playbook": "PLAYBOOK", "zone": "Zone", "sentiment": "Sentiment", "strategy": "Strategy",
        "fgi_playbook": "F&G PLAYBOOK", "fgi_pb_sub": "For S&P 500",
        "today_strategy": "TODAY'S STRATEGY",
        "lbl_sp500": "Keep Pace", "lbl_ndx": "RSI still strong", "lbl_fgi": "Wait for deeper dips"
    }
}

# ==========================================
# 5. 页面主渲染函数
# ==========================================
def render_pulse_page():
    lang = st.session_state.get('lang', 'CN')
    t = PULSE_TEXTS.get(lang, PULSE_TEXTS['CN'])
    data = fetch_market_data()
    today_str = datetime.now().strftime("%Y-%m-%d / %A")

    st.markdown("""
        <style>
        .now-badge { background-color: #f1c40f; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .fgi-bar-container { display: flex; width: 100%; height: 20px; border-radius: 4px; overflow: hidden; margin-top: 10px; position: relative;}
        .fgi-segment { height: 100%; display: flex; align-items: center; justify-content: center; font-size: 10px; color: rgba(0,0,0,0.5); font-weight: bold;}
        .fgi-table { width: 100%; border-collapse: collapse; font-size: 14px; color: var(--text-color); }
        .fgi-table th { text-align: left; padding: 8px; border-bottom: 1px solid #ddd; color: gray; font-weight: normal; }
        .fgi-table td { padding: 8px; border-bottom: 1px solid rgba(128,128,128,0.2); }
        .fgi-row-active { background-color: rgba(241, 196, 15, 0.15); font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<h1>{t['page_title']}</h1>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='text-align: right; padding-top: 20px; color: gray;'>{today_str}</div>", unsafe_allow_html=True)
    st.markdown("---")

    if not data:
        st.warning("正在拉取实时数据，请稍后刷新...")
        return

    # --- 1. 指数概览区 ---
    col_idx1, col_idx2 = st.columns(2)
    with col_idx1:
        with st.container(border=True): 
            sp500 = data.get("SP500", {"current": 0, "change": 0, "history": [], "pe": 25.0})
            color = "#27ae60" if sp500['change'] >= 0 else "#e74c3c"
            arrow = "▲" if sp500['change'] >= 0 else "▼"
            val_str = "估值偏高" if sp500['pe'] > 20 else ("估值偏低" if sp500['pe'] < 15 else "估值合理")
            
            st.markdown(
                f'<div style="margin-bottom: -15px;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">S&P 500 · ^GSPC <span style="float:right; color:{color}; border:1px solid {color}; padding:2px 8px; border-radius:15px; font-size:14px; font-weight:normal;">{arrow} {sp500["change"]:+.2f}%</span></h4>'
                f'<p style="color: gray; font-size: 13px; margin-bottom: 5px;">{t["sp500_title"]}</p>'
                f'<h1 style="margin: 0px; color: var(--text-color); font-weight: 700; font-size: 40px;">{sp500["current"]:,.2f}</h1>'
                f'<p style="margin: 5px 0 0 0; font-size: 13px; color: var(--text-color);"><strong>P/E {sp500["pe"]:.1f}</strong> · <span style="color: gray;">{val_str}</span></p>'
                f'<p style="margin: 0; font-size: 11px; color: gray;">10Y TREND · 近十年走势</p>'
                f'</div>', 
                unsafe_allow_html=True
            )
            if len(sp500['history']) > 0:
                st.plotly_chart(create_sparkline(sp500['history'], color=color), use_container_width=True, config={'displayModeBar': False})

    with col_idx2:
        with st.container(border=True):
            ndx = data.get("NDX", {"current": 0, "change": 0, "history": [], "pe": 35.0})
            color_ndx = "#8e44ad" if ndx['change'] >= 0 else "#e74c3c"
            arrow_ndx = "▲" if ndx['change'] >= 0 else "▼"
            val_str_ndx = "估值偏高" if ndx['pe'] > 30 else ("估值偏低" if ndx['pe'] < 20 else "估值合理")
            
            st.markdown(
                f'<div style="margin-bottom: -15px;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">NASDAQ 100 · ^NDX <span style="float:right; color:{color_ndx}; border:1px solid {color_ndx}; padding:2px 8px; border-radius:15px; font-size:14px; font-weight:normal;">{arrow_ndx} {ndx["change"]:+.2f}%</span></h4>'
                f'<p style="color: gray; font-size: 13px; margin-bottom: 5px;">{t["ndx_title"]}</p>'
                f'<h1 style="margin: 0px; color: var(--text-color); font-weight: 700; font-size: 40px;">{ndx["current"]:,.2f}</h1>'
                f'<p style="margin: 5px 0 0 0; font-size: 13px; color: var(--text-color);"><strong>P/E {ndx["pe"]:.1f}</strong> · <span style="color: gray;">{val_str_ndx}</span></p>'
                f'<p style="margin: 0; font-size: 11px; color: gray;">10Y TREND · 近十年走势</p>'
                f'</div>', 
                unsafe_allow_html=True
            )
            if len(ndx['history']) > 0:
                st.plotly_chart(create_sparkline(ndx['history'], color=color_ndx), use_container_width=True, config={'displayModeBar': False})

    # --- 2. 波动率区 (VIX & VXN) ---
    col_vix, col_vxn = st.columns(2)
    vix = data.get("VIX", {"current": 0, "change": 0})
    vxn = data.get("VXN", {"current": 0, "change": 0})
    
    with col_vix:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: left; padding: 0;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">VIX <span style="color:gray; font-size:14px; font-weight:normal;">· {vix["change"]:+.2f}%</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["vix_title"]}</p>'
                f'<h1 style="font-size: 48px; margin: 0; color: var(--text-color); line-height: 1; text-align: center;">{vix["current"]:.2f}</h1>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_vol_scale_html(vix['current'], "VIX"), unsafe_allow_html=True)
            st.markdown(generate_playbook_html(vix['current'], "VIX", lang, t), unsafe_allow_html=True)
            
    with col_vxn:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: left; padding: 0;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">VXN <span style="color:gray; font-size:14px; font-weight:normal;">· {vxn["change"]:+.2f}%</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["vxn_title"]}</p>'
                f'<h1 style="font-size: 48px; margin: 0; color: var(--text-color); line-height: 1; text-align: center;">{vxn["current"]:.2f}</h1>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_vol_scale_html(vxn['current'], "VXN"), unsafe_allow_html=True)
            st.markdown(generate_playbook_html(vxn['current'], "VXN", lang, t), unsafe_allow_html=True)

    # --- 3. RSI 动量区 (S&P RSI & NDX RSI) ---
    col_rsi1, col_rsi2 = st.columns(2)
    sp_rsi = sp500.get("rsi_current", 50)
    sp_rsi_chg = sp500.get("rsi_change", 0)
    ndx_rsi = ndx.get("rsi_current", 50)
    ndx_rsi_chg = ndx.get("rsi_change", 0)
    
    # 状态判定辅助闭包
    def get_rsi_status(val):
        if val < 30: return "超卖 OVERSOLD", "#27ae60"
        elif val < 50: return "偏弱 WEAK", "#2ecc71"
        elif val < 70: return "中性偏强 STRONG", "#27ae60" # 参照图片配色
        elif val < 80: return "偏强 STRONG", "#8e44ad" 
        else: return "超买 OVERBOUGHT", "#e74c3c"
        
    with col_rsi1:
        with st.container(border=True):
            status_text, status_col = get_rsi_status(sp_rsi)
            # S&P RSI 强制使用绿色系边框匹配图表
            status_col = "#27ae60" if 50 <= sp_rsi < 80 else status_col
            st.markdown(
                f'<div style="text-align: left; padding: 0;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">S&P RSI(14) <span style="color:gray; font-size:14px; font-weight:normal;">· {sp_rsi_chg:+.1f}</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["sp_rsi_title"]}</p>'
                f'<h1 style="font-size: 48px; margin: 0; color: var(--text-color); line-height: 1; text-align: center;">{sp_rsi:.1f}</h1>'
                f'<div style="text-align: center; margin-top: 10px;">'
                f'<span style="border: 2px solid {status_col}; color: {status_col}; border-radius: 20px; padding: 2px 12px; font-size: 12px; font-weight: bold; display: inline-block;">{status_text}</span>'
                f'</div>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_playbook_html(sp_rsi, "SP_RSI", lang, t), unsafe_allow_html=True)
            
    with col_rsi2:
        with st.container(border=True):
            status_text_n, status_col_n = get_rsi_status(ndx_rsi)
            # NDX RSI 强制使用紫色系边框匹配图表
            status_col_n = "#8e44ad" if 50 <= ndx_rsi < 80 else status_col_n
            st.markdown(
                f'<div style="text-align: left; padding: 0;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">NDX RSI(14) <span style="color:gray; font-size:14px; font-weight:normal;">· {ndx_rsi_chg:+.1f}</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["ndx_rsi_title"]}</p>'
                f'<h1 style="font-size: 48px; margin: 0; color: var(--text-color); line-height: 1; text-align: center;">{ndx_rsi:.1f}</h1>'
                f'<div style="text-align: center; margin-top: 10px;">'
                f'<span style="border: 2px solid {status_col_n}; color: {status_col_n}; border-radius: 20px; padding: 2px 12px; font-size: 12px; font-weight: bold; display: inline-block;">{status_text_n}</span>'
                f'</div>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_playbook_html(ndx_rsi, "NDX_RSI", lang, t), unsafe_allow_html=True)

    # --- 4. 恐惧与贪婪指数 (FEAR & GREED) ---
    fgi = data.get("FGI")
    arrow_position = max(5, min(95, fgi['current'])) 

    col_fgi_main, col_fgi_pb = st.columns(2)
    with col_fgi_main:
        st.markdown(f"<h4 style='color: var(--text-color); margin-top: 10px; margin-bottom: 5px;'>— {t['fgi_title']}</h4><p style='color: gray; font-size: 12px; margin: 0 0 10px 0;'>{t['fgi_sub']} · 针对标普500</p>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; padding-top: 10px;">'
                f'<h1 style="margin: 0px; color: var(--text-color); font-size: 54px;">{fgi["current"]}</h1>'
                f'<div style="margin: 10px 0;"><span style="border: 2px solid #f1c40f; color: #f39c12; padding: 4px 20px; border-radius: 20px; font-weight: bold; font-size: 14px;">'
                f'{fgi["status_cn"] if lang=="CN" else fgi["status_en"]}</span></div>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(
                f'<div style="padding: 20px 10px 10px 10px;">'
                f'<div style="position: relative; width: 100%;">'
                f'<div style="position: absolute; top: -12px; left: calc({arrow_position}% - 8px); width: 0; height: 0; border-left: 8px solid transparent; border-right: 8px solid transparent; border-top: 10px solid #f1c40f;"></div>'
                f'<div class="fgi-bar-container">'
                f'<div class="fgi-segment" style="width: 25%; background-color: #fadbd8;">0-24</div>'
                f'<div class="fgi-segment" style="width: 20%; background-color: #fdebd0;">25-44</div>'
                f'<div class="fgi-segment" style="width: 11%; background-color: #d6eaf8;">45-55</div>'
                f'<div class="fgi-segment" style="width: 20%; background-color: #f1c40f; color: white;">56-75</div>'
                f'<div class="fgi-segment" style="width: 24%; background-color: #fadbd8;">76-100</div>'
                f'</div></div></div>', 
                unsafe_allow_html=True
            )

    with col_fgi_pb:
        st.markdown(f"<h4 style='color: var(--text-color); margin-top: 10px; margin-bottom: 5px;'>— {t['fgi_playbook']}</h4><p style='color: gray; font-size: 12px; margin: 0 0 10px 0;'>F&G · {t['fgi_pb_sub']}</p>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                f'<table class="fgi-table" style="margin-top: 0;">'
                f'<tr><th>{t["zone"]}</th><th>{t["sentiment"]}</th><th>{t["strategy"]}</th></tr>'
                f'<tr><td style="color: #e74c3c; font-weight: bold;">0 - 24</td><td>极度恐慌</td><td>加倍买入</td></tr>'
                f'<tr><td style="color: #f39c12; font-weight: bold;">25 - 44</td><td>恐慌</td><td>加大定投</td></tr>'
                f'<tr><td style="color: #3498db; font-weight: bold;">45 - 55</td><td>中性</td><td>常规定投</td></tr>'
                f'<tr class="fgi-row-active"><td style="color: #f1c40f; font-weight: bold; border-left: 4px solid #f1c40f;">56 - 75</td><td>贪婪</td><td>谨慎追高 <span class="now-badge" style="float:right;">NOW</span></td></tr>'
                f'<tr><td style="color: #e74c3c; font-weight: bold;">76 - 100</td><td>极度贪婪</td><td>部分止盈</td></tr>'
                f'</table>', 
                unsafe_allow_html=True
            )

    # --- 5. 商品与债券 (黄金 & 10年期美债) ---
    st.markdown("<br>", unsafe_allow_html=True)
    col_gold, col_ust = st.columns(2)
    
    with col_gold:
        gold = data.get("GOLD", {"current": 0, "change": 0, "history": pd.Series()})
        g_col = "#e74c3c" if gold["change"] < 0 else "#27ae60"
        g_arrow = "▼" if gold["change"] < 0 else "▲"
        with st.container(border=True):
            st.markdown(
                f'<div style="margin-bottom: -15px;">'
                f'<h4 style="margin-bottom: 5px; color: var(--text-color);"> <span style="color:#f1c40f;">▬</span> GOLD · XAU/USD <span style="float:right; color:{g_col}; border:1px solid {g_col}; padding:2px 8px; border-radius:15px; font-size:14px; font-weight:normal;">{g_arrow} {gold["change"]:+.2f}%</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">伦敦金 · 美元/盎司</p>'
                f'<h2 style="margin: 0px; color: var(--text-color); font-weight: 700;">${gold["current"]:,.0f}</h2>'
                f'</div>', 
                unsafe_allow_html=True
            )
            if len(gold['history']) > 0:
                st.plotly_chart(create_sparkline(gold['history'], color="#f1c40f"), use_container_width=True, config={'displayModeBar': False})

    with col_ust:
        ust = data.get("UST10", {"current": 0, "change": 0, "history": pd.Series()})
        u_col = "#3498db" if ust["change"] >= 0 else "#e74c3c"
        u_arrow = "▲" if ust["change"] >= 0 else "▼"
        with st.container(border=True):
            st.markdown(
                f'<div style="margin-bottom: -15px;">'
                f'<h4 style="margin-bottom: 5px; color: var(--text-color);"> <span style="color:#3498db;">▬</span> 10Y UST · ^TNX <span style="float:right; color:{u_col}; border:1px solid {u_col}; padding:2px 8px; border-radius:15px; font-size:14px; font-weight:normal;">{u_arrow} {ust["change"]:+.2f}pp</span></h4>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">十年期美债收益率</p>'
                f'<h2 style="margin: 0px; color: var(--text-color); font-weight: 700;">{ust["current"]:.2f}%</h2>'
                f'</div>', 
                unsafe_allow_html=True
            )
            if len(ust['history']) > 0:
                st.plotly_chart(create_sparkline(ust['history'], color="#3498db", fill=True), use_container_width=True, config={'displayModeBar': False})

    # --- 6. 动态今日策略 (数据驱动) ---
    st.markdown(f"<h3 style='color: var(--text-color); margin-top: 20px;'>◆ {t['today_strategy']}</h3>", unsafe_allow_html=True)
    
    # 根据最新指标获取策略模块文案 (匹配图中：定投不停、谨慎追高、留好子弹)
    vix_title, _, vix_color = get_dynamic_strategy(vix['current'], "VIX", lang)
    rsi_title, _, rsi_color = get_dynamic_strategy(ndx_rsi, "RSI", lang)
    fgi_title, _, fgi_color = get_dynamic_strategy(fgi['current'], "FGI", lang)

    scol1, scol2, scol3 = st.columns(3)
    
    with scol1:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid #27ae60; padding-top: 10px; margin-top: -15px;">'
                f'<h3 style="color: #27ae60; margin: 0 0 5px 0;">定投不停</h3>'
                f'<span style="color: gray; font-size: 13px;">{t["lbl_sp500"]}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
            
    with scol2:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid #f39c12; padding-top: 10px; margin-top: -15px;">'
                f'<h3 style="color: #f39c12; margin: 0 0 5px 0;">谨慎追高</h3>'
                f'<span style="color: gray; font-size: 13px;">{t["lbl_ndx"]}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
            
    with scol3:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid #3498db; padding-top: 10px; margin-top: -15px;">'
                f'<h3 style="color: #3498db; margin: 0 0 5px 0;">留好子弹</h3>'
                f'<span style="color: gray; font-size: 13px;">{t["lbl_fgi"]}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )

    st.markdown("<p style='text-align:center; color:gray; font-size:12px; margin-top:20px;'>Data: yFinance · FGI API | 仅供参考，非投资建议</p>", unsafe_allow_html=True)
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime
import fear_and_greed

# ==========================================
# 1. 数据获取与缓存机制 (缓存15分钟)
# ==========================================
@st.cache_data(ttl=900)
def fetch_market_data():
    tickers = {"SP500": "^GSPC", "NDX": "^NDX", "VIX": "^VIX", "VXN": "^VXN"}
    market_data = {}
    
    for name, symbol in tickers.items():
        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(period="1y") 
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                pct_change = ((current_price - prev_price) / prev_price) * 100
                market_data[name] = {"current": current_price, "change": pct_change, "history": hist['Close']}
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
# 2. 极简折线图渲染器
# ==========================================
def create_sparkline(data_series, color="#27ae60"):
    fig = go.Figure(go.Scatter(
        x=data_series.index, y=data_series.values, mode='lines',
        line=dict(color=color, width=3), hoverinfo='skip'
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
# 3. UI 助手函数：波动率、Playbook 表格 & 动态策略卡片
# ==========================================
def generate_vol_scale_html(val, vol_type="VIX"):
    if vol_type == "VIX":
        zones, labels = [12, 20, 30, 50], ["<12", "12-20", "20-30", "30-50", ">50"]
    else: 
        zones, labels = [15, 22, 32, 55], ["<15", "15-22", "22-32", "32-55", ">55"]

    if val < zones[0]:   idx, stat, col, pos = 0, "极度乐观 OPTIMISTIC", "#f39c12", 10
    elif val < zones[1]: idx, stat, col, pos = 1, "正常波动 NORMAL", "#27ae60", 30
    elif val < zones[2]: idx, stat, col, pos = 2, "略升 ELEVATED", "#f39c12", 50
    elif val < zones[3]: idx, stat, col, pos = 3, "市场恐慌 FEAR", "#e67e22", 70
    else:                idx, stat, col, pos = 4, "极度恐慌 EXTREME", "#e74c3c", 90

    base_colors = ["#fef5e7", "#e8f8f5", "#fef5e7", "#fdebd0", "#fadbd8"]
    active_colors = ["#f39c12", "#27ae60", "#f39c12", "#e67e22", "#e74c3c"]
    
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

def generate_playbook_html(val, vol_type, lang, t):
    if vol_type == "VIX":
        ranges, thresholds = ["< 12", "12 — 20", "20 — 30", "30 — 50", "> 50"], [12, 20, 30, 50]
    else:
        ranges, thresholds = ["< 15", "15 — 22", "22 — 32", "32 — 55", "> 55"], [15, 22, 32, 55]

    pb_dict = {
        "CN": {"sents": ["极度乐观", "正常区间", "恐慌上升", "市场恐慌", "极度恐慌"], "strats": ["谨慎追高", "常规定投", "加大定投", "加倍定投", "大胆抄底"]},
        "EN": {"sents": ["Optimism", "Normal", "Elevated Fear", "Market Fear", "Extreme Fear"], "strats": ["Cautious", "Regular DCA", "Increase DCA", "Double DCA", "Bold Buying"]}
    }
    sents, strats = pb_dict[lang]["sents"], pb_dict[lang]["strats"]
    scale_colors = ["#f39c12", "#27ae60", "#f39c12", "#e67e22", "#e74c3c"]

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
        f"<table style='width: 100%; border-collapse: collapse; font-size: 14px; color: var(--text-color);'>"
        f"<tr style='color: gray; border-bottom: 1px solid #ddd; text-align: left;'>"
        f"<th style='padding: 8px 8px 8px 16px;'>{t['zone']}</th>"
        f"<th style='padding: 8px;'>{t['sentiment']}</th>"
        f"<th style='padding: 8px;'>{t['strategy']}</th>"
        f"</tr>{rows_html}</table>"
    )
    return table_html

# 🌟 新增：根据数值动态计算策略卡片的文案和颜色
def get_dynamic_strategy(val, stype, lang):
    if stype == "VIX":
        thresholds = [12, 20, 30, 50]
        colors = ["#f39c12", "#27ae60", "#f39c12", "#e67e22", "#e74c3c"]
        if lang == "CN":
            titles = ["谨慎追高", "常规定投", "加大定投", "加倍定投", "大胆抄底"]
            subs = ["VIX极度乐观，控制节奏", "VIX波动正常，保持定投", "VIX恐慌上升，逢低吸筹", "VIX市场恐慌，加大力度", "VIX极度恐慌，绝佳机会"]
        else:
            titles = ["Cautious", "Regular DCA", "Increase DCA", "Double DCA", "Bold Buying"]
            subs = ["VIX optimism, pace yourself", "VIX normal, keep DCA", "VIX fear elevated, buy dips", "VIX market fear, buy more", "VIX extreme fear, best chance"]
            
    elif stype == "VXN":
        thresholds = [15, 22, 32, 55]
        colors = ["#f39c12", "#27ae60", "#f39c12", "#e67e22", "#e74c3c"]
        if lang == "CN":
            titles = ["谨慎追高", "常规定投", "加大定投", "加倍定投", "大胆抄底"]
            subs = ["VXN极度乐观，控制节奏", "VXN波动正常，保持定投", "VXN恐慌上升，逢低吸筹", "VXN市场恐慌，加大力度", "VXN极度恐慌，绝佳机会"]
        else:
            titles = ["Cautious", "Regular DCA", "Increase DCA", "Double DCA", "Bold Buying"]
            subs = ["VXN optimism, pace yourself", "VXN normal, keep DCA", "VXN fear elevated, buy dips", "VXN market fear, buy more", "VXN extreme fear, best chance"]
            
    else: # FGI
        thresholds = [25, 45, 56, 76]
        colors = ["#e74c3c", "#f39c12", "#3498db", "#f1c40f", "#e74c3c"]
        if lang == "CN":
            titles = ["黄金机会", "加大定投", "常规定投", "控制仓位", "警惕回调"]
            subs = ["极度恐慌，加倍买入", "市场恐慌，分批布局", "情绪中性，保持节奏", "市场贪婪，谨慎追高", "极度贪婪，部分止盈"]
        else:
            titles = ["Golden Chance", "Increase DCA", "Regular DCA", "Control Pos", "Take Profit"]
            subs = ["Extreme Fear, buy double", "Fear, batch layout", "Neutral, keep pace", "Greed, cautious chasing", "Extreme Greed, watch out"]

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
        "sp500_title": "标普500", "ndx_title": "纳指100", "vix_title": "标普500波动率", "vxn_title": "纳指100波动率",
        "fgi_title": "FEAR & GREED", "fgi_sub": "恐惧与贪婪指数",
        "playbook": "PLAYBOOK", "zone": "区间", "sentiment": "情绪", "strategy": "策略",
        "fgi_playbook": "FEAR & GREED PLAYBOOK", "fgi_pb_sub": "指数区间 · 市场情绪 · 定投策略",
        "today_strategy": "TODAY'S STRATEGY · 今日策略",
        "lbl_sp500": "S&P 500 指引", "lbl_ndx": "Nasdaq 100 指引", "lbl_fgi": "综合情绪指引"
    },
    "EN": {
        "page_title": "DAILY MARKET PULSE",
        "sp500_title": "S&P 500", "ndx_title": "NASDAQ 100", "vix_title": "S&P 500 Volatility", "vxn_title": "Nasdaq 100 Volatility",
        "fgi_title": "FEAR & GREED", "fgi_sub": "Fear & Greed Index",
        "playbook": "PLAYBOOK", "zone": "Zone", "sentiment": "Sentiment", "strategy": "Strategy",
        "fgi_playbook": "FEAR & GREED PLAYBOOK", "fgi_pb_sub": "Index Zone · Sentiment · Strategy",
        "today_strategy": "TODAY'S STRATEGY",
        "lbl_sp500": "S&P 500 Guide", "lbl_ndx": "Nasdaq Guide", "lbl_fgi": "Overall Sentiment Guide"
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
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">S&P 500 · ^GSPC</h4>'
                f'<p style="color: gray; font-size: 13px; margin-bottom: 5px;">{t["sp500_title"]}</p>'
                f'<h1 style="margin: 0px; color: var(--text-color); font-weight: 700;">{sp500["current"]:,.2f} <span style="font-size: 16px; color: {color}; font-weight: normal;">{arrow} {sp500["change"]:+.2f}%</span></h1>'
                f'<p style="margin: 5px 0 0 0; font-size: 13px; color: var(--text-color);"><strong>P/E {sp500["pe"]:.1f}</strong> · <span style="color: gray;">{val_str}</span></p>'
                f'<p style="margin: 0; font-size: 11px; color: gray;">1Y TREND · 近一年走势</p>'
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
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">NASDAQ 100 · ^NDX</h4>'
                f'<p style="color: gray; font-size: 13px; margin-bottom: 5px;">{t["ndx_title"]}</p>'
                f'<h1 style="margin: 0px; color: var(--text-color); font-weight: 700;">{ndx["current"]:,.2f} <span style="font-size: 16px; color: {color_ndx}; font-weight: normal;">{arrow_ndx} {ndx["change"]:+.2f}%</span></h1>'
                f'<p style="margin: 5px 0 0 0; font-size: 13px; color: var(--text-color);"><strong>P/E {ndx["pe"]:.1f}</strong> · <span style="color: gray;">{val_str_ndx}</span></p>'
                f'<p style="margin: 0; font-size: 11px; color: gray;">1Y TREND · 近一年走势</p>'
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
                f'<div style="text-align: center; padding: 10px 0 0 0;">'
                f'<h5 style="margin-bottom: 0px; color: var(--text-color);">VIX <span style="color:gray;">· {vix["change"]:+.2f}%</span></h5>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["vix_title"]}</p>'
                f'<h1 style="font-size: 54px; margin: 0; color: var(--text-color); line-height: 1;">{vix["current"]:.2f}</h1>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_vol_scale_html(vix['current'], "VIX"), unsafe_allow_html=True)
            
    with col_vxn:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; padding: 10px 0 0 0;">'
                f'<h5 style="margin-bottom: 0px; color: var(--text-color);">VXN <span style="color:gray;">· {vxn["change"]:+.2f}%</span></h5>'
                f'<p style="color: gray; font-size: 12px; margin-bottom: 5px;">{t["vxn_title"]}</p>'
                f'<h1 style="font-size: 54px; margin: 0; color: var(--text-color); line-height: 1;">{vxn["current"]:.2f}</h1>'
                f'</div>', 
                unsafe_allow_html=True
            )
            st.markdown(generate_vol_scale_html(vxn['current'], "VXN"), unsafe_allow_html=True)

    # --- VIX & VXN Playbook 策略表 ---
    col_pb1, col_pb2 = st.columns(2)
    with col_pb1:
        st.markdown(f"<h4 style='color: var(--text-color); margin-top: 15px; margin-bottom: 5px;'>— VIX {t['playbook']}</h4>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<p style='color: gray; font-size: 12px; margin: 0 0 10px 0;'>VIX · 标普500</p>", unsafe_allow_html=True)
            st.markdown(generate_playbook_html(vix['current'], "VIX", lang, t), unsafe_allow_html=True)

    with col_pb2:
        st.markdown(f"<h4 style='color: var(--text-color); margin-top: 15px; margin-bottom: 5px;'>— VXN {t['playbook']}</h4>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<p style='color: gray; font-size: 12px; margin: 0 0 10px 0;'>VXN · 纳指100</p>", unsafe_allow_html=True)
            st.markdown(generate_playbook_html(vxn['current'], "VXN", lang, t), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. 恐惧与贪婪指数 (FEAR & GREED) ---
    fgi = data.get("FGI")
    arrow_position = max(5, min(95, fgi['current'])) 

    with st.container(border=True):
        col_fgi_l, col_fgi_r = st.columns([1, 2])
        with col_fgi_l:
            st.markdown(
                f'<div style="padding-top: 10px;">'
                f'<h4 style="margin-bottom: 0px; color: var(--text-color);">{t["fgi_title"]} <span style="color:gray;">· {fgi["change"]}</span></h4>'
                f'<p style="color: gray; font-size: 13px; margin-bottom: 5px;">{t["fgi_sub"]}</p>'
                f'<h1 style="margin: 0px; color: var(--text-color); font-size: 54px; display: inline-block; vertical-align: middle;">{fgi["current"]}</h1>'
                f'<span style="background-color: rgba(241, 196, 15, 0.2); color: #f39c12; border: 1px solid #f39c12; padding: 4px 12px; border-radius: 20px; font-weight: bold; margin-left: 10px; vertical-align: super;">'
                f'{fgi["status_cn"] if lang=="CN" else fgi["status_en"]}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
            
        with col_fgi_r:
            st.markdown(
                f'<div style="padding-top: 40px;">'
                f'<div style="position: relative; width: 100%;">'
                f'<div style="position: absolute; top: -15px; left: calc({arrow_position}% - 10px); width: 0; height: 0; border-left: 10px solid transparent; border-right: 10px solid transparent; border-top: 12px solid #f1c40f;"></div>'
                f'<div class="fgi-bar-container">'
                f'<div class="fgi-segment" style="width: 25%; background-color: #f5b7b1;">0-24</div>'
                f'<div class="fgi-segment" style="width: 20%; background-color: #fdebd0;">25-44</div>'
                f'<div class="fgi-segment" style="width: 11%; background-color: #d4e6f1;">45-55</div>'
                f'<div class="fgi-segment" style="width: 20%; background-color: #f1c40f; color: white;">56-75</div>'
                f'<div class="fgi-segment" style="width: 24%; background-color: #f5b7b1;">76-100</div>'
                f'</div></div></div>', 
                unsafe_allow_html=True
            )

    # --- 恐惧与贪婪策略表 ---
    st.markdown(f"<h3 style='color: var(--text-color); margin-top: 20px; margin-bottom: 0px;'>— {t['fgi_playbook']}</h3><p style='color: gray; font-size: 14px;'>{t['fgi_pb_sub']}</p>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown(
            f'<table class="fgi-table">'
            f'<tr><th>{t["zone"]}</th><th>{t["sentiment"]}</th><th>{t["strategy"]}</th><th style="width: 60px;"></th></tr>'
            f'<tr><td style="color: #e74c3c; font-weight: bold;">0 — 24</td><td>极度恐慌</td><td>黄金机会，加倍买入</td><td></td></tr>'
            f'<tr><td style="color: #f39c12; font-weight: bold;">25 — 44</td><td>恐慌</td><td>加大定投，分批布局</td><td></td></tr>'
            f'<tr><td style="color: #3498db; font-weight: bold;">45 — 55</td><td>中性</td><td>常规定投，保持节奏</td><td></td></tr>'
            f'<tr class="fgi-row-active"><td style="color: #f1c40f; font-weight: bold;">56 — 75</td><td>贪婪</td><td>谨慎追高，控制仓位</td><td><span class="now-badge">NOW</span></td></tr>'
            f'<tr><td style="color: #e74c3c; font-weight: bold;">76 — 100</td><td>极度贪婪</td><td>警惕回调，部分止盈</td><td></td></tr>'
            f'</table>', 
            unsafe_allow_html=True
        )

    # 🌟 --- 4. 动态今日策略 (数据驱动) ---
    st.markdown(f"<h3 style='color: var(--text-color); margin-top: 30px;'>◆ {t['today_strategy']}</h3>", unsafe_allow_html=True)
    
    # 根据实时数据动态获取策略文案和颜色
    vix_title, vix_sub, vix_color = get_dynamic_strategy(vix['current'], "VIX", lang)
    vxn_title, vxn_sub, vxn_color = get_dynamic_strategy(vxn['current'], "VXN", lang)
    fgi_title, fgi_sub, fgi_color = get_dynamic_strategy(fgi['current'], "FGI", lang)

    scol1, scol2, scol3 = st.columns(3)
    
    with scol1:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid {vix_color}; padding-top: 10px; margin-top: -15px;">'
                f'<p style="color: gray; font-size: 11px; margin: 0 0 2px 0;">{t["lbl_sp500"]}</p>'
                f'<h3 style="color: {vix_color}; margin: 0 0 5px 0;">{vix_title}</h3>'
                f'<span style="color: gray; font-size: 13px;">{vix_sub}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
            
    with scol2:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid {vxn_color}; padding-top: 10px; margin-top: -15px;">'
                f'<p style="color: gray; font-size: 11px; margin: 0 0 2px 0;">{t["lbl_ndx"]}</p>'
                f'<h3 style="color: {vxn_color}; margin: 0 0 5px 0;">{vxn_title}</h3>'
                f'<span style="color: gray; font-size: 13px;">{vxn_sub}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
            
    with scol3:
        with st.container(border=True):
            st.markdown(
                f'<div style="text-align: center; border-top: 4px solid {fgi_color}; padding-top: 10px; margin-top: -15px;">'
                f'<p style="color: gray; font-size: 11px; margin: 0 0 2px 0;">{t["lbl_fgi"]}</p>'
                f'<h3 style="color: {fgi_color}; margin: 0 0 5px 0;">{fgi_title}</h3>'
                f'<span style="color: gray; font-size: 13px;">{fgi_sub}</span>'
                f'</div>', 
                unsafe_allow_html=True
            )
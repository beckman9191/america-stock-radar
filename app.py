import streamlit as st
import stock
import crypto
import market_pulse  # 导入新加的页面模块

# 1. 页面配置必须在最开头
st.set_page_config(page_title="US Stock Radar | 美股雷达", layout="wide")

# ==========================================
# 2. 多语言字典配置区
# ==========================================
TEXTS = {
    "CN": {
        "nav_title": "🧭 雷达导航",
        "market_selector": "🌐 选择交易市场",
        "market_pulse": "📊 情绪观察 (Pulse)",  # 新增
        "market_us": "🇺🇸 美股雷达",
        "market_crypto": "🪙 Crypto 雷达 (V3)"
    },
    "EN": {
        "nav_title": "🧭 Radar Nav",
        "market_selector": "🌐 Select Market",
        "market_pulse": "📊 Market Pulse",      # 新增
        "market_us": "🇺🇸 US Stocks Radar",
        "market_crypto": "🪙 Crypto Radar (V3)"
    }
}

# ==========================================
# 3. 语言切换器 (存入全局状态)
# ==========================================
lang_choice = st.sidebar.radio("🌍 Language / 语言", ["中文", "English"], horizontal=True)
lang = "CN" if lang_choice == "中文" else "EN"

# 将当前语言保存到 session_state
st.session_state['lang'] = lang  

# 获取当前语言的文本包
t = TEXTS[lang]

# ==========================================
# 4. 渲染侧边栏导航
# ==========================================
st.sidebar.title(t["nav_title"])
market_choice = st.sidebar.radio(
    t["market_selector"], 
    [t["market_pulse"], t["market_us"], t["market_crypto"]] # 加入新页面选项
)
st.sidebar.markdown("---")

# ==========================================
# 5. 路由分发机制
# ==========================================
if market_choice == t["market_pulse"]:
    market_pulse.render_pulse_page()
elif market_choice == t["market_us"]:
    stock.render_stock_page()
elif market_choice == t["market_crypto"]:
    crypto.render_crypto_page()
import streamlit as st
import stock
import crypto

# 1. 页面配置必须在最开头（标题可以直接写成双语版）
st.set_page_config(page_title="Quant Radar | 量化雷达", layout="wide")

# ==========================================
# 2. 多语言字典配置区
# ==========================================
TEXTS = {
    "CN": {
        "nav_title": "🧭 量化雷达导航",
        "market_selector": "🌐 选择交易市场",
        "market_us": "🇺🇸 美股量化雷达",
        "market_crypto": "🪙 Crypto 量化雷达 (V3)"
    },
    "EN": {
        "nav_title": "🧭 Quant Radar Nav",
        "market_selector": "🌐 Select Market",
        "market_us": "🇺🇸 US Stocks Radar",
        "market_crypto": "🪙 Crypto Radar (V3)"
    }
}

# ==========================================
# 3. 语言切换器 (存入全局状态)
# ==========================================
# 在侧边栏最上方放一个横向的单选按钮来切换语言
lang_choice = st.sidebar.radio("🌍 Language / 语言", ["中文", "English"], horizontal=True)
lang = "CN" if lang_choice == "中文" else "EN"

# 将当前语言保存到 session_state，这样子页面也能随时读取！
st.session_state['lang'] = lang  

# 获取当前语言的文本包
t = TEXTS[lang]

# ==========================================
# 4. 渲染侧边栏导航
# ==========================================
st.sidebar.title(t["nav_title"])
market_choice = st.sidebar.radio(t["market_selector"], [t["market_us"], t["market_crypto"]])
st.sidebar.markdown("---")

# ==========================================
# 5. 路由分发机制
# ==========================================
if market_choice == t["market_us"]:
    stock.render_stock_page()
elif market_choice == t["market_crypto"]:
    crypto.render_crypto_page()
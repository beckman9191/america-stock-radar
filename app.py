import streamlit as st
import stock
import crypto

# 必须在第一个 Streamlit 命令调用
st.set_page_config(page_title="多市场雷达平台", layout="wide")

# 侧边栏：市场导航
st.sidebar.title("🧭 雷达导航")
market_choice = st.sidebar.radio("🌐 选择交易市场", ["美股雷达", "🪙 Crypto雷达"])
st.sidebar.markdown("---")

# 路由分发机制
if market_choice == "🇺🇸美股雷达":
    stock.render_stock_page()
elif market_choice == "🪙Crypto雷达":

    crypto.render_crypto_page()

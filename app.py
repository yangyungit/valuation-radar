import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 (宏观全家桶版) ---
st.set_page_config(page_title="全球宏观雷达", layout="wide")

# 你的宏观监控列表
ASSETS = {
    # --- 全球核心指数 ---
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "中概互联": "KWEB",
    "中国大盘(FXI)": "FXI",
    "日本股市": "EWJ",
    "印度股市": "INDA",
    "欧洲股市": "VGK",
    "新兴市场": "EEM",
    "越南股市": "VNM",

    # --- 核心大宗与货币 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "农产品": "DBA",
    "美元指数": "UUP",
    "日元": "FXY",

    # --- 关键行业板块 ---
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "公用事业": "XLU",
    "房地产": "XLRE",
    "消费": "XLY",
    
    # --- 债券与利率 ---
    "20年美债": "TLT",
    "高收益债": "HYG",
    "投资级债": "LQD",

    # --- 风格因子 ---
    "价值股": "IVE",
    "成长股": "IVW",
    "动量因子": "MTUM",
    "红利因子": "VYM",

    # --- 另类与主题 ---
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",
    "人工智能": "BOTZ",
    "网络安全": "CIBR",
    "生物科技": "XBI",
    "军工": "ITA",
    "铀矿(核能)": "URA"
}

# --- 2. 数据处理核心逻辑 ---
@st.cache_data(ttl=3600) # 缓存1小时
def get_market_data(tickers):
    data_list = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) 
    
    # 增加进度条，因为资产多了加载会变慢
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    count = 0

    for name, ticker in tickers.items():
        try:
            # 更新进度显示
            count += 1
            status_text.text(f"正在扫描: {name} ({ticker})...")
            progress_bar.progress(count / total)

            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if df.empty:
                continue
                
            if isinstance(df, pd.DataFrame):
                series = df.iloc[:, 0]
            else:
                series = df

            # 只要最近252天的数据
            series = series.dropna()
            if len(series) < 60: # 数据太少的不算
                continue

            last_year = series.tail(252)
            current_price = last_year.iloc[-1]
            
            # 计算 Z-Score (位置)
            mean = last_year.mean()
            std = last_year.std()
            z_score = (current_price - mean) / std
            
            # 计算 Momentum (3个月动量)
            lookback_window = 60 
            if len(series) > lookback_window:
                price_prev = series.iloc[-lookback_window]
                momentum = ((current_price - price_prev) / price_prev) * 100
            else:
                momentum = 0

            data_list.append({
                "Name": name,
                "Ticker": ticker,
                "Price": round(current_price, 2),
                "Z-Score": round(z_score, 2),
                "Momentum": round(momentum, 2)
            })
            
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(data_list)

# --- 3. 页面渲染 ---
# 获取当前时间（美东时间）
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("🌪️ 全球宏观扭曲力场雷达")
st.caption(f"数据最后更新: {update_time} | 监控资产数: {len(ASSETS)}")

df = get_market_data(ASSETS)

if not df.empty:
    # --- 4. 绘制四象限散点图 ---
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Z-Score'],
        y=df['Momentum'],
        mode='markers+text',
        text=df['Name'],
        textposition="top center",
        marker=dict(
            size=14,
            color=df['Momentum'], 
            colorscale='RdYlGn', 
            showscale=True,
            colorbar=dict(title="资金热度")
        ),
        hovertemplate="<b>%{text}</b><br>Z-Score: %{x}<br>3月涨跌: %{y}%<extra></extra>"
    ))

    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    annotations = [
        dict(x=2.5, y=25, text="<b>🔥 拥挤/泡沫</b><br>(高估值+高动量)", showarrow=False, font=dict(color="red", size=12)),
        dict(x=-2.5, y=25, text="<b>💎 捡漏/爆发</b><br>(低估值+高动量)", showarrow=False, font=dict(color="#00FF00", size=12)),
        dict(x=-2.5, y=-25, text="<b>🧊 冷宫/菜市场</b><br>(低估值+无资金)", showarrow=False, font=dict(color="gray", size=12)),
        dict(x=2.5, y=-25, text="<b>⚠️ 崩盘/陷阱</b><br>(高估值+资金流出)", showarrow=False, font=dict(color="orange", size=12))
    ]
    fig.update_layout(annotations=annotations)

    fig.update_layout(
        height=800, # 图表拉高一点，防止拥挤
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        xaxis=dict(range=[-4, 4]), 
        yaxis=dict(range=[-40, 50]), # 扩大一点范围
        template="plotly_dark",
        margin=dict(l=20, r=20, t=30, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 显示数据表格
    with st.expander("查看详细数据表"):
        st.dataframe(df.sort_values(by="Z-Score", ascending=False).style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), use_container_width=True)

else:
    st.error("数据加载中或网络超时，请刷新页面...")

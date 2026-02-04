import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="全球宏观雷达 (矢量版)", layout="wide")

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
    "越南股市": "VNM",

    # --- 核心大宗与货币 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "美元指数": "UUP",
    "日元": "FXY",

    # --- 关键行业板块 ---
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "房地产": "XLRE",
    "消费": "XLY",
    
    # --- 债券 ---
    "20年美债": "TLT",
    "高收益债": "HYG",

    # --- 另类与主题 ---
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",
    "人工智能": "BOTZ",
    "网络安全": "CIBR",
    "生物科技": "XBI",
    "军工": "ITA",
    "铀矿(核能)": "URA"
}

# --- 2. 数据处理核心逻辑 (短矢量版) ---
@st.cache_data(ttl=3600)
def get_market_data_vector(tickers):
    current_data = []
    vectors_data = [] 
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    count = 0

    for name, ticker in tickers.items():
        try:
            count += 1
            if count % 5 == 0: 
                status_text.text(f"正在计算瞬时方向: {name}...")
                progress_bar.progress(count / total)

            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if df.empty: continue
            if isinstance(df, pd.DataFrame): series = df.iloc[:, 0]
            else: series = df
            
            series = series.dropna()
            if len(series) < 260: continue

            # --- 核心修改：只计算"当前"和"5天前"两个点 ---
            # 这两点连线，就是这一周的"速度矢量"
            
            # 1. 坐标系标尺 (用过去一年的均值标准差)
            base_window = series.tail(252)
            mean = base_window.mean()
            std = base_window.std()
            
            # 2. 获取两个关键时间点：现在(t) 和 1周前(t-5)
            # 确保数据够
            if len(series) < 70: continue

            idx_now = -1
            idx_prev = -6 # 5个交易日前
            
            # --- 现在的坐标 ---
            price_now = series.iloc[idx_now]
            z_now = (price_now - mean) / std
            # 现在的动量 (vs 60天前)
            price_60_now = series.iloc[idx_now - 60]
            m_now = ((price_now - price_60_now) / price_60_now) * 100
            
            # --- 1周前的坐标 (尾巴根部) ---
            price_prev = series.iloc[idx_prev]
            z_prev = (price_prev - mean) / std
            # 当时的动量 (vs 当时之前的60天)
            price_60_prev = series.iloc[idx_prev - 60]
            m_prev = ((price_prev - price_60_prev) / price_60_prev) * 100
            
            # 存入数据
            current_data.append({
                "Name": name,
                "Z-Score": round(z_now, 2),
                "Momentum": round(m_now, 2),
                "Price": round(price_now, 2)
            })
            
            # 存尾巴 (只有两个点：起点 -> 终点)
            vectors_data.append({
                "Name": name,
                "X": [z_prev, z_now],
                "Y": [m_prev, m_now]
            })
            
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(current_data), vectors_data

# --- 3. 页面渲染 ---
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("🌪️ 宏观矢量雷达 (1-Week Vector)")
st.caption(f"数据更新: {update_time} | 箭头含义：过去 1 周的瞬时运动方向")

show_trails = st.sidebar.checkbox("显示方向短尾", value=True)

df_now, vectors = get_market_data_vector(ASSETS)

if not df_now.empty:
    fig = go.Figure()

    # --- A. 画短尾巴 (矢量线) ---
    if show_trails:
        for vec in vectors:
            curr_mom = vec['Y'][-1] # 当前动量
            
            # 颜色逻辑：动量高红，低绿
            # 线条稍微透明一点，不要喧宾夺主
            color = "rgba(200, 200, 200, 0.4)" 
            if curr_mom > 5: color = "rgba(255, 80, 80, 0.6)" 
            elif curr_mom < -5: color = "rgba(80, 255, 80, 0.6)" 
            
            # 画线 (只连两个点)
            fig.add_trace(go.Scatter(
                x=vec['X'],
                y=vec['Y'],
                mode='lines',
                line=dict(color=color, width=2), # 线条短而有力
                hoverinfo='skip',
                showlegend=False
            ))

    # --- B. 画当前点 (大球) ---
    fig.add_trace(go.Scatter(
        x=df_now['Z-Score'],
        y=df_now['Momentum'],
        mode='markers+text',
        text=df_now['Name'],
        textposition="top center",
        marker=dict(
            size=16, 
            color=df_now['Momentum'], 
            colorscale='RdYlGn', 
            showscale=True,
            colorbar=dict(title="资金热度"),
            line=dict(color='black', width=1)
        ),
        hovertemplate="<b>%{text}</b><br>Z-Score: %{x}<br>3月涨跌: %{y}%<extra></extra>"
    ))

    # --- C. 坐标轴与修饰 ---
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    annotations = [
        dict(x=3.2, y=40, text="<b>🔥 拥挤/泡沫</b>", showarrow=False, font=dict(color="red", size=14)),
        dict(x=-3.2, y=40, text="<b>💎 捡漏/爆发</b>", showarrow=False, font=dict(color="#00FF00", size=14)),
        dict(x=-3.2, y=-40, text="<b>🧊 冷宫/菜市场</b>", showarrow=False, font=dict(color="gray", size=14)),
        dict(x=3.2, y=-40, text="<b>⚠️ 崩盘/陷阱</b>", showarrow=False, font=dict(color="orange", size=14))
    ]
    fig.update_layout(annotations=annotations)

    fig.update_layout(
        height=850,
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        xaxis=dict(range=[-4.5, 4.5]), 
        yaxis=dict(range=[-50, 60]),
        template="plotly_dark",
        margin=dict(l=40, r=40, t=40, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("查看详细数据表"):
        st.dataframe(df_now.sort_values(by="Z-Score", ascending=False).style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), use_container_width=True)

else:
    st.info("正在扫描全球市场，请稍等...")

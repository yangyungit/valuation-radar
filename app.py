import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="市场扭曲力场雷达", layout="wide")

# 这里定义你想监控的资产（可以随时在这个列表里加）
# 包含：宽基指数, 行业板块, 主题ETF, 另类资产
ASSETS = {
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "中概互联": "KWEB",
    "房地产": "XLRE",
    "比特币": "BTC-USD",
    "黄金": "GLD",
    "原油": "USO",
    "长期国债": "TLT",
    "人工智能": "BOTZ",
    "网络安全": "CIBR",
    "生物科技": "XBI"
}

# --- 2. 数据处理核心逻辑 ---
@st.cache_data(ttl=3600) # 缓存1小时，避免频繁请求
def get_market_data(tickers):
    data_list = []
    
    # 批量获取数据，过去1年（252个交易日）用于计算统计特征
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) # 多取一点buffer
    
    st.write(f"正在扫描市场数据 ({len(tickers)} 个资产)...")
    
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if df.empty:
                continue
                
            # 这里的df可能是多层索引，处理一下
            if isinstance(df, pd.DataFrame):
                series = df.iloc[:, 0]
            else:
                series = df

            # 截取最近252个交易日（约一年）
            last_year = series.tail(252)
            current_price = last_year.iloc[-1]
            
            # --- 核心算法：计算 Z-Score (估值/位置) ---
            # 逻辑：当前价格相对于过去一年均值的偏离程度（标准差倍数）
            # Z=0 表示处于均值，Z>2 表示极度拥挤，Z<-2 表示极度被抛弃
            mean = last_year.mean()
            std = last_year.std()
            z_score = (current_price - mean) / std
            
            # --- 核心算法：计算 Momentum (动量/流量) ---
            # 逻辑：过去60个交易日（约3个月）的涨跌幅，代表中期资金流向
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
            print(f"Error fetching {name}: {e}")
            continue
            
    return pd.DataFrame(data_list)

# --- 3. 页面渲染 ---
st.title("🌪️ 市场扭曲力场监控 (Distortion Field Radar)")
st.markdown("### 估值(Z-Score) vs 动量(Momentum)")

df = get_market_data(ASSETS)

if not df.empty:
    # --- 4. 绘制四象限散点图 (使用 Plotly) ---
    fig = go.Figure()

    # 添加散点
    fig.add_trace(go.Scatter(
        x=df['Z-Score'],
        y=df['Momentum'],
        mode='markers+text',
        text=df['Name'],
        textposition="top center",
        marker=dict(
            size=15,
            color=df['Momentum'], # 颜色随动量变化
            colorscale='RdYlGn',  # 红绿配色
            showscale=True,
            colorbar=dict(title="资金热度")
        ),
        hovertemplate="<b>%{text}</b><br>Z-Score: %{x}<br>3月涨跌: %{y}%<extra></extra>"
    ))

    # --- 关键：画出十字坐标轴，构建四象限 ---
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    # --- 添加象限背景色或标注 ---
    # 为了清晰，我们直接在图上标注四个区域的含义
    annotations = [
        dict(x=2.5, y=20, text="<b>🔥 佳士得/米其林</b><br>(高估值+高动量)<br>泡沫/主升浪", showarrow=False, font=dict(color="red")),
        dict(x=-2.5, y=20, text="<b>💎 潜力/捡漏区</b><br>(低估值+高动量)<br>资金刚开始关注", showarrow=False, font=dict(color="green")),
        dict(x=-2.5, y=-20, text="<b>🥦 菜市场/冷宫</b><br>(低估值+无资金)<br>烂在锅里", showarrow=False, font=dict(color="gray")),
        dict(x=2.5, y=-20, text="<b>⚠️ 崩盘/补跌</b><br>(高估值+资金流出)<br>价值回归", showarrow=False, font=dict(color="orange"))
    ]
    fig.update_layout(annotations=annotations)

    # 布局美化
    fig.update_layout(
        height=700,
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出 (动量负)  |  资金流入 (动量正) -->",
        xaxis=dict(range=[-4, 4]), # 固定视野，突出中心
        yaxis=dict(range=[-30, 40]),
        template="plotly_dark" # 暗色主题，看起来更专业
    )

    st.plotly_chart(fig, use_container_width=True)

    # 显示数据表格
    st.markdown("### 📊 详细数据监控")
    # 按照 Z-Score 排序
    st.dataframe(df.sort_values(by="Z-Score", ascending=False).style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), use_container_width=True)

else:
    st.error("数据加载失败，请检查网络连接（Yahoo Finance 需要访问外网）。")
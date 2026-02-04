import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="全球宏观雷达 Pro", layout="wide")

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

# --- 2. 数据处理核心逻辑 (带轨迹版) ---
@st.cache_data(ttl=3600)
def get_market_data_with_trails(tickers):
    current_data = []
    trails_data = [] # 用来存尾巴的数据
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    count = 0

    for name, ticker in tickers.items():
        try:
            count += 1
            if count % 5 == 0: # 减少刷新频率
                status_text.text(f"正在计算轨迹: {name}...")
                progress_bar.progress(count / total)

            # 获取数据
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if df.empty: continue
            if isinstance(df, pd.DataFrame): series = df.iloc[:, 0]
            else: series = df
            
            series = series.dropna()
            if len(series) < 260: continue

            # --- 计算过去 10 天的轨迹 ---
            # 我们需要计算每天的 Z-Score 和 Momentum，这就需要一个滚动窗口
            # 为了性能，我们只取最后 15 天切片来计算轨迹
            
            # 基础数据准备 (过去一年的均值和方差，作为统一标尺)
            # 注意：为了轨迹平滑，我们固定用今天的 benchmark 来衡量过去10天的位置
            # 这样展示的是"过去10天相对于今天的估值体系"是如何移动的
            base_window = series.tail(252)
            mean = base_window.mean()
            std = base_window.std()
            
            # 取最后 10 个交易日做尾巴
            trail_window = series.tail(10)
            
            # 暂存这条尾巴的坐标
            trail_x = [] # Z-Score 轨迹
            trail_y = [] # Momentum 轨迹
            
            current_price = 0
            current_z = 0
            current_m = 0

            # 遍历这10天，算出每一天的坐标
            for i in range(len(trail_window)):
                price_t = trail_window.iloc[i]
                
                # 计算当天的 Z-Score (用统一标尺)
                z_t = (price_t - mean) / std
                
                # 计算当天的 Momentum (相对于那天之前的60天)
                # 这里的 index 需要对应回原始 series
                idx = trail_window.index[i]
                loc = series.index.get_loc(idx)
                
                if loc > 60:
                    price_prev = series.iloc[loc - 60]
                    m_t = ((price_t - price_prev) / price_prev) * 100
                else:
                    m_t = 0
                
                trail_x.append(z_t)
                trail_y.append(m_t)
                
                # 记录最后一个点作为"当前点"
                if i == len(trail_window) - 1:
                    current_price = price_t
                    current_z = z_t
                    current_m = m_t

            # 存入列表
            current_data.append({
                "Name": name,
                "Z-Score": round(current_z, 2),
                "Momentum": round(current_m, 2),
                "Price": round(current_price, 2)
            })
            
            trails_data.append({
                "Name": name,
                "X": trail_x, # 这是一个列表
                "Y": trail_y  # 这是一个列表
            })
            
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(current_data), trails_data

# --- 3. 页面渲染 ---
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("☄️ 市场趋势雷达 (带轨迹追踪)")
st.caption(f"数据最后更新: {update_time} | 显示过去 10 个交易日的运动轨迹")

# 侧边栏控制
show_trails = st.sidebar.checkbox("显示运动轨迹 (Comet Tails)", value=True)

df_now, trails = get_market_data_with_trails(ASSETS)

if not df_now.empty:
    fig = go.Figure()

    # --- A. 画尾巴 (轨迹线) ---
    if show_trails:
        for trail in trails:
            # 获取该资产当前的动量，用于给尾巴上色
            # 逻辑：动量越高越红，越低越绿。尾巴颜色稍微淡一点
            curr_mom = trail['Y'][-1]
            
            # 简单的颜色逻辑
            color = "rgba(200, 200, 200, 0.3)" # 默认灰色半透明
            if curr_mom > 5: color = "rgba(255, 100, 100, 0.5)" # 红
            elif curr_mom < -5: color = "rgba(100, 255, 100, 0.5)" # 绿
            
            fig.add_trace(go.Scatter(
                x=trail['X'],
                y=trail['Y'],
                mode='lines',
                line=dict(color=color, width=1), # 细线
                hoverinfo='skip', # 尾巴不显示悬停信息，太乱
                showlegend=False
            ))
            
            # 在尾巴的起点（10天前）画个小点，方便看方向
            fig.add_trace(go.Scatter(
                x=[trail['X'][0]],
                y=[trail['Y'][0]],
                mode='markers',
                marker=dict(size=3, color=color),
                hoverinfo='skip',
                showlegend=False
            ))

    # --- B. 画现在的点 (大球) ---
    fig.add_trace(go.Scatter(
        x=df_now['Z-Score'],
        y=df_now['Momentum'],
        mode='markers+text',
        text=df_now['Name'],
        textposition="top center",
        marker=dict(
            size=14,
            color=df_now['Momentum'], 
            colorscale='RdYlGn', 
            showscale=True,
            colorbar=dict(title="当前资金热度"),
            line=dict(color='black', width=1) # 给球加个黑边，更清楚
        ),
        hovertemplate="<b>%{text}</b><br>Z-Score: %{x}<br>3月涨跌: %{y}%<extra></extra>"
    ))

    # --- C. 坐标轴与修饰 ---
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    annotations = [
        dict(x=3.2, y=35, text="<b>🔥 拥挤/泡沫</b>", showarrow=False, font=dict(color="red", size=14)),
        dict(x=-3.2, y=35, text="<b>💎 捡漏/爆发</b>", showarrow=False, font=dict(color="#00FF00", size=14)),
        dict(x=-3.2, y=-35, text="<b>🧊 冷宫/菜市场</b>", showarrow=False, font=dict(color="gray", size=14)),
        dict(x=3.2, y=-35, text="<b>⚠️ 崩盘/陷阱</b>", showarrow=False, font=dict(color="orange", size=14))
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
    st.info("正在初始化数据，请稍等...")

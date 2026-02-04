import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="全球宏观雷达 (月度趋势版)", layout="wide")

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

# --- 2. 数据处理核心逻辑 (月度平滑版) ---
@st.cache_data(ttl=3600)
def get_market_data_smooth(tickers):
    current_data = []
    trails_data = [] 
    
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
                status_text.text(f"正在计算月度趋势: {name}...")
                progress_bar.progress(count / total)

            df = yf.download(ticker, start=start_date, end=end_date, progress=False)['Close']
            
            if df.empty: continue
            if isinstance(df, pd.DataFrame): series = df.iloc[:, 0]
            else: series = df
            
            series = series.dropna()
            # 至少需要一年的数据做基准，加最近的波动
            if len(series) < 260: continue

            # --- 核心修改：计算"月度路径" (Weekly Snapshots) ---
            # 我们不再取最后10天，而是取过去20个交易日（约1个月），每隔5天（1周）采一个样
            # 这样轨迹就是平滑的：4周前 -> 3周前 -> 2周前 -> 1周前 -> 现在
            
            # 1. 计算过去一年的均值标准差作为"地图坐标系" (保持坐标系稳定)
            base_window = series.tail(252)
            mean = base_window.mean()
            std = base_window.std()
            
            # 2. 选出关键时间点 (Keyframes)
            # indices: [-21, -16, -11, -6, -1] 对应过去4周的每周节点
            step = 5 # 每5个交易日(一周)取一个点
            lookback_weeks = 4
            indices_to_plot = []
            
            # 确保数据够长
            if len(series) < (lookback_weeks * step + 65): continue

            for w in range(lookback_weeks, -1, -1): # 4, 3, 2, 1, 0
                idx = len(series) - 1 - (w * step)
                indices_to_plot.append(idx)
            
            trail_x = []
            trail_y = []
            
            current_price = 0
            current_z = 0
            current_m = 0

            # 3. 遍历这些关键点计算坐标
            for i, idx in enumerate(indices_to_plot):
                price_t = series.iloc[idx]
                
                # Z-Score
                z_t = (price_t - mean) / std
                
                # Momentum (相对于那个时间点之前的60天)
                price_prev = series.iloc[idx - 60]
                m_t = ((price_t - price_prev) / price_prev) * 100
                
                trail_x.append(z_t)
                trail_y.append(m_t)
                
                # 最后一个点是"现在"
                if i == len(indices_to_plot) - 1:
                    current_price = price_t
                    current_z = z_t
                    current_m = m_t

            current_data.append({
                "Name": name,
                "Z-Score": round(current_z, 2),
                "Momentum": round(current_m, 2),
                "Price": round(current_price, 2)
            })
            
            trails_data.append({
                "Name": name,
                "X": trail_x,
                "Y": trail_y 
            })
            
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(current_data), trails_data

# --- 3. 页面渲染 ---
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("🌪️ 宏观趋势雷达 (Monthly Trend)")
st.caption(f"数据更新: {update_time} | 轨迹显示：过去1个月的路径 (每周采样)")

show_trails = st.sidebar.checkbox("显示月度路径", value=True)

df_now, trails = get_market_data_smooth(ASSETS)

if not df_now.empty:
    fig = go.Figure()

    # --- A. 画平滑轨迹 ---
    if show_trails:
        for trail in trails:
            curr_mom = trail['Y'][-1]
            
            # 颜色逻辑：动量高红，低绿
            color = "rgba(200, 200, 200, 0.2)" # 默认极淡的灰色
            if curr_mom > 5: color = "rgba(255, 80, 80, 0.4)" # 红
            elif curr_mom < -5: color = "rgba(80, 255, 80, 0.4)" # 绿
            
            # 画线 (平滑的月度路径)
            fig.add_trace(go.Scatter(
                x=trail['X'],
                y=trail['Y'],
                mode='lines', # 纯线
                line=dict(color=color, width=1.5), # 稍微加粗一点点
                hoverinfo='skip',
                showlegend=False
            ))
            
            # 起点标记 (一个月前在哪里)
            fig.add_trace(go.Scatter(
                x=[trail['X'][0]],
                y=[trail['Y'][0]],
                mode='markers',
                marker=dict(size=2, color=color),
                hoverinfo='skip',
                showlegend=False
            ))

    # --- B. 画当前点 ---
    fig.add_trace(go.Scatter(
        x=df_now['Z-Score'],
        y=df_now['Momentum'],
        mode='markers+text',
        text=df_now['Name'],
        textposition="top center",
        marker=dict(
            size=16, # 球大一点
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
        # 表格修复了，这里会正常显示
        st.dataframe(df_now.sort_values(by="Z-Score", ascending=False).style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), use_container_width=True)

else:
    st.info("正在初始化数据，请稍等...")

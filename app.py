import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观时光机 Pro Max", layout="wide")

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

# --- 2. 数据处理核心逻辑 ---
@st.cache_data(ttl=3600)
def get_market_animation_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    ticker_list = list(tickers.values())
    try:
        status_text.text("正在下载全市场数据...")
        raw_data = yf.download(ticker_list, start=start_date, end=end_date, progress=False)['Close']
    except Exception as e:
        return pd.DataFrame() 

    progress_bar.progress(0.3)
    status_text.text("正在构建时空模型...")

    processed_dfs = []
    
    for name, ticker in tickers.items():
        try:
            if ticker not in raw_data.columns:
                continue
            
            series = raw_data[ticker].dropna()
            if len(series) < 260: continue

            # 重采样为"周" (Weekly)
            series_weekly = series.resample('W-FRI').last() 
            
            # 计算固定基准
            base_mean = series.tail(252).mean()
            base_std = series.tail(252).std()

            # 只取最近52周
            recent_weeks = series_weekly.tail(52)
            
            for date, price in recent_weeks.items():
                z_score = (price - base_mean) / base_std
                
                # 动量回溯
                lookback_date = date - timedelta(weeks=12)
                try:
                    idx = series.index.searchsorted(lookback_date)
                    if idx < len(series) and idx >= 0:
                        price_prev = series.iloc[idx]
                        momentum = ((price - price_prev) / price_prev) * 100
                    else:
                        momentum = 0
                except:
                    momentum = 0
                
                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'), # 这就是 Frame 的名字
                    "Name": name,
                    "Ticker": ticker,
                    "Z-Score": round(z_score, 2),
                    "Momentum": round(momentum, 2),
                    "Price": round(price, 2),
                    "Size": 15
                })
        except:
            continue

    progress_bar.empty()
    status_text.empty()
    
    full_df = pd.DataFrame(processed_dfs)
    if not full_df.empty:
        full_df = full_df.sort_values(by="Date")
    return full_df

# --- 3. 页面渲染 ---
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("🎢 宏观时光机 Pro Max (带倒放)")
st.caption(f"更新: {update_time} | 全能控制台：⏪ 倒放 | ▶️ 播放 | 🐢 慢放 | ⏸️ 暂停")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    # 获取所有的 Frame 名称（日期字符串），用于构造倒放序列
    # 必须排序确保顺序正确
    all_dates = sorted(df_anim['Date'].unique())
    # 倒序列表
    reverse_dates = all_dates[::-1]

    # 制作动画
    fig = px.scatter(
        df_anim, 
        x="Z-Score", 
        y="Momentum", 
        animation_frame="Date", 
        animation_group="Name", 
        text="Name",
        hover_name="Name",
        hover_data=["Price", "Ticker"],
        color="Momentum", 
        range_x=[-4.5, 4.5], 
        range_y=[-50, 60],   
        color_continuous_scale="RdYlGn",
        range_color=[-20, 40], 
        title="👇 使用下方按钮控制时间流向"
    )

    fig.update_traces(
        textposition='top center', 
        marker=dict(size=14, line=dict(width=1, color='black'))
    )
    
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    # 区域标注
    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", 
                       text="🔥 拥挤/泡沫", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", 
                       text="💎 捡漏/爆发", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", 
                       text="🧊 冷宫/菜市场", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", 
                       text="⚠️ 崩盘/陷阱", showarrow=False, font=dict(color="orange"))

    # --- 核心修改：自定义按钮逻辑 ---
    fig.update_layout(
        height=800,
        template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=60, b=40),
        
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                direction="left",
                x=0.1, y=0,
                pad={"r": 10, "t": 10},
                buttons=[
                    # 按钮1: ⏪ 倒放 (Rewind)
                    # 核心魔法：args[0] 传入了倒序的 Frame 列表
                    dict(
                        label="⏪ 倒放",
                        method="animate",
                        args=[reverse_dates, dict(frame=dict(duration=200, redraw=True), fromcurrent=True, mode='immediate')]
                    ),
                    # 按钮2: ▶️ 正常播放
                    dict(
                        label="▶️ 播放",
                        method="animate",
                        args=[None, dict(frame=dict(duration=200, redraw=True), fromcurrent=True)]
                    ),
                    # 按钮3: 🐢 慢速播放
                    dict(
                        label="🐢 慢放",
                        method="animate",
                        args=[None, dict(frame=dict(duration=1000, redraw=True), fromcurrent=True)]
                    ),
                    # 按钮4: ⏸️ 暂停
                    dict(
                        label="⏸️ 暂停",
                        method="animate",
                        args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))]
                    )
                ]
            )
        ],
        sliders=[dict(currentvalue={"prefix": "时间: "}, pad={"t": 50})]
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📊 最新市场状态快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    st.dataframe(
        df_latest[['Name', 'Ticker', 'Price', 'Z-Score', 'Momentum']]
        .sort_values(by="Z-Score", ascending=False)
        .style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), 
        use_container_width=True
    )

else:
    st.info("时光机预热中... (首次加载需约20秒)")

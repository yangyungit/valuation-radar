import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观时光机 (极简版)", layout="wide")

ASSETS = {
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "中概互联": "KWEB",
    "中国大盘(FXI)": "FXI",
    "日本股市": "EWJ",
    "印度股市": "INDA",
    "欧洲股市": "VGK",
    "越南股市": "VNM",
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "美元指数": "UUP",
    "日元": "FXY",
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "房地产": "XLRE",
    "消费": "XLY",
    "20年美债": "TLT",
    "高收益债": "HYG",
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",
    "人工智能": "BOTZ",
    "网络安全": "CIBR",
    "生物科技": "XBI",
    "军工": "ITA",
    "铀矿(核能)": "URA"
}

# --- 2. 数据处理 ---
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

            # 重采样为"周"
            series_weekly = series.resample('W-FRI').last() 
            base_mean = series.tail(252).mean()
            base_std = series.tail(252).std()
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
                    "Date": date.strftime('%Y-%m-%d'), 
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

st.title("🎢 宏观时光机 (UI 修复版)")
st.caption(f"更新: {update_time} | 无干扰纯净模式")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    # 准备倒放序列
    all_dates = sorted(df_anim['Date'].unique())
    reverse_dates = all_dates[::-1]

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
        title="" # 去掉标题，界面更干净
    )

    fig.update_traces(
        textposition='top center', 
        marker=dict(size=14, line=dict(width=1, color='black'))
    )
    
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    # 区域标注
    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", 
                       text="🔥 拥挤", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", 
                       text="💎 捡漏", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", 
                       text="🧊 冷宫", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", 
                       text="⚠️ 崩盘", showarrow=False, font=dict(color="orange"))

    # --- 关键修改：强制覆盖默认按钮 ---
    # 我们直接重写 updatemenus，这样方块键就再也回不来了
    fig.layout.updatemenus = [
        dict(
            type="buttons",
            showactive=False,
            direction="left",
            x=0.1, y=0, # 按钮位置调整到左下角
            pad={"r": 10, "t": 10},
            buttons=[
                # 倒放键
                dict(
                    label="⏪ 倒放",
                    method="animate",
                    args=[reverse_dates, dict(frame=dict(duration=150, redraw=True), fromcurrent=True, mode='immediate')]
                ),
                # 播放键
                dict(
                    label="▶️ 播放",
                    method="animate",
                    args=[None, dict(frame=dict(duration=150, redraw=True), fromcurrent=True)]
                ),
                # 暂停键
                dict(
                    label="⏸️ 暂停",
                    method="animate",
                    args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))]
                )
            ]
        )
    ]

    fig.update_layout(
        height=800,
        template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=40, b=40),
        sliders=[dict(currentvalue={"prefix": "时间: "}, pad={"t": 50})]
    )

    st.plotly_chart(fig, use_container_width=True)

    # 底部简报
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    st.markdown("### 📊 最新市场快照")
    st.dataframe(
        df_latest[['Name', 'Ticker', 'Price', 'Z-Score', 'Momentum']]
        .sort_values(by="Z-Score", ascending=False)
        .style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), 
        use_container_width=True
    )

else:
    st.info("数据加载中...")

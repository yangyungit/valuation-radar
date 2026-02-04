import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 极简配置 ---
st.set_page_config(page_title="宏观雷达 (最终修正版)", layout="wide")

ASSETS = {
    "标普500": "SPY", "纳指100": "QQQ", "罗素小盘": "IWM",
    "中概互联": "KWEB", "中国大盘(FXI)": "FXI", "日本股市": "EWJ",
    "印度股市": "INDA", "欧洲股市": "VGK", "越南股市": "VNM",
    "黄金": "GLD", "白银": "SLV", "铜矿": "COPX",
    "原油": "USO", "天然气": "UNG", "美元指数": "UUP", "日元": "FXY",
    "半导体": "SMH", "科技": "XLK", "金融": "XLF",
    "能源": "XLE", "医疗": "XLV", "工业": "XLI",
    "房地产": "XLRE", "消费": "XLY",
    "20年美债": "TLT", "高收益债": "HYG",
    "比特币": "BTC-USD", "以太坊": "ETH-USD",
    "人工智能": "BOTZ", "网络安全": "CIBR", "生物科技": "XBI",
    "军工": "ITA", "铀矿(核能)": "URA"
}

# --- 2. 核心引擎 (10年视野 / 1年滚动) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers):
    end_date = datetime.now()
    # 下载 11 年数据 (10年展示 + 1年滚动基准)
    start_date = end_date - timedelta(days=365*11)
    
    display_years = 10
    rolling_window = 252 # 滚动 1 年 (交易日)
    
    status_text = st.empty()
    status_text.text(f"📥 正在构建10年情绪图谱 (基准: 滚动1年)...")
    
    try:
        data = yf.download(list(tickers.values()), start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except:
        return pd.DataFrame() 
    
    status_text.text("⚡ 正在清洗量价因子...")
    
    processed_dfs = []
    
    for name, ticker in tickers.items():
        try:
            if ticker not in raw_close.columns: continue
            
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            if len(series_price) < rolling_window + 60: continue

            price_weekly = series_price.resample('W-FRI').last()
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index
            
            for date in display_dates:
                # Rolling 1 Year Calculation
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.9: continue
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                v_mean = window_vol.mean()
                v_std = window_vol.std()
                
                if p_std == 0: continue

                # 1. Price Z-Score
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                # 2. Momentum (1 Month / 4 Weeks)
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0
                
                # 3. Volume Z-Score
                vol_val = vol_weekly.loc[date]
                vol_z = (vol_val - v_mean) / v_std if v_std > 0 else 0
                
                size_metric = max(5, min(10 + (vol_z * 8), 60))
                
                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'), 
                    "Name": name,
                    "Z-Score": round(z_score, 2),
                    "Momentum": round(momentum, 2),
                    "Vol_Z": round(vol_z, 2),
                    "Price": round(price_val, 2),
                    "Size": size_metric 
                })
        except: continue

    status_text.empty()
    full_df = pd.DataFrame(processed_dfs)
    if not full_df.empty:
        full_df = full_df.sort_values(by="Date")
    return full_df

# --- 3. 页面渲染 ---
st.title(f"🔭 宏观雷达 (10年全景·滚动1年)")

df_anim = get_market_data(ASSETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    
    range_x = [-4.5, 4.5]
    range_y = [-50, 60] 

    fig = px.scatter(
        df_anim, 
        x="Z-Score", y="Momentum", 
        animation_frame="Date", animation_group="Name", 
        text="Name", hover_name="Name",
        hover_data=["Price", "Vol_Z"],
        color="Momentum", size="Size", size_max=50, 
        range_x=range_x, range_y=range_y, 
        color_continuous_scale="RdYlGn", range_color=[-20, 40],
        title=""
    )

    fig.update_traces(cliponaxis=False, textposition='top center', marker=dict(line=dict(width=1, color='black')))
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 拥挤/主升", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 爆发/抢筹", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 冷宫/吸筹", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 崩盘/主跌", showarrow=False, font=dict(color="orange"))

    settings_normal = dict(frame=dict(duration=200, redraw=True), fromcurrent=True)
    settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.1,
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[all_dates[::-1], settings_fast]),
            dict(label="▶️ 播放", method="animate", args=[None, settings_normal]),
            dict(label="🐢 慢放", method="animate", args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True)]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    fig.layout.sliders[0].currentvalue.prefix = "" 
    fig.layout.sliders[0].currentvalue.font.size = 20
    fig.layout.sliders[0].pad.t = 20
    
    fig.update_layout(
        height=800, template="plotly_dark",
        margin=dict(l=40, r=40, t=20, b=80)
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- 4. 静态表格 (双色修正版) ---
    st.markdown("### 📊 最新数据快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    
    # 这里我们同时应用两个颜色映射
    st.dataframe(
        df_latest[['Name', 'Z-Score', 'Momentum', 'Vol_Z', 'Price']]
        .sort_values(by="Z-Score", ascending=False)
        .style
        .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40) # 动量：红黄绿
        .background_gradient(subset=['Vol_Z'], cmap='Blues', vmin=0, vmax=3),       # 量能：深蓝
        use_container_width=True
    )

    # --- 5. 局限性与方法论说明 (恢复版) ---
    with st.expander("⚠️ 局限性与方法论说明 (Limitations & Methodology)", expanded=False):
        st.markdown("""
        ### 1. 幸存者偏差 (Survivorship Bias)
        * **问题：** 当前资产列表是基于 **2026年** 的视角选取的。
        * **影响：** 回看 2016 年数据时，我们看到了当时的“赢家”，但忽略了当时存在但后来退市的资产。这会导致历史回测看起来比实际情况更乐观。
        
        ### 2. 滚动窗口的“近视效应” (Rolling 1-Year Bias)
        * **算法：** Z-Score 基于 **“当时的过去一年”** 计算。
        * **局限：** 如果市场发生结构性突变（如利率中枢永久抬升），旧的均值参照系会失效。Z-Score < -2 可能不是“便宜”，而是“价值重估”。
        
        ### 3. 正态分布假设谬误 (Normality Assumption)
        * **问题：** 金融市场存在 **肥尾效应 (Fat Tails)**。
        * **现实：** Z-Score < -2 只是统计学上的低估，不代表物理上的底。极端行情下可能跌至 -5 标准差。
        
        ### 4. 波动率量纲差异
        * **问题：** 比特币（高波）和美债（低波）在同一坐标系。
        * **提醒：** 位置代表的是“相对自身历史的极端程度”，而非绝对涨幅。
        
        ### 5. 数据源精度
        * 数据源为 Yahoo Finance 免费接口，仅供宏观趋势参考，不适用于高频交易。
        """)

else:
    st.info("数据下载中，请稍候...")

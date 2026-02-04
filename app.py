import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观雷达 (专业洁净版)", layout="wide")

# 纯净版资产池 (无Emoji, Crypto分拆)
ASSETS = {
    # --- 全球核心指数 ---
    "标普500 (SPY)": "SPY",
    "纳指100 (QQQ)": "QQQ",
    "罗素小盘 (IWM)": "IWM",
    "中概互联 (KWEB)": "KWEB",
    "中国大盘 (FXI)": "FXI",
    "日本股市 (EWJ)": "EWJ",
    "印度股市 (INDA)": "INDA",
    "欧洲股市 (VGK)": "VGK",
    "越南股市 (VNM)": "VNM",

    # --- 核心行业 ---
    "AI机器人 (BOTZ)": "BOTZ",
    "半导体 (SMH)": "SMH",
    "科技 (XLK)": "XLK",
    "金融 (XLF)": "XLF",
    "能源 (XLE)": "XLE",
    "医疗 (XLV)": "XLV",
    "工业 (XLI)": "XLI",
    "房地产 (XLRE)": "XLRE",
    "消费 (XLY)": "XLY",
    "公用事业 (XLU)": "XLU",

    # --- 加密货币 (独立列示) ---
    "比特币 (BTC)": "BTC-USD",
    "以太坊 (ETH)": "ETH-USD",

    # --- 大宗商品 ---
    "黄金 (GLD)": "GLD",
    "白银 (SLV)": "SLV",
    "铜矿 (COPX)": "COPX",
    "原油 (USO)": "USO",
    "天然气 (UNG)": "UNG",
    "铀矿 (URA)": "URA",

    # --- 利率与外汇 ---
    "美元指数 (UUP)": "UUP",
    "日元 (FXY)": "FXY",
    "20年美债 (TLT)": "TLT",
    "高收益债 (HYG)": "HYG"
}

# --- 2. 核心数据引擎 (10年视野 / 1年滚动) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*11)
    
    display_years = 10
    rolling_window = 252 # 滚动 1 年
    
    status_text = st.empty()
    status_text.text(f"📥 正在扫描全球资产 (10年历史 / 滚动1年基准)...")
    
    try:
        data = yf.download(list(tickers.values()), start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except:
        return pd.DataFrame() 
    
    status_text.text("⚡ 正在计算量价因子...")
    
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
                # Rolling 1 Year Window
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.9: continue
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                v_mean = window_vol.mean()
                v_std = window_vol.std()
                
                if p_std == 0: continue

                # Z-Score
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                # Momentum (4 Weeks)
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0
                
                # Vol Z-Score
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
st.title(f"🔭 宏观雷达 (Pro)")

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

    # 区域标注
    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 主升/拥挤", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 爆发/抢筹", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 冷宫/吸筹", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 崩盘/主跌", showarrow=False, font=dict(color="orange"))

    # 动画控件
    settings_normal = dict(frame=dict(duration=200, redraw=True), fromcurrent=True)
    settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.15,
        buttons=[
            dict(label="⏪ 历史回放", method="animate", args=[all_dates[::-1], settings_fast]), # 倒放更有用，叫"历史回放"
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    # --- 核心修改：强制默认显示最后一帧 (Show Latest) ---
    # 1. 把图表的初始数据 (data) 替换为最后一帧的数据
    if len(fig.frames) > 0:
        last_frame_data = fig.frames[-1].data
        fig.data = last_frame_data
    
    # 2. 把 Slider 的滑块位置设为最后一个
    fig.layout.sliders[0].active = len(all_dates) - 1
    
    # Slider 样式
    fig.layout.sliders[0].currentvalue.prefix = "" 
    fig.layout.sliders[0].currentvalue.font.size = 20
    fig.layout.sliders[0].pad = {"t": 50} 
    
    fig.update_layout(
        height=750, template="plotly_dark",
        margin=dict(l=40, r=40, t=20, b=100),
        xaxis=dict(visible=True, showticklabels=True, title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->"),
        yaxis=dict(title="<-- 资金流出  |  资金流入 -->")
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- 4. 局限性说明 ---
    with st.expander("⚠️ 局限性与方法论说明 (Limitations & Methodology)", expanded=False):
        st.markdown("""
        * **滚动窗口 (Rolling Window):** Z-Score 基于资产**过去 1 年 (252交易日)** 的均值和波动率计算。反映的是“相对过去一年的贵贱”，而非历史绝对底部。
        * **数据源:** 使用 Yahoo Finance 免费接口。
        * **BTC/ETH:** 作为高波动资产，其 Z-Score 波动范围可能远超传统资产，请关注相对位置。
        """)

    # --- 5. 静态表格 (双色) ---
    st.markdown("### 📊 最新数据快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    
    st.dataframe(
        df_latest[['Name', 'Z-Score', 'Momentum', 'Vol_Z', 'Price']]
        .sort_values(by="Z-Score", ascending=False)
        .style
        .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40) 
        .background_gradient(subset=['Vol_Z'], cmap='Blues', vmin=0, vmax=3),
        use_container_width=True
    )

else:
    st.info("数据下载中，请稍候...")

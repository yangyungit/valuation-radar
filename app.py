import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 纯净宏观资产池 (板块/指数级) ---
st.set_page_config(page_title="宏观雷达 (纯净板块版)", layout="wide")

ASSETS = {
    # --- 权益类：全球核心市场 ---
    "🇺🇸 标普500 (美股基准)": "SPY",
    "🇺🇸 纳指100 (科技成长)": "QQQ",
    "🇺🇸 罗素2000 (小盘股)": "IWM",
    "🇨🇳 中概互联 (中国科技)": "KWEB",
    "🇨🇳 中国大盘 (FXI)": "FXI",
    "🇯🇵 日本股市": "EWJ",
    "🇮🇳 印度股市": "INDA",
    "🇪🇺 欧洲股市": "VGK",
    "🇻🇳 越南股市": "VNM",

    # --- 权益类：核心行业板块 ---
    "🤖 AI与机器人": "BOTZ",     # AI 独立板块
    "💾 半导体": "SMH",          # 半导体 独立板块
    "💻 传统科技 (XLK)": "XLK",
    "💰 金融 (XLF)": "XLF",
    "⚡ 能源 (XLE)": "XLE",
    "💊 医疗 (XLV)": "XLV",
    "🏭 工业 (XLI)": "XLI",
    "🏠 房地产 (XLRE)": "XLRE",
    "🛍️ 消费 (XLY)": "XLY",
    "💡 公用事业 (XLU)": "XLU",

    # --- 大宗商品与资源 ---
    "🥇 黄金 (避险)": "GLD",
    "🥈 白银 (工业)": "SLV",
    "⛏️ 铜矿 (周期)": "COPX",
    "🛢️ 原油 (能源)": "USO",
    "🔥 天然气": "UNG",
    "☢️ 铀矿 (核能)": "URA",

    # --- 另类资产与货币 ---
    "₿ 加密货币 (Crypto)": "BTC-USD", # 用BTC代表整个板块Beta
    "💵 美元指数": "UUP",
    "💴 日元": "FXY",
    
    # --- 利率与债券 ---
    "📉 20年美债 (长债)": "TLT",
    "🧨 高收益债 (垃圾债)": "HYG"
}

# --- 2. 核心数据引擎 (10年视野 / 1年滚动) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*11)
    
    # 你的核心逻辑：看10年历史，用1年均线做尺子
    display_years = 10
    rolling_window = 252 # 滚动 1 年
    
    status_text = st.empty()
    status_text.text(f"📥 正在扫描全球板块 (10年历史 / 滚动1年基准)...")
    
    try:
        # 批量下载
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
                # Rolling 1 Year Window
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.9: continue
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                v_mean = window_vol.mean()
                v_std = window_vol.std()
                
                if p_std == 0: continue

                # Z-Score (位置)
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                # Momentum (1 Month / 4 Weeks)
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0
                
                # Volume Z-Score (量能)
                vol_val = vol_weekly.loc[date]
                vol_z = (vol_val - v_mean) / v_std if v_std > 0 else 0
                
                # 气泡大小逻辑
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
st.title(f"🔭 宏观雷达 (纯净板块版)")

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
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 抢筹/爆发", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 吸筹/冷宫", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 主跌/崩盘", showarrow=False, font=dict(color="orange"))

    # 动画控件
    settings_normal = dict(frame=dict(duration=200, redraw=True), fromcurrent=True)
    settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.15,
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[all_dates[::-1], settings_fast]),
            dict(label="▶️ 播放", method="animate", args=[None, settings_normal]),
            dict(label="🐢 慢放", method="animate", args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True)]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

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

    # --- 4. 局限性说明 (位置调整到进度条下方) ---
    with st.expander("⚠️ 局限性与方法论说明 (Limitations & Methodology)", expanded=False):
        st.markdown("""
        * **加密货币板块：** 使用 `BTC-USD` 历史数据作为整个 Crypto 板块的 Beta 代理，以保证能回溯 10 年历史（大多数加密 ETF 历史不足 5 年）。
        * **AI 板块：** 使用 `BOTZ` (机器人与AI ETF) 作为代理。
        * **滚动窗口：** Z-Score 基准为滚动 1 年 (252交易日)。
        * **量纲差异：** 高波动资产（如加密货币）的 Z-Score 波动范围天生比低波动资产（如债券）更大，请关注相对位置而非绝对数值。
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

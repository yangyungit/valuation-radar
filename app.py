import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观雷达 (完整版)", layout="wide")

# 纯净版资产池
ASSETS = {
    # --- 全球核心指数 ---
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "中概互联": "KWEB",
    "中国大盘": "FXI",
    "日本股市": "EWJ",
    "印度股市": "INDA",
    "欧洲股市": "VGK",
    "越南股市": "VNM",

    # --- 核心行业 ---
    "机器人": "BOTZ",     # 修正名称
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "房地产": "XLRE",
    "消费": "XLY",
    "公用事业": "XLU",
    "军工": "ITA",         # 新增
    "农业": "DBA",         # 新增

    # --- 加密货币 ---
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",

    # --- 大宗商品 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "铀矿": "URA",

    # --- 利率与外汇 ---
    "美元指数": "UUP",
    "日元": "FXY",
    "20年美债": "TLT",
    "高收益债": "HYG"
}

# --- 2. 核心数据引擎 ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*11)
    
    display_years = 10
    rolling_window = 252 
    
    status_text = st.empty()
    status_text.text(f"📥 正在扫描全球资产 (10年历史)...")
    
    try:
        data = yf.download(list(tickers.values()), start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except:
        return pd.DataFrame() 
    
    status_text.text("⚡ 正在计算因子...")
    
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
                # Rolling Window
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
                
                # Momentum
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
                    "Ticker": ticker, 
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

    # 气泡图
    fig = px.scatter(
        df_anim, 
        x="Z-Score", y="Momentum", 
        animation_frame="Date", animation_group="Name", 
        text="Name", hover_name="Name",
        hover_data=["Ticker", "Price", "Vol_Z"], 
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
    settings_play = dict(frame=dict(duration=400, redraw=True), fromcurrent=True, transition=dict(duration=100))
    settings_rewind = dict(frame=dict(duration=100, redraw=True), fromcurrent=True, transition=dict(duration=0))

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.15,
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[all_dates[::-1], settings_rewind]),
            dict(label="▶️ 正放", method="animate", args=[None, settings_play]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    # 进度条
    fig.layout.sliders[0].active = len(all_dates) - 1
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

    # --- 4. 深度局限性说明 (The Whitebox + Risk Disclosure) ---
    with st.expander("⚠️ 详细局限性、数据来源与算法说明 (Detailed Methodology & Risks)", expanded=False):
        st.markdown("""
        ### I. 数据来源与算法 (Data & Algorithms)
        * **数据源:** Yahoo Finance (复权收盘价)。
        * **Z-Score (估值):** 基于 **滚动 1 年 (252交易日)** 的均值计算。公式: $Z = (P - Mean) / Std$。
        * **Momentum (动量):** 过去 4 周 (20交易日) 的涨跌幅。
        * **Vol_Z (量能):** 成交量的 Z-Score，用于衡量拥挤度。

        ---
        
        ### II. 五大关键局限性 (Critical Limitations)
        
        #### 1. 幸存者偏差 (Survivorship Bias)
        * **问题：** 当前的资产列表是基于 **2026年** 的视角选取的。
        * **影响：** 回看 2015 年数据时，我们看到了当时的“赢家”（如 Nvidia, Bitcoin），但忽略了当时存在但后来退市或破产的公司/代币（如 LUNA, FTX, 或某些退市的中概股）。这会导致历史回测看起来比实际情况更乐观。
        
        #### 2. 滚动窗口的“近视效应” (Rolling Window Bias)
        * **算法：** 本图表的 Z-Score 是基于 **“当时的过去一年”** 计算的。
        * **局限：** 如果市场发生 **结构性突变 (Structural Break)**，例如利率从 0% 永久升至 5%，旧的估值中枢会失效。此时 Z-Score = -2 可能不是“便宜”，而是“价值重估”。不要刻舟求剑。
        
        #### 3. 正态分布假设谬误 (Normality Assumption)
        * **问题：** Z-Score 假设价格波动服从正态分布。
        * **现实：** 金融市场存在 **肥尾效应 (Fat Tails)**。在黑天鹅事件中，资产价格可能会跌至 -5甚至 -10个标准差。Z-Score < -2 只是统计学上的低估，不代表物理上的底。
        
        #### 4. 波动率量纲差异 (Volatility Scale)
        * **问题：** 图表中比特币（高波）和美债（低波）放在同一个坐标系中。
        * **影响：** 美债的 Z-Score +2 可能意味着 2% 的涨幅，而比特币的 Z-Score +2 意味着 50% 的涨幅。**位置代表的是“相对自身历史的极端程度”，而不是绝对收益率。**
        
        #### 5. 数据源精度 (Data Quality)
        * 数据源为 Yahoo Finance 免费接口，可能存在分红/拆股调整延迟，不适用于高频交易决策。
        """)

    # 静态表格
    st.markdown("### 📊 最新数据快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    
    display_cols = ['Name', 'Ticker', 'Z-Score', 'Momentum', 'Vol_Z', 'Price']
    
    st.dataframe(
        df_latest[display_cols]
        .sort_values(by="Z-Score", ascending=False)
        .style
        .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40) 
        .background_gradient(subset=['Vol_Z'], cmap='Blues', vmin=0, vmax=3),
        use_container_width=True
    )

else:
    st.info("数据下载中，请稍候...")

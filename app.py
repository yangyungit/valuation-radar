import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观真理雷达 (同步修复版)", layout="wide")

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

# --- 2. 数据处理 ---
@st.cache_data(ttl=3600*12) 
def get_market_animation_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*11) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    ticker_list = list(tickers.values())
    try:
        status_text.text("正在拉取 10 年量价数据 (Price & Volume)...")
        data = yf.download(ticker_list, start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except Exception as e:
        return pd.DataFrame() 

    progress_bar.progress(0.4)
    status_text.text("正在计算结构性因子 (Volume Confirmation)...")

    processed_dfs = []
    total_assets = len(tickers)
    current_asset = 0

    for name, ticker in tickers.items():
        current_asset += 1
        if current_asset % 5 == 0:
            progress_bar.progress(0.4 + (0.5 * current_asset / total_assets))

        try:
            if ticker not in raw_close.columns:
                continue
            
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            
            if len(series_price) < 260: continue

            price_weekly = series_price.resample('W-FRI').last()
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            target_start_date = end_date - timedelta(days=365*10)
            display_idx = price_weekly.index >= target_start_date
            
            display_dates = price_weekly[display_idx].index
            
            for date in display_dates:
                past_year_price = series_price.loc[:date].tail(252)
                if len(past_year_price) < 100: continue
                
                p_mean = past_year_price.mean()
                p_std = past_year_price.std()
                if p_std == 0: continue
                
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                lookback_date = date - timedelta(weeks=12)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        if price_prev > 0:
                            momentum = ((price_val - price_prev) / price_prev) * 100
                        else: momentum = 0
                    else: momentum = 0
                except: momentum = 0
                
                past_year_vol = series_vol.loc[:date].tail(252)
                v_mean = past_year_vol.mean()
                v_std = past_year_vol.std()
                
                vol_val = vol_weekly.loc[date]
                if v_std > 0:
                    vol_z = (vol_val - v_mean) / v_std
                else:
                    vol_z = 0
                
                size_metric = 10 + (vol_z * 8) 
                size_metric = max(5, min(size_metric, 50))
                
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
        except Exception as e:
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

st.title("👁️ 宏观真理雷达 (时间轴修复版)")
st.caption(f"洞察核心：**球体大小** 代表 **成交量异动**。时间轴现已完美同步。")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    reverse_dates = all_dates[::-1]
    
    start_str = all_dates[0]
    end_str = all_dates[-1]

    fig = px.scatter(
        df_anim, 
        x="Z-Score", 
        y="Momentum", 
        animation_frame="Date", 
        animation_group="Name", 
        text="Name",
        hover_name="Name",
        hover_data=["Price", "Ticker", "Vol_Z"],
        color="Momentum", 
        size="Size", 
        size_max=45, 
        range_x=[-4.5, 4.5], 
        range_y=[-60, 80], 
        color_continuous_scale="RdYlGn",
        range_color=[-20, 40],
        title=f"📅 {start_str} 至 {end_str} (大球 = 强共识/结构性变化)"
    )

    fig.update_traces(
        textposition='top center', 
        marker=dict(line=dict(width=1, color='black')) 
    )
    
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", 
                       text="🔥 拥挤区<br>(大球=新范式)<br>(小球=假泡沫)", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", 
                       text="💎 爆发区<br>(大球=主力抢筹)", showarrow=False, font=dict(color="#00FF00"))
    
    animation_settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)
    animation_settings_slow = dict(frame=dict(duration=500, redraw=True), fromcurrent=True)

    # --- 关键修改：只更新按钮，不再覆盖 sliders ---
    fig.layout.updatemenus = [
        dict(
            type="buttons",
            showactive=False,
            direction="left",
            x=0.1, y=0, 
            pad={"r": 10, "t": 10},
            buttons=[
                dict(label="⏪ 倒放", method="animate", args=[reverse_dates, animation_settings_fast]),
                dict(label="▶️ 极速", method="animate", args=[None, animation_settings_fast]),
                dict(label="🐢 慢放", method="animate", args=[None, animation_settings_slow]),
                dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
            ]
        )
    ]
    
    # --- 修复逻辑：访问现有的 slider 并修改它，而不是替换它 ---
    try:
        # Plotly Express 自动生成的 slider 通常是列表中的第一个
        if fig.layout.sliders:
            fig.layout.sliders[0].currentvalue.prefix = "当前时间: "
            fig.layout.sliders[0].pad.t = 50 # 增加一点顶部间距防止重叠
    except:
        pass # 如果万一没有slider，就不改了，防止报错

    fig.update_layout(
        height=850,
        template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=40, b=40)
        # 注意：这里删除了 sliders=[...] 那一行
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🧐 如何用此图做'穿透力'审视？", expanded=True):
        st.markdown("""
        ### 投资功力的试金石：量价背离 (Volume-Price Divergence)
        
        **1. 结构性牛市 (The Paradigm Shift)**
        * **现象：** 资产处于右上角（Z-Score > 2），但气泡**异常巨大**。
        * **解读：** 尽管价格很贵，但成交量也在通过历史极值。说明市场不仅接受了这个价格，还在疯狂涌入。**这是新钱在把旧钱洗出去，新周期开启。**
        
        **2. 虚假繁荣 (The Bull Trap)**
        * **现象：** 资产处于右上角，但气泡**非常小**。
        * **解读：** 价格是被少量资金“买”上去的（缩量上涨）。极度危险。
        
        **3. 底部吸筹 (Accumulation)**
        * **现象：** 资产处于左下角（冷宫），但气泡**突然变大**。
        * **解读：** 价格还没涨，但有人在暗中大量吃货。最佳左侧建仓点。
        """)

    latest_date = df_anim['Date'].iloc[-1]
    st.markdown(f"### 📊 市场定格 ({latest_date})")
    df_latest = df_anim[df_anim['Date'] == latest_date]
    st.dataframe(
        df_latest[['Name', 'Ticker', 'Price', 'Z-Score', 'Momentum', 'Vol_Z']]
        .sort_values(by="Z-Score", ascending=False)
        .style.background_gradient(subset=['Vol_Z'], cmap='Blues'), 
        use_container_width=True
    )

else:
    st.info("正在初始化...")

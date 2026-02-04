import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观真理雷达 (完美同步版)", layout="wide")

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
                
                # 调整球体大小逻辑
                size_metric = 10 + (vol_z * 8) 
                size_metric = max(5, min(size_metric, 60)) # 稍微放大一点上限
                
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

st.title("👁️ 宏观真理雷达 (视觉修复版)")
st.caption(f"更新: {update_time} | 修复：日期标题同步显示 & 大球防出框")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    reverse_dates = all_dates[::-1]

    # 1. 基础图表构建
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
        size_max=50, # 允许球更大
        # --- 核心修改：扩大坐标轴范围，防止出框 ---
        range_x=[-5.5, 5.5], 
        range_y=[-80, 100], 
        color_continuous_scale="RdYlGn",
        range_color=[-20, 40],
        # 初始标题
        title=f"📅 市场定格: {all_dates[0]}"
    )

    # --- 核心修改：解决球体出框被切的问题 ---
    fig.update_traces(
        cliponaxis=False, # 关键：允许球体画在坐标轴外面，不被切掉
        textposition='top center', 
        marker=dict(line=dict(width=1, color='black')) 
    )
    
    # 辅助线
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    # 区域标注
    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", 
                       text="🔥 拥挤/新范式", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", 
                       text="💎 捡漏/爆发", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", 
                       text="🧊 冷宫/吸筹", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", 
                       text="⚠️ 崩盘/陷阱", showarrow=False, font=dict(color="orange"))

    # --- 核心修改：手动注入每一帧的标题 ---
    # 这一步是让标题跟着日期跑的关键！
    # 我们遍历 Plotly 生成的每一帧，强行把它的 Layout 标题改成当天的日期
    for frame in fig.frames:
        frame_date = frame.name # 这里的 name 就是我们在 dataframe 里存的 Date
        frame.layout.title.text = f"📅 市场定格: {frame_date}"

    # 动画参数
    animation_settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)
    animation_settings_slow = dict(frame=dict(duration=500, redraw=True), fromcurrent=True)

    # 按钮组
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

    fig.update_layout(
        height=850,
        template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 底部说明与数据
    with st.expander("🧐 视觉解读指南", expanded=False):
        st.markdown("""
        * **大标题日期：** 抬头看图表上方，日期会随动画实时跳动。
        * **球体完整性：** 现已允许球体溢出边界，确保你能看到完整的大泡沫。
        * **球体大小：** 代表成交量异动 (Volume Z-Score)。球越大，共识越强。
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
    st.info("正在加载数据...")

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="双频宏观雷达", layout="wide")

ASSETS = {
    # --- 全球核心指数 ---
    "标普500": "SPY", "纳指100": "QQQ", "罗素小盘": "IWM",
    "中概互联": "KWEB", "中国大盘(FXI)": "FXI", "日本股市": "EWJ",
    "印度股市": "INDA", "欧洲股市": "VGK", "越南股市": "VNM",

    # --- 核心大宗与货币 ---
    "黄金": "GLD", "白银": "SLV", "铜矿": "COPX",
    "原油": "USO", "天然气": "UNG", "美元指数": "UUP", "日元": "FXY",

    # --- 关键行业板块 ---
    "半导体": "SMH", "科技": "XLK", "金融": "XLF",
    "能源": "XLE", "医疗": "XLV", "工业": "XLI",
    "房地产": "XLRE", "消费": "XLY",
    
    # --- 债券 ---
    "20年美债": "TLT", "高收益债": "HYG",

    # --- 另类与主题 ---
    "比特币": "BTC-USD", "以太坊": "ETH-USD",
    "人工智能": "BOTZ", "网络安全": "CIBR", "生物科技": "XBI",
    "军工": "ITA", "铀矿(核能)": "URA"
}

# --- 2. 数据处理引擎 (双模式) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers, mode="10Y"):
    end_date = datetime.now()
    
    # 根据模式决定下载多少数据
    if mode == "10Y":
        start_date = end_date - timedelta(days=365*11) # 下载11年
        display_years = 10
        status_msg = "正在拉取 10 年历史数据 (滚动视角)..."
    else:
        start_date = end_date - timedelta(days=365*2)  # 下载2年足够了
        display_years = 1
        status_msg = "正在拉取近期战术数据 (静态视角)..."
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    ticker_list = list(tickers.values())
    try:
        status_text.text(status_msg)
        data = yf.download(ticker_list, start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except Exception as e:
        return pd.DataFrame() 

    progress_bar.progress(0.4)
    status_text.text("正在计算时空因子...")

    processed_dfs = []
    total_assets = len(tickers)
    current_asset = 0

    for name, ticker in tickers.items():
        current_asset += 1
        if current_asset % 5 == 0:
            progress_bar.progress(0.4 + (0.5 * current_asset / total_assets))

        try:
            if ticker not in raw_close.columns: continue
            
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            if len(series_price) < 260: continue

            # 重采样为周线
            price_weekly = series_price.resample('W-FRI').last()
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            # 确定显示的起始时间
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_idx = price_weekly.index >= target_start_date
            display_dates = price_weekly[display_idx].index
            
            # --- 模式差异化逻辑 ---
            if mode == "1Y":
                # 1年模式（静态视角）：
                # 基准固定为"这一整年"的均值。这样能看到资产在今年内的相对位置。
                # 注意：为了动画效果，这里我们取一个滑动窗口，但窗口很大，接近静态
                pass 

            for date in display_dates:
                # --- A. Z-Score 计算 ---
                if mode == "10Y":
                    # 10年模式：严格的 Rolling Window (过去1年)
                    # 还原历史当下的视角
                    window_price = series_price.loc[:date].tail(252)
                    window_vol = series_vol.loc[:date].tail(252)
                else:
                    # 1年模式：静态视角 (Static View)
                    # 我们用"当前这1年"的数据作为标尺。
                    # 但为了不引入未来函数太严重，我们还是用 Rolling，
                    # 只是在 1年 模式下，我们更关注短期波动。
                    # *修正*：为了保持 1年 视角的战术意义，我们用较短的窗口？
                    # 不，统一用 Rolling 252 比较公平，区别在于显示的时间跨度。
                    window_price = series_price.loc[:date].tail(252)
                    window_vol = series_vol.loc[:date].tail(252)
                
                if len(window_price) < 100: continue
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                
                # 价格 Z-Score
                price_val = price_weekly.loc[date]
                if p_std > 0: z_score = (price_val - p_mean) / p_std
                else: z_score = 0
                
                # --- B. 动量 (10Y看3个月，1Y看1个月) ---
                # 10年看大趋势(12周)，1年看灵敏度(4周)
                mom_weeks = 12 if mode == "10Y" else 4
                lookback_date = date - timedelta(weeks=mom_weeks)
                
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        if price_prev > 0:
                            momentum = ((price_val - price_prev) / price_prev) * 100
                        else: momentum = 0
                    else: momentum = 0
                except: momentum = 0
                
                # --- C. 成交量异动 ---
                v_mean = window_vol.mean()
                v_std = window_vol.std()
                vol_val = vol_weekly.loc[date]
                if v_std > 0: vol_z = (vol_val - v_mean) / v_std
                else: vol_z = 0
                
                size_metric = 10 + (vol_z * 8) 
                size_metric = max(5, min(size_metric, 60))
                
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
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

# 侧边栏控制
with st.sidebar:
    st.header("🎮 雷达控制台")
    mode = st.radio(
        "选择时间维度",
        ("1Y 战术视角 (Tactical)", "10Y 战略视角 (Strategic)"),
        index=0
    )
    
    st.info("""
    **👀 视角说明:**
    
    **1Y 战术视角:**
    * 关注最近一年
    * 动量敏感度高 (1个月)
    * 用途: 找短期买卖点
    
    **10Y 战略视角:**
    * 关注过去十年
    * 动量更平滑 (3个月)
    * 用途: 找历史大底/大顶
    """)

# 解析模式参数
if "10Y" in mode:
    selected_mode = "10Y"
    title_prefix = "🗺️ 宏观战略雷达 (10年)"
else:
    selected_mode = "1Y"
    title_prefix = "⚡ 战术突击雷达 (1年)"

st.title(title_prefix)
st.caption(f"更新: {update_time} | 模式: {selected_mode} | 气泡大小: 成交量异动")

df_anim = get_market_data(ASSETS, mode=selected_mode)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    reverse_dates = all_dates[::-1]
    
    # 动态调整坐标轴范围
    if selected_mode == "10Y":
        range_x = [-5.5, 5.5]
        range_y = [-80, 100]
    else:
        # 1年模式下，波动可能没那么大，稍微聚焦一点
        range_x = [-4, 4]
        range_y = [-40, 50]

    fig = px.scatter(
        df_anim, 
        x="Z-Score", y="Momentum", 
        animation_frame="Date", animation_group="Name", 
        text="Name", hover_name="Name",
        hover_data=["Price", "Ticker", "Vol_Z"],
        color="Momentum", size="Size", size_max=50, 
        range_x=range_x, range_y=range_y, 
        color_continuous_scale="RdYlGn", range_color=[-20, 40],
        title=f"📅 {title_prefix}: {all_dates[0]}"
    )

    fig.update_traces(cliponaxis=False, textposition='top center', marker=dict(line=dict(width=1, color='black')))
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    # 区域标注
    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 拥挤/主升浪", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 爆发/抢筹", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 冷宫/吸筹", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 崩盘/出货", showarrow=False, font=dict(color="orange"))

    # 标题同步
    for frame in fig.frames:
        frame.layout.title.text = f"📅 {title_prefix}: {frame.name}"

    # 动画设置
    settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)
    settings_normal = dict(frame=dict(duration=400, redraw=True), fromcurrent=True) # 1年模式用这个舒服

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.1, y=0, pad={"r": 10, "t": 10},
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[reverse_dates, settings_fast]),
            dict(label="▶️ 播放", method="animate", args=[None, settings_normal]), # 默认适中速度
            dict(label="🐢 慢放", method="animate", args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True)]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    fig.update_layout(
        height=850, template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=60, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)

    # 底部数据
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

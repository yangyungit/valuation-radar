import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观时光机 (10年珍藏版)", layout="wide")

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

# --- 2. 数据处理 (支持超长跨度) ---
@st.cache_data(ttl=3600*12) # 缓存时间加长到12小时，因为下载10年数据比较久
def get_market_animation_data(tickers):
    end_date = datetime.now()
    # 下载 11 年的数据（多1年是为了计算最开始那一天的均值）
    start_date = end_date - timedelta(days=365*11) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    ticker_list = list(tickers.values())
    try:
        status_text.text("正在从华尔街搬运 10 年的历史数据 (约需30-60秒)...")
        # auto_adjust=True 修复拆股/分红导致的价格断层
        raw_data = yf.download(ticker_list, start=start_date, end=end_date, progress=False, auto_adjust=True)['Close']
    except Exception as e:
        st.error(f"数据下载失败: {e}")
        return pd.DataFrame() 

    progress_bar.progress(0.4)
    status_text.text("正在进行 12 万条数据的时空清洗...")

    processed_dfs = []
    total_assets = len(tickers)
    current_asset = 0

    for name, ticker in tickers.items():
        current_asset += 1
        # 偶尔更新一下进度条
        if current_asset % 5 == 0:
            progress_bar.progress(0.4 + (0.5 * current_asset / total_assets))

        try:
            if ticker not in raw_data.columns:
                continue
            
            series = raw_data[ticker].dropna()
            if len(series) < 260: continue

            # 重采样为"周" (Weekly)，减少动画帧数，保证流畅
            series_weekly = series.resample('W-FRI').last() 
            
            # --- 核心算法：滚动时间窗口 (Rolling Window) ---
            # 我们只取最近 10 年的数据来展示
            # 但每一天的 Z-Score，是基于它"当时的前一年"来计算的
            
            target_start_date = end_date - timedelta(days=365*10)
            display_series = series_weekly[series_weekly.index >= target_start_date]
            
            for date, price in display_series.items():
                # 1. 动态 Z-Score: 获取"当时"过去一年的数据切片
                # 这样才能还原当时的视角，不受未来涨跌影响
                past_year_slice = series.loc[:date].tail(252)
                
                if len(past_year_slice) < 100: continue # 数据不够不算

                rolling_mean = past_year_slice.mean()
                rolling_std = past_year_slice.std()
                
                if rolling_std == 0: continue

                z_score = (price - rolling_mean) / rolling_std
                
                # 2. 动量回溯 (3个月)
                lookback_date = date - timedelta(weeks=12)
                try:
                    # 在原始日线数据里找
                    idx = series.index.searchsorted(lookback_date)
                    if idx < len(series) and idx >= 0:
                        price_prev = series.iloc[idx]
                        if price_prev > 0:
                            momentum = ((price - price_prev) / price_prev) * 100
                        else: momentum = 0
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

st.title("🎢 宏观时光机 (10-Year Edition)")
st.caption(f"数据范围：过去 10 年 | 资产数：{len(ASSETS)} | 算法：滚动 Z-Score (还原历史真实估值)")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    reverse_dates = all_dates[::-1]
    
    # 算出数据起止时间，显示在界面上
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
        hover_data=["Price", "Ticker"],
        color="Momentum", 
        # 锁定坐标轴：虽然是10年，但Z-Score是标准化的，所以坐标轴可以固定
        range_x=[-4.5, 4.5], 
        range_y=[-60, 80], # 稍微扩大Y轴范围，10年里有些极端波动  
        color_continuous_scale="RdYlGn",
        range_color=[-20, 40],
        title=f"📅 历史回放 ({start_str} 至 {end_str})"
    )

    fig.update_traces(
        textposition='top center', 
        marker=dict(size=14, line=dict(width=1, color='black'))
    )
    
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", 
                       text="🔥 拥挤/泡沫", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", 
                       text="💎 捡漏/爆发", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", 
                       text="🧊 冷宫/崩溃", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", 
                       text="⚠️ 价值陷阱", showarrow=False, font=dict(color="orange"))

    # --- 播放控制台 ---
    # 默认速度设为 50ms (极速)，因为数据量大
    # 用户想看细节可以用"慢放"
    
    animation_settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)
    animation_settings_slow = dict(frame=dict(duration=500, redraw=True), fromcurrent=True)

    fig.layout.updatemenus = [
        dict(
            type="buttons",
            showactive=False,
            direction="left",
            x=0.1, y=0, 
            pad={"r": 10, "t": 10},
            buttons=[
                dict(
                    label="⏪ 倒放",
                    method="animate",
                    args=[reverse_dates, animation_settings_fast]
                ),
                dict(
                    label="▶️ 极速浏览 (10年)",
                    method="animate",
                    args=[None, animation_settings_fast]
                ),
                dict(
                    label="🐢 慢速研究",
                    method="animate",
                    args=[None, animation_settings_slow]
                ),
                dict(
                    label="⏸️ 暂停",
                    method="animate",
                    args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))]
                )
            ]
        )
    ]

    fig.update_layout(
        height=850,
        template="plotly_dark",
        xaxis_title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出  |  资金流入 -->",
        margin=dict(l=40, r=40, t=40, b=40),
        sliders=[dict(currentvalue={"prefix": "时间: "}, pad={"t": 50})]
    )

    st.plotly_chart(fig, use_container_width=True)

    # 底部显示最新一期数据
    latest_date = df_anim['Date'].iloc[-1]
    st.markdown(f"### 📊 市场定格 ({latest_date})")
    df_latest = df_anim[df_anim['Date'] == latest_date]
    st.dataframe(
        df_latest[['Name', 'Ticker', 'Price', 'Z-Score', 'Momentum']]
        .sort_values(by="Z-Score", ascending=False)
        .style.background_gradient(subset=['Momentum'], cmap='RdYlGn'), 
        use_container_width=True
    )

else:
    st.info("正在初始化长周期模型，请稍等...")

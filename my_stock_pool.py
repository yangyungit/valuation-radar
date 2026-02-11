import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="核心标的池 - 动态追踪", layout="wide")

# --- 1. 您的专属标的池 ---
PORTFOLIO_CONFIG = {
    "A: 防守股": ["GLD", "WMT", "TJX", "RSG", "LLY", "COST", "KO", "V", "BRK-B", "ISRG", "LMT", "WM", "JNJ", "LIN"],
    "B: 核心资产": ["COST", "GOOGL", "MSFT", "AMZN", "PWR", "CACI", "AAPL", "MNST", "LLY", "XOM", "CVX", "WM"],
    "C: 时代之王": ["TSLA", "VRT", "NVDA", "PLTR", "NOC", "XAR", "XLP", "MS", "GS", "LMT", "ANET", "ETN", "BTC-USD", "GOLD"]
}

# --- 2. 核心计算引擎 (完全继承宏观雷达的 Z-Score 与 Momentum 时序逻辑) ---
def get_unique_tickers():
    all_tickers = []
    for tickers in PORTFOLIO_CONFIG.values():
        all_tickers.extend(tickers)
    return list(set(all_tickers))

def get_category_label(ticker):
    """给标的打上 A/B/C 标签"""
    labels = []
    for section, tickers in PORTFOLIO_CONFIG.items():
        if ticker in tickers:
            labels.append(section.split(":")[0])
    return ", ".join(labels)

@st.cache_data(ttl=3600*12) # 缓存半天
def get_market_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2.5) # 取2.5年数据，保证Z-score能完整回溯1年
    display_years = 1
    rolling_window = 252

    tickers = get_unique_tickers()
    try:
        data = yf.download(tickers, start=start_date, end=end_date, group_by='ticker', progress=False)
    except Exception as e:
        st.error(f"数据下载失败: {e}")
        return pd.DataFrame()

    processed_dfs = []

    for ticker in tickers:
        try:
            df = data[ticker] if len(tickers) > 1 else data
            
            if 'Close' not in df.columns: continue
            
            # 剔除空值，对齐美股与加密货币的时差
            df = df.dropna(subset=['Close'])

            if len(df) < rolling_window + 20: continue

            series_price = df['Close']
            # 按周五重采样，平滑动画
            price_weekly = series_price.resample('W-FRI').last()

            # 只保留最近一年的日期用于动画进度条
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index

            cat_label = get_category_label(ticker)

            for date in display_dates:
                # 滚动计算 Z-Score
                window_price = series_price.loc[:date].tail(rolling_window)
                if len(window_price) < rolling_window * 0.9: continue

                p_mean = window_price.mean()
                p_std = window_price.std()
                if p_std == 0: continue

                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std

                # 滚动计算 4周动量 (Momentum)
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0

                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'),
                    "Ticker": ticker,
                    "Category": cat_label,
                    "Z-Score": round(float(z_score), 2),
                    "Momentum": round(float(momentum), 2),
                    "Price": round(float(price_val), 2)
                })
        except Exception:
            continue

    full_df = pd.DataFrame(processed_dfs)
    if not full_df.empty:
        full_df = full_df.sort_values(by="Date")
    return full_df

# --- 3. 页面渲染 (带一年的进度条和均匀小圆点) ---
st.title("🎯 核心标的池 - 动态追踪 (一周年回放版)")

# 侧边栏
st.sidebar.header("⚙️ 显示设置")
show_categories = st.sidebar.multiselect(
    "选择显示的分类", ["A", "B", "C"], default=["A", "B", "C"]
)

with st.spinner("正在构建长周期时序数据，生成一周年进度条..."):
    df_anim = get_market_data()

if not df_anim.empty:
    # 筛选分类
    mask = df_anim['Category'].apply(lambda x: any(c in x for c in show_categories))
    filtered_df = df_anim[mask].copy()

    if filtered_df.empty:
        st.warning("没有符合筛选条件的数据。")
    else:
        all_dates = sorted(filtered_df['Date'].unique())
        
        # 固定坐标轴范围以防动画跳动
        x_min, x_max = filtered_df["Z-Score"].min() - 0.5, filtered_df["Z-Score"].max() + 0.5
        y_min, y_max = filtered_df["Momentum"].min() - 5, filtered_df["Momentum"].max() + 5

        # 保留属于你A/B/C池的专属颜色分类
        color_map = {
            "A": "#2ca02c", "B": "#1f77b4", "C": "#d62728",
            "A, B": "#17becf", "A, C": "#e377c2", "B, C": "#bcbd22"
        }

        # 核心雷达图
        fig = px.scatter(
            filtered_df,
            x="Z-Score", y="Momentum",
            animation_frame="Date", animation_group="Ticker", # 激活进度条动画
            text="Ticker", hover_name="Ticker",
            hover_data=["Category", "Price"],
            color="Category",
            color_discrete_map=color_map,
            range_x=[x_min, x_max], range_y=[y_min, y_max],
            title="左: 便宜 (低 Z-Score) | 右: 昂贵 (高 Z-Score) <---> 下: 资金流出 | 上: 资金流入"
        )

        # 强制设置为小圆点，去掉气泡大小差异，完全复刻宏观雷达样式
        fig.update_traces(
            cliponaxis=False,
            textposition='top center',
            marker=dict(size=14, opacity=0.9, line=dict(width=1, color='DarkSlateGrey'))
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        
        # 动态区域标注
        fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 黄金坑", showarrow=False, font=dict(color="green"))
        fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 顶部狂热", showarrow=False, font=dict(color="red"))
        fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="❄️ 深度冻结", showarrow=False, font=dict(color="blue"))
        fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 顶部派发", showarrow=False, font=dict(color="orange"))

        # 播放/倒放按钮控制 (完全复刻宏观雷达)
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

        fig.layout.sliders[0].active = len(all_dates) - 1
        fig.layout.sliders[0].currentvalue.prefix = "" 
        fig.layout.sliders[0].currentvalue.font.size = 20
        fig.layout.sliders[0].pad = {"t": 50} 
        
        fig.update_layout(height=750, margin=dict(l=40, r=40, t=40, b=100))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 最新一期的数据表
        st.markdown("### 📊 最新一期数据快照")
        latest_date = filtered_df['Date'].max()
        df_latest = filtered_df[filtered_df['Date'] == latest_date]
        
        st.dataframe(
            df_latest[["Ticker", "Category", "Price", "Z-Score", "Momentum"]]
            .sort_values("Momentum", ascending=False)
            .style.background_gradient(subset=["Z-Score"], cmap="RdYlGn_r")
            .format({"Price": "{:.2f}", "Z-Score": "{:.2f}", "Momentum": "{:+.2f}%"}),
            use_container_width=True
        )
else:
    st.info("等待数据加载，请稍候...")
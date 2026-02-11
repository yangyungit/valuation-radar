import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="核心资产雷达 (动量热力版)", layout="wide")

# --- 1. 您的专属标的池 ---
PORTFOLIO_CONFIG = {
    "A (防守)": ["GLD", "WMT", "TJX", "RSG", "LLY", "COST", "KO", "V", "BRK-B", "ISRG", "LMT", "WM", "JNJ", "LIN"],
    "B (核心)": ["COST", "GOOGL", "MSFT", "AMZN", "PWR", "CACI", "AAPL", "MNST", "LLY", "XOM", "CVX", "WM"],
    "C (时代之王)": ["TSLA", "VRT", "NVDA", "PLTR", "NOC", "XAR", "XLP", "MS", "GS", "LMT", "ANET", "ETN", "BTC-USD", "GOLD"]
}

# --- 2. 核心计算引擎 (完全采用原版宏观雷达底层防错逻辑) ---
def get_unique_tickers():
    all_tickers = []
    for tickers in PORTFOLIO_CONFIG.values():
        all_tickers.extend(tickers)
    return list(set(all_tickers))

def get_category_label(ticker):
    for section, tickers in reversed(PORTFOLIO_CONFIG.items()):
        if ticker in tickers:
            return section.split(" ")[0] 
    return "Other"

@st.cache_data(ttl=3600*6)
def get_market_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2.5) 
    display_years = 1
    rolling_window = 252

    tickers = get_unique_tickers()
    try:
        # 关键修复1：加入 auto_adjust=True (前复权)，摒弃 group_by，防止分红除息导致的动量断层
        data = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
    except Exception as e:
        return pd.DataFrame()

    processed_dfs = []

    for ticker in tickers:
        try:
            if ticker not in raw_close.columns: continue
            
            series_price = raw_close[ticker].dropna()
            if len(series_price) < rolling_window + 20: continue

            price_weekly = series_price.resample('W-FRI').last()

            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index

            cat_label = get_category_label(ticker)

            for date in display_dates:
                window_price = series_price.loc[:date].tail(rolling_window)
                if len(window_price) < rolling_window * 0.9: continue

                p_mean = window_price.mean()
                p_std = window_price.std()
                if p_std == 0: continue

                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std

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
        # 关键修复2：极其严格的双重排序！强制 Plotly 每一帧的数据索引死死咬住，杜绝气泡“张冠李戴”
        full_df = full_df.sort_values(by=["Date", "Ticker"])
    return full_df

# --- 3. 页面渲染 (完全复刻原版 UI) ---
st.title("🎯 核心资产雷达 (动量热力版)")

st.sidebar.header("⚙️ 筛选工具")
selected_cats = st.sidebar.multiselect(
    "过滤分类 (A/B/C)", ["A", "B", "C"], default=["A", "B", "C"]
)

with st.spinner("正在加载深色模式与长周期数据..."):
    df_anim = get_market_data()

if not df_anim.empty:
    filtered_df = df_anim[df_anim['Category'].isin(selected_cats)].copy()

    if filtered_df.empty:
        st.warning("没有符合筛选条件的数据。")
    else:
        all_dates = sorted(filtered_df['Date'].unique())
        
        range_x = [-4.0, 4.0]
        range_y = [-40, 50] 

        fig = px.scatter(
            filtered_df, 
            x="Z-Score", y="Momentum", 
            animation_frame="Date", animation_group="Ticker", 
            text="Ticker", hover_name="Category",
            hover_data=["Price"], 
            color="Momentum", 
            range_x=range_x, range_y=range_y, 
            color_continuous_scale="RdYlGn", range_color=[-20, 40], 
            title=""
        )

        fig.update_traces(
            cliponaxis=False, 
            textposition='top center', 
            marker=dict(size=14, line=dict(width=1, color='black'))
        )
        
        fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
        fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

        fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 强势/拥挤", showarrow=False, font=dict(color="red"))
        fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 反转/启动", showarrow=False, font=dict(color="#00FF00"))
        fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 弱势/冷宫", showarrow=False, font=dict(color="gray"))
        fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 补跌/崩盘", showarrow=False, font=dict(color="orange"))

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
        
        fig.update_layout(
            height=750, template="plotly_dark",
            margin=dict(l=40, r=40, t=20, b=100),
            xaxis=dict(visible=True, showticklabels=True, title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->"),
            yaxis=dict(title="<-- 资金流出  |  资金流入 -->")
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📊 最新数据快照")
        latest_date = filtered_df['Date'].iloc[-1]
        df_latest = filtered_df[filtered_df['Date'] == latest_date]
        
        display_cols = ['Ticker', 'Category', 'Z-Score', 'Momentum', 'Price']
        
        st.dataframe(
            df_latest[display_cols]
            .sort_values(by="Z-Score", ascending=False)
            .style
            .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40),
            use_container_width=True
        )

else:
    st.info("等待数据加载，请稍候...")
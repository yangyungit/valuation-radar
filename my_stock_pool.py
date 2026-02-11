import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 全局配置：深色模式与页面标题
st.set_page_config(page_title="核心资产雷达 (动量热力版)", layout="wide")
# ---------------------------------------------------------

# --- 1. 您的专属标的池 ---
# 注意：如果一个标的同时出现在多个池子里，下面的代码会优先取最下面的分类（C优于B优于A）
PORTFOLIO_CONFIG = {
    "A (防守)": ["GLD", "WMT", "TJX", "RSG", "LLY", "COST", "KO", "V", "BRK-B", "ISRG", "LMT", "WM", "JNJ", "LIN"],
    "B (核心)": ["COST", "GOOGL", "MSFT", "AMZN", "PWR", "CACI", "AAPL", "MNST", "LLY", "XOM", "CVX", "WM"],
    "C (时代之王)": ["TSLA", "VRT", "NVDA", "PLTR", "NOC", "XAR", "XLP", "MS", "GS", "LMT", "ANET", "ETN", "BTC-USD", "GOLD"]
}

# --- 2. 核心计算引擎 ---
def get_unique_tickers():
    all_tickers = []
    for tickers in PORTFOLIO_CONFIG.values():
        all_tickers.extend(tickers)
    return list(set(all_tickers))

def get_category_label(ticker):
    """给标的打上单一标签，强制不重叠"""
    # 倒序遍历，优先级 C > B > A
    for section, tickers in reversed(PORTFOLIO_CONFIG.items()):
        if ticker in tickers:
            return section.split(" ")[0] # 只返回 A, B, 或 C
    return "Other"

@st.cache_data(ttl=3600*6) # 缓存6小时
def get_market_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2.5) # 取2.5年数据用于计算稳定的Z-Score
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
            # 按周五重采样，平滑动画路径
            price_weekly = series_price.resample('W-FRI').last()

            # 只保留最近一年的日期用于动画展示
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index

            # 获取单一分类标签
            cat_label = get_category_label(ticker)

            for date in display_dates:
                # 滚动计算 Z-Score (估值位置)
                window_price = series_price.loc[:date].tail(rolling_window)
                if len(window_price) < rolling_window * 0.9: continue

                p_mean = window_price.mean()
                p_std = window_price.std()
                if p_std == 0: continue

                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std

                # 滚动计算 4周动量 (Momentum / 资金流向代理)
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
                    "Category": cat_label, # 用于鼠标悬停显示
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

# --- 3. 页面渲染 (深色主题 + 热力力图配色) ---
st.title("🎯 核心资产雷达 (动量热力版)")

# 侧边栏过滤器
st.sidebar.header("⚙️ 筛选工具")
selected_cats = st.sidebar.multiselect(
    "过滤分类 (A/B/C)", ["A", "B", "C"], default=["A", "B", "C"]
)

with st.spinner("正在加载深色模式与长周期数据..."):
    df_anim = get_market_data()

if not df_anim.empty:
    # 筛选分类
    filtered_df = df_anim[df_anim['Category'].isin(selected_cats)].copy()

    if filtered_df.empty:
        st.warning("没有符合筛选条件的数据。")
    else:
        all_dates = sorted(filtered_df['Date'].unique())
        
        # 计算颜色映射的动态范围 (让红绿对比更鲜明)
        mom_min = filtered_df["Momentum"].quantile(0.05) # 去掉极端的5%
        mom_max = filtered_df["Momentum"].quantile(0.95)

        # --- 核心雷达图配置 (关键修改) ---
        fig = px.scatter(
            filtered_df,
            x="Z-Score", y="Momentum",
            animation_frame="Date", animation_group="Ticker",
            text="Ticker", 
            hover_name="Category", # 鼠标放上去显示分类
            hover_data=["Price", "Z-Score", "Momentum"],
            
            # 【关键修改】颜色由“动量”决定，使用红绿热力图
            color="Momentum",
            color_continuous_scale="RdYlGn", # 红-黄-绿 渐变
            range_color=[mom_min, mom_max], # 动态设定颜色范围
            
            title="<b>核心资产相对位置图</b>"
        )

        # 【关键修改】样式微调：深色背景、扎实小圆点、清晰坐标轴
        fig.update_traces(
            cliponaxis=False,
            textposition='top center',
            textfont=dict(color='white'), # 深色背景下文字改白色
            # size=14, opacity=1.0 (不透明), 白色细描边
            marker=dict(size=14, opacity=1.0, line=dict(width=1, color='white'))
        )
        
        # 使用深色模板，瞬间提升质感
        fig.update_layout(
            template="plotly_dark", 
            height=700, 
            margin=dict(l=60, r=40, t=60, b=100),
            # 清晰的坐标轴标签
            xaxis=dict(title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->", showgrid=True, gridcolor='#444'),
            yaxis=dict(title="<-- 资金流出 (弱势)  |  资金流入 (强势) -->", showgrid=True, gridcolor='#444'),
            # 隐藏颜色条，让画面更干净(可选)
            coloraxis_showscale=False
        )
        
        # 添加中心十字辅助线
        fig.add_hline(y=0, line_dash="dash", line_color="#888")
        fig.add_vline(x=0, line_dash="dash", line_color="#888")
        
        # 动态区域标注 (适配深色背景的亮色文字)
        fig.add_annotation(x=0.02, y=0.98, xref="paper", yref="paper", text="💎 黄金坑 (便宜+启动)", showarrow=False, font=dict(color="#00FF00", size=14))
        fig.add_annotation(x=0.98, y=0.98, xref="paper", yref="paper", text="🔥 顶部狂热 (贵+强势)", showarrow=False, font=dict(color="#FF3333", size=14), xanchor="right")
        fig.add_annotation(x=0.02, y=0.02, xref="paper", yref="paper", text="🧊 深度冻结 (便宜+弱势)", showarrow=False, font=dict(color="#8888FF", size=14), yanchor="bottom")
        fig.add_annotation(x=0.98, y=0.02, xref="paper", yref="paper", text="⚠️ 顶部派发 (贵+弱势)", showarrow=False, font=dict(color="#FFA500", size=14), xanchor="right", yanchor="bottom")

        # 动画播放控件配置
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

        # 进度条样式优化
        fig.layout.sliders[0].active = len(all_dates) - 1
        fig.layout.sliders[0].currentvalue.prefix = "当前日期: " 
        fig.layout.sliders[0].currentvalue.font.size = 16
        fig.layout.sliders[0].pad = {"t": 50} 
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 最新一期数据表 (同样采用热力图配色)
        st.markdown("### 📋 最新截面数据")
        latest_date = filtered_df['Date'].max()
        df_latest = filtered_df[filtered_df['Date'] == latest_date].copy()
        
        # 数据表也用动量上色，保持一致性
        st.dataframe(
            df_latest[["Ticker", "Category", "Price", "Z-Score", "Momentum"]]
            .sort_values("Momentum", ascending=False)
            .style.background_gradient(subset=["Momentum"], cmap="RdYlGn", vmin=mom_min, vmax=mom_max)
            .format({"Price": "{:.2f}", "Z-Score": "{:.2f}", "Momentum": "{:+.2f}%"}),
            use_container_width=True
        )
else:
    st.info("等待数据加载，请稍候...")
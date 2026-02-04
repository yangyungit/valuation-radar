import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px

# ---------------------------------------------------------
# 1. 您的专属标的池
# ---------------------------------------------------------
PORTFOLIO_CONFIG = {
    "A: 防守股": [
        "GLD", "WMT", "TJX", "RSG", "LLY", "COST", "KO", "V", 
        "BRK-B", "ISRG", "LMT", "WM", "JNJ", "LIN"
    ],
    "B: 核心资产": [
        "COST", "GOOGL", "MSFT", "AMZN", "PWR", "CACI", "AAPL", 
        "MNST", "LLY", "XOM", "CVX", "WM"
    ],
    "C: 时代之王": [
        "TSLA", "VRT", "NVDA", "PLTR", "NOC", "XAR", "XLP", 
        "MS", "GS", "LMT", "ANET", "ETN", "BTC-USD", "GOLD"
    ]
}

# ---------------------------------------------------------
# 2. 核心计算逻辑 (增强容错版)
# ---------------------------------------------------------
def get_unique_tickers(config):
    all_tickers = []
    for section, tickers in config.items():
        all_tickers.extend(tickers)
    return list(set(all_tickers))

def get_category_label(ticker):
    """给标的打上 A/B/C 标签"""
    labels = []
    for section, tickers in PORTFOLIO_CONFIG.items():
        if ticker in tickers:
            labels.append(section.split(":")[0]) 
    return ", ".join(labels)

@st.cache_data(ttl=300)
def get_radar_data():
    tickers = get_unique_tickers(PORTFOLIO_CONFIG)
    if not tickers:
        return pd.DataFrame()
    
    # 批量下载数据
    try:
        data = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    except Exception as e:
        st.error(f"数据下载失败: {e}")
        return pd.DataFrame()
    
    rows = []
    for ticker in tickers:
        try:
            # 兼容处理：如果只有一个标的，data层级会少一层
            df = data[ticker] if len(tickers) > 1 else data
            
            # 数据完整性检查
            if df.empty or len(df) < 20:
                continue
            
            # 必须包含 Close 列
            if 'Close' not in df.columns:
                continue

            # --- 指标计算 ---
            
            # 1. 相对估值
            current_price = df['Close'].iloc[-1]
            # 容错：如果最后价格是 NaN
            if pd.isna(current_price):
                continue

            low_52w = df['Low'].min()
            high_52w = df['High'].max()
            
            if high_52w == low_52w:
                valuation_score = 0.5
            else:
                valuation_score = (current_price - low_52w) / (high_52w - low_52w)
            
            # 2. 资金流向 (5日涨跌幅)
            price_5d_ago = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
            if price_5d_ago == 0 or pd.isna(price_5d_ago):
                flow_score = 0
            else:
                flow_score = (current_price - price_5d_ago) / price_5d_ago * 100
            
            # 3. 波动率 (用于气泡大小)
            # 填充 NaN 为 0，避免计算报错
            pct_change = df['Close'].pct_change().fillna(0)
            volatility = pct_change.std() * 100
            
            # 关键修复：Plotly size 必须 > 0，且不能为 NaN
            if pd.isna(volatility) or volatility <= 0:
                volatility = 1.0 # 给一个默认大小
            
            rows.append({
                "Ticker": ticker,
                "Category": get_category_label(ticker),
                "Price": round(float(current_price), 2),
                "Valuation(0-1)": round(float(valuation_score), 2),
                "MoneyFlow(%)": round(float(flow_score), 2),
                "Volatility": round(float(volatility), 2)
            })
            
        except Exception:
            continue
            
    return pd.DataFrame(rows)

# ---------------------------------------------------------
# 3. 页面渲染
# ---------------------------------------------------------
st.set_page_config(page_title="Alpha Pool Radar", layout="wide")

st.title("🎯 核心标的池 - 估值与资金雷达")

# 侧边栏
st.sidebar.header("⚙️ 显示设置")
show_categories = st.sidebar.multiselect(
    "选择显示的分类", ["A", "B", "C"], default=["A", "B", "C"]
)

# 获取数据
with st.spinner("正在计算 52周相对估值 与 资金流向..."):
    df = get_radar_data()

if not df.empty:
    # 再次清洗：确保绘图所需的列没有 NaN
    df = df.dropna(subset=["Valuation(0-1)", "MoneyFlow(%)", "Volatility"])
    
    # 筛选分类
    mask = df['Category'].apply(lambda x: any(c in x for c in show_categories))
    filtered_df = df[mask].copy()
    
    if filtered_df.empty:
        st.warning("没有符合筛选条件的数据。")
    else:
        # 统计区
        col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
        with col_kpi1:
            st.metric("监控标的总数", len(filtered_df))
        with col_kpi2:
            top_flow = filtered_df.loc[filtered_df['MoneyFlow(%)'].idxmax()]
            st.metric("资金流入最强", f"{top_flow['Ticker']}", f"+{top_flow['MoneyFlow(%)']}%")
        with col_kpi3:
            cheapest = filtered_df.loc[filtered_df['Valuation(0-1)'].idxmin()]
            st.metric("相对估值最低", f"{cheapest['Ticker']}", f"{(cheapest['Valuation(0-1)']*100):.0f}% 分位")

        # --- 核心雷达图 ---
        st.markdown("### 🧭 估值-资金象限图")
        
        # 定义颜色映射（移除不完全的映射，让 Plotly 自动分配未定义的组合）
        # 这样即使出现 "A, C" 这种组合也不会报错
        color_map = {
            "A": "#2ca02c", # 绿
            "B": "#1f77b4", # 蓝
            "C": "#d62728", # 红
            "A, B": "#17becf" # 青
        }

        fig = px.scatter(
            filtered_df,
            x="Valuation(0-1)",
            y="MoneyFlow(%)",
            color="Category",
            text="Ticker",
            size="Volatility", 
            hover_data=["Price"],
            # 只有当分类在字典里时才强制颜色，否则自动
            color_discrete_map=color_map, 
            height=600,
            title="左: 便宜(地板价) | 右: 昂贵(天花板) <---> 下: 资金流出 | 上: 资金流入"
        )
        
        # 辅助线
        fig.add_vline(x=0.5, line_dash="dash", line_color="gray")
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        
        # 区域标注
        y_max = filtered_df['MoneyFlow(%)'].max()
        y_min = filtered_df['MoneyFlow(%)'].min()
        # 增加一些缓冲空间防止文字重叠
        y_range = y_max - y_min
        
        fig.add_annotation(x=0.05, y=y_max, text="💎 黄金坑", showarrow=False, font=dict(color="green"))
        fig.add_annotation(x=0.95, y=y_max, text="🔥 顶部狂热", showarrow=False, font=dict(color="red"))
        fig.add_annotation(x=0.05, y=y_min, text="❄️ 深度冻结", showarrow=False, font=dict(color="blue"))
        fig.add_annotation(x=0.95, y=y_min, text="⚠️ 顶部派发", showarrow=False, font=dict(color="orange"))

        fig.update_traces(textposition='top center', marker=dict(opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
        fig.update_layout(
            xaxis_title="相对估值 (0=年内最低, 1=年内最高)", 
            yaxis_title="5日资金流向 (涨跌幅 %)",
            xaxis=dict(range=[-0.1, 1.1]) # 稍微扩大范围防止气泡被切
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表
        with st.expander("查看详细数据表"):
            st.dataframe(
                filtered_df.sort_values("MoneyFlow(%)", ascending=False)
                .style.background_gradient(subset=["Valuation(0-1)"], cmap="RdYlGn_r")
                .format({"Price": "{:.2f}", "Valuation(0-1)": "{:.2f}", "MoneyFlow(%)": "{:+.2f}%", "Volatility": "{:.2f}"}),
                use_container_width=True
            )
else:
    st.info("等待数据加载，请稍候...")

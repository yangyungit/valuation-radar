import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import datetime

# ---------------------------------------------------------
# 1. 你的专属标的池 (带 A/B/C 自动分类)
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
# 2. 核心计算逻辑
# ---------------------------------------------------------
def get_unique_tickers(config):
    all_tickers = []
    for section, tickers in config.items():
        all_tickers.extend(tickers)
    return list(set(all_tickers))

def get_category_label(ticker):
    """给标的打上 A/B/C 标签，支持重叠"""
    labels = []
    for section, tickers in PORTFOLIO_CONFIG.items():
        if ticker in tickers:
            labels.append(section.split(":")[0]) # 只取 A, B, C
    return ", ".join(labels)

@st.cache_data(ttl=300) # 缓存5分钟
def get_radar_data():
    tickers = get_unique_tickers(PORTFOLIO_CONFIG)
    if not tickers:
        return pd.DataFrame()
    
    # 下载1年数据以计算相对估值位置，下载额外缓冲期以计算指标
    data = yf.download(tickers, period="1y", group_by='ticker', progress=False)
    
    rows = []
    for ticker in tickers:
        try:
            # 兼容单标的和多标的返回格式
            df = data[ticker] if len(tickers) > 1 else data
            
            if df.empty or len(df) < 20:
                continue
            
            # --- 指标计算 ---
            
            # 1. 相对估值 (Location in 52-week Range)
            # 公式: (当前价 - 52周最低) / (52周最高 - 52周最低)
            # 0 = 最便宜 (地板价), 1 = 最贵 (天花板价)
            current_price = df['Close'].iloc[-1]
            low_52w = df['Low'].min()
            high_52w = df['High'].max()
            
            # 避免除以0
            if high_52w == low_52w:
                valuation_score = 0.5
            else:
                valuation_score = (current_price - low_52w) / (high_52w - low_52w)
            
            # 2. 资金流向/短期动能 (Short-term Flow)
            # 使用 5日涨跌幅 + 相对强弱 综合判断
            # 这里简单用 5日涨跌幅代表短期资金态度
            price_5d_ago = df['Close'].iloc[-6] if len(df) >= 6 else df['Close'].iloc[0]
            flow_score = (current_price - price_5d_ago) / price_5d_ago * 100
            
            # 3. 辅助信息
            volatility = df['Close'].pct_change().std() * 100 # 波动率
            
            rows.append({
                "Ticker": ticker,
                "Category": get_category_label(ticker),
                "Price": round(current_price, 2),
                "Valuation(0-1)": round(valuation_score, 2), # 横轴
                "MoneyFlow(%)": round(flow_score, 2),        # 纵轴
                "Volatility": volatility
            })
            
        except Exception:
            continue
            
    return pd.DataFrame(rows)

# ---------------------------------------------------------
# 3. 页面渲染
# ---------------------------------------------------------
st.set_page_config(page_title="Alpha Pool Radar", layout="wide")

st.title("🎯 核心标的池 - 估值与资金雷达")

# 侧边栏控制
st.sidebar.header("⚙️ 显示设置")
show_categories = st.sidebar.multiselect(
    "选择显示的分类", ["A", "B", "C"], default=["A", "B", "C"]
)

# 获取数据
with st.spinner("正在计算 52周相对估值 与 资金流向..."):
    df = get_radar_data()

if not df.empty:
    # 筛选
    mask = df['Category'].apply(lambda x: any(c in x for c in show_categories))
    filtered_df = df[mask].copy()
    
    # 分区统计
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric("监控标的总数", len(filtered_df))
    with col_kpi2:
        top_flow = filtered_df.loc[filtered_df['MoneyFlow(%)'].idxmax()]
        st.metric("资金流入最强", f"{top_flow['Ticker']} ({top_flow['Category']})", f"+{top_flow['MoneyFlow(%)']}%")
    with col_kpi3:
        cheapest = filtered_df.loc[filtered_df['Valuation(0-1)'].idxmin()]
        st.metric("相对估值最低", f"{cheapest['Ticker']}", f"{(cheapest['Valuation(0-1)']*100):.0f}% 分位")

    # --- 核心雷达图 ---
    st.markdown("### 🧭 估值-资金象限图")
    
    # 构造坐标轴标签
    # X轴: 0 (Cheap) -> 1 (Expensive)
    # Y轴: Negative (Outflow) -> Positive (Inflow)
    
    fig = px.scatter(
        filtered_df,
        x="Valuation(0-1)",
        y="MoneyFlow(%)",
        color="Category",
        text="Ticker",
        size="Volatility", # 气泡大小代表波动率/活跃度
        hover_data=["Price"],
        color_discrete_map={"A": "#2ca02c", "B": "#1f77b4", "C": "#d62728", "A, B": "#17becf"},
        height=600,
        title="左: 便宜(地板价) | 右: 昂贵(天花板) <---> 下: 资金流出 | 上: 资金流入"
    )
    
    # 绘制十字准线
    fig.add_vline(x=0.5, line_dash="dash", line_color="gray", annotation_text="估值中枢")
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="资金分水岭")
    
    # 区域标注背景 (可选，增加可读性)
    fig.add_annotation(x=0.1, y=filtered_df['MoneyFlow(%)'].max(), text="💎 黄金坑 (便宜+流入)", showarrow=False, font=dict(color="green"))
    fig.add_annotation(x=0.9, y=filtered_df['MoneyFlow(%)'].max(), text="🔥 顶部狂热 (贵+流入)", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.1, y=filtered_df['MoneyFlow(%)'].min(), text="❄️ 深度冻结 (便宜+流出)", showarrow=False, font=dict(color="blue"))
    fig.add_annotation(x=0.9, y=filtered_df['MoneyFlow(%)'].min(), text="⚠️ 顶部派发 (贵+流出)", showarrow=False, font=dict(color="orange"))

    fig.update_traces(textposition='top center', marker=dict(opacity=0.8, line=dict(width=1, color='DarkSlateGrey')))
    fig.update_layout(xaxis_title="相对估值 (0=年内最低, 1=年内最高)", yaxis_title="5日资金流向 (涨跌幅 %)")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 表格展示
    with st.expander("查看详细数据表"):
        st.dataframe(
            filtered_df.sort_values("MoneyFlow(%)", ascending=False)
            .style.background_gradient(subset=["Valuation(0-1)"], cmap="RdYlGn_r") # 估值越低越绿
            .format({"Price": "{:.2f}", "Valuation(0-1)": "{:.2f}", "MoneyFlow(%)": "{:+.2f}%"}),
            use_container_width=True
        )

else:
    st.info("等待数据加载，请稍候...")
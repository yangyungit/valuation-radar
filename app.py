import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 页面配置 ---
st.set_page_config(page_title="宏观雷达 Pro", layout="wide", page_icon="🔭")

st.title("🔭 宏观雷达 (Macro Radar Pro)")
st.caption("全市场扫描：基于 **Z-Score (估值位置)** 与 **Momentum (动量趋势)** 的四象限分析")

# --- 1. 定义资产池 (The 3 Tables Strategy) ---
ASSET_POOLS = {
    "🌍 全球大类 (Global Macro)": {
        "SPY": "美股大盘", "QQQ": "纳指100", "DIA": "道琼斯", "IWM": "罗素小盘",
        "TLT": "20年美债", "IEF": "10年美债", "SHy": "短债现金",
        "GLD": "黄金", "SLV": "白银", "CPER": "铜", "USO": "原油", "UNG": "天然气",
        "UUP": "美元指数", "FXE": "欧元", "FXY": "日元",
        "BTC-USD": "比特币", "ETH-USD": "以太坊"
    },
    "🏭 美股板块 (US Sectors)": {
        "XLK": "科技", "XLF": "金融", "XLV": "医疗", 
        "XLY": "可选消费", "XLP": "必选消费", "XLE": "能源", 
        "XLI": "工业", "XLB": "材料", "XLU": "公用事业", 
        "XLRE": "地产", "XLC": "通讯"
    },
    "🚀 风格与主题 (Factors & Themes)": {
        "SMH": "半导体", "IGV": "软件SaaS", "XBI": "生物科技", "ITA": "军工国防",
        "KWEB": "中国互联网", "MCHI": "中国大盘", "EWJ": "日本股市", "VGK": "欧洲股市", "INDA": "印度股市",
        "MTUM": "动量因子", "USMV": "低波红利", "VLUE": "价值因子", "ARKK": "木头姐创新"
    }
}

# --- 2. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_bulk_data():
    # 提取所有去重代码
    all_tickers = []
    for pool in ASSET_POOLS.values():
        all_tickers.extend(list(pool.keys()))
    all_tickers = list(set(all_tickers))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) # 拉取一年多数据用于计算Z-Score
    
    try:
        # 批量下载
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data
    except Exception as e:
        st.error(f"数据拉取失败: {e}")
        return pd.DataFrame()

raw_data = get_bulk_data()

# --- 3. 指标计算核心 (Math Engine) ---
def calculate_metrics(pool_dict):
    metrics_list = []
    
    for ticker, name in pool_dict.items():
        try:
            # 处理多层级索引
            df_t = raw_data[ticker].copy()
            if df_t.empty: continue
            
            # 清洗
            df_t = df_t['Close'].dropna()
            if len(df_t) < 200: continue # 数据太短跳过
            
            curr_price = df_t.iloc[-1]
            
            # A. Z-Score (估值位置)
            # 逻辑：当前价格距离过去1年均值的偏离程度（以标准差为单位）
            # Z = (Price - MA250) / STD250
            window = 250
            ma = df_t.rolling(window).mean().iloc[-1]
            std = df_t.rolling(window).std().iloc[-1]
            z_score = (curr_price - ma) / std if std != 0 else 0
            
            # B. Momentum (动量)
            # 逻辑：过去 20 天的涨跌幅 (反映短期资金流向)
            mom_20d = (curr_price / df_t.iloc[-21] - 1) * 100
            
            # C. RSI (相对强弱 - 辅助)
            delta = df_t.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]

            metrics_list.append({
                "代码": ticker,
                "名称": name,
                "现价": curr_price,
                "Z-Score (估值)": round(z_score, 2),
                "Momentum (20日)": round(mom_20d, 2),
                "RSI": round(rsi, 0)
            })
            
        except Exception:
            continue
            
    return pd.DataFrame(metrics_list)

# --- 4. 绘图引擎 (Plot Engine) ---
def plot_radar(df_plot):
    if df_plot.empty:
        st.warning("暂无数据")
        return

    # 定义象限
    fig = px.scatter(
        df_plot,
        x="Z-Score (估值)",
        y="Momentum (20日)",
        text="名称",
        color="Momentum (20日)",
        color_continuous_scale="RdYlGn", # 红涨绿跌
        size_max=60,
        hover_data=["代码", "RSI", "现价"]
    )
    
    # 绘制十字坐标系
    fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
    
    # 标注象限含义
    fig.add_annotation(x=2, y=10, text="🔥 强势/拥挤", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=-2, y=-10, text="❄️ 弱势/冷宫", showarrow=False, font=dict(color="blue"))
    fig.add_annotation(x=-2, y=10, text="🚀 反转/启动", showarrow=False, font=dict(color="green"))
    fig.add_annotation(x=2, y=-10, text="⚠️ 补跌/崩盘", showarrow=False, font=dict(color="orange"))

    fig.update_traces(textposition='top center', marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
    fig.update_layout(
        height=600,
        xaxis_title="<-- 便宜 (低 Z-Score) | 昂贵 (高 Z-Score) -->",
        yaxis_title="<-- 资金流出 | 资金流入 (Momentum) -->",
        plot_bgcolor="#1e1e1e",
    )
    
    st.plotly_chart(fig, use_container_width=True)

# --- 5. 主界面逻辑 ---

if not raw_data.empty:
    
    # 创建三个 Tab
    tab1, tab2, tab3 = st.tabs(list(ASSET_POOLS.keys()))
    
    # --- Tab 1: 全球大类 ---
    with tab1:
        st.markdown("##### 🌍 全球资产定风向")
        st.caption("这是宏观交易员的仪表盘。用于判断**通胀预期**（看铜油金）、**流动性**（看美债美元）和**风险偏好**（看BTC纳指）。")
        df_macro = calculate_metrics(ASSET_POOLS["🌍 全球大类 (Global Macro)"])
        plot_radar(df_macro)
        with st.expander("查看详细数据表"):
            st.dataframe(df_macro.sort_values("Momentum (20日)", ascending=False), use_container_width=True)

    # --- Tab 2: 美股板块 ---
    with tab2:
        st.markdown("##### 🏭 行业轮动看资金")
        st.caption("这里展示存量资金在去哪。**防御板块**（公用/必选消费）强说明避险；**进攻板块**（科技/可选消费）强说明贪婪。")
        df_sector = calculate_metrics(ASSET_POOLS["🏭 美股板块 (US Sectors)"])
        plot_radar(df_sector)
        
        # 智能解读
        if not df_sector.empty:
            top_sector = df_sector.sort_values("Momentum (20日)", ascending=False).iloc[0]['名称']
            bot_sector = df_sector.sort_values("Momentum (20日)", ascending=True).iloc[0]['名称']
            st.info(f"💡 **当前盘面：** 资金正在猛攻 **{top_sector}**，同时抛弃 **{bot_sector}**。")
            
        with st.expander("查看详细数据表"):
            st.dataframe(df_sector.sort_values("Momentum (20日)", ascending=False), use_container_width=True)

    # --- Tab 3: 风格与主题 ---
    with tab3:
        st.markdown("##### 🚀 寻找 Alpha (细分赛道)")
        st.caption("这里是捕捉超额收益的地方。包含了**半导体、中概股、日股**以及**价值/成长因子**的对比。")
        df_theme = calculate_metrics(ASSET_POOLS["🚀 风格与主题 (Factors & Themes)"])
        plot_radar(df_theme)
        with st.expander("查看详细数据表"):
            st.dataframe(df_theme.sort_values("Momentum (20日)", ascending=False), use_container_width=True)

else:
    st.info("⏳ 正在初始化全球数据引擎，请稍候...")
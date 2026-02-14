import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="宏观全景雷达", layout="wide", page_icon="🔭")

st.title("🔭 宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场扫描：**Z-Score (估值)** vs **Momentum (动量)** | 已补全：天然气、铜、越南、日元、七姐妹等")

# --- 1. 定义超全资产池 (The Ultimate Pool) ---
ASSET_GROUPS = {
    "A: 全球国别 (Global)": {
        "SPY": "🇺🇸 美股大盘", "QQQ": "🇺🇸 纳指", "IWM": "🇺🇸 罗素小盘", 
        "EEM": "🌏 新兴市场", "VGK": "🇪🇺 欧洲", "EWJ": "🇯🇵 日本", 
        "MCHI": "🇨🇳 中国大盘", "KWEB": "🇨🇳 中概互联", 
        "INDA": "🇮🇳 印度", "VNM": "🇻🇳 越南", "EWZ": "🇧🇷 巴西"
    },
    "B: 大宗与货币 (Commodities & FX)": {
        "TLT": "🇺🇸 20年美债", "UUP": "💵 美元指数", 
        "FXY": "💴 日元", "CYB": "🇨🇳 人民币(ETF)",
        "GLD": "🥇 黄金", "SLV": "🥈 白银", 
        "USO": "🛢️ 原油", "UNG": "🔥 天然气", 
        "CPER": "🥉 铜", "DBA": "🌽 农业", 
        "BTC-USD": "₿ 比特币"
    },
    "C: 核心板块 (US Sectors)": {
        "XLK": "💻 科技", "XLF": "🏦 金融", "XLV": "💊 医疗", 
        "XLE": "⚡ 能源", "XLI": "🏗️ 工业", "XLP": "🛒 必选", 
        "XLY": "🛍️ 可选", "XLB": "🧱 材料", "XLU": "💡 公用", 
        "XLRE": "🏠 地产", "XLC": "📡 通讯"
    },
    "D: 风格与赛道 (Themes)": {
        "MAGS": "👑 七姐妹(Mag7)", "SMH": "💾 半导体", 
        "IGV": "☁️ 软件SaaS", "XBI": "🧬 生物科技", 
        "ITA": "✈️ 军工国防", "URA": "☢️ 铀矿核能", 
        "PAVE": "🛣️ 基建", "MTUM": "🚀 动量因子", 
        "USMV": "🛡️ 低波防御"
    }
}

# --- 2. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_data():
    all_tickers = []
    for group in ASSET_GROUPS.values():
        all_tickers.extend(list(group.keys()))
    all_tickers = list(set(all_tickers))
    
    end_date = datetime.now()
    # 拉取 400 天数据以计算 1年期 Z-Score
    start_date = end_date - timedelta(days=400) 
    
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data
    except: return pd.DataFrame()

raw_data = get_data()

# --- 3. 计算逻辑 ---
def calculate_metrics():
    metrics = []
    for group_name, tickers in ASSET_GROUPS.items():
        for ticker, name in tickers.items():
            try:
                # 兼容 yfinance 数据结构
                if isinstance(raw_data.columns, pd.MultiIndex):
                    df_t = raw_data[ticker]['Close'].dropna()
                else:
                    df_t = raw_data['Close'].dropna() # Fallback

                if len(df_t) < 200: continue
                
                curr = df_t.iloc[-1]
                
                # Z-Score (250日/1年均值回归)
                ma250 = df_t.rolling(250).mean().iloc[-1]
                std250 = df_t.rolling(250).std().iloc[-1]
                z_score = (curr - ma250) / std250 if std250 != 0 else 0
                
                # Momentum (20日短期趋势)
                mom20 = (curr / df_t.iloc[-21] - 1) * 100
                
                # RSI (相对强弱) - 用于气泡大小
                delta = df_t.diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs)).iloc[-1]
                
                metrics.append({
                    "代码": ticker, 
                    "名称": name, 
                    "组别": group_name,
                    "Z-Score": round(z_score, 2), 
                    "Momentum": round(mom20, 2),
                    "RSI": round(rsi, 0)
                })
            except: continue
    return pd.DataFrame(metrics)

# --- 4. 绘图与展示 ---
if not raw_data.empty:
    df_metrics = calculate_metrics()
    
    if not df_metrics.empty:
        # 侧边栏筛选
        st.sidebar.header("🔍 筛选器")
        selected_groups = st.sidebar.multiselect("选择资产类别", list(ASSET_GROUPS.keys()), default=list(ASSET_GROUPS.keys()))
        
        df_plot = df_metrics[df_metrics['组别'].isin(selected_groups)]
        
        # 核心散点图
        fig = px.scatter(
            df_plot, 
            x="Z-Score", 
            y="Momentum", 
            color="组别", 
            text="名称",
            hover_data=["代码", "RSI"],
            size="RSI", # 气泡大小由 RSI 决定 (越强越大)
            size_max=40,
            color_discrete_map={
                "A: 全球国别 (Global)": "#3498DB", # 蓝
                "B: 大宗与货币 (Commodities & FX)": "#F1C40F", # 黄
                "C: 核心板块 (US Sectors)": "#E74C3C", # 红
                "D: 风格与赛道 (Themes)": "#9B59B6"  # 紫
            }
        )
        
        # 辅助线和象限标注
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.3)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.3)
        
        # 动态标注 (根据数据范围调整位置)
        max_y = df_plot['Momentum'].max()
        min_y = df_plot['Momentum'].min()
        max_x = df_plot['Z-Score'].max()
        min_x = df_plot['Z-Score'].min()
        
        fig.add_annotation(x=max_x, y=max_y, text="🔥 强势拥挤", showarrow=False, font=dict(color="#E74C3C"))
        fig.add_annotation(x=min_x, y=min_y, text="❄️ 弱势超跌", showarrow=False, font=dict(color="#3498DB"))
        fig.add_annotation(x=min_x, y=max_y, text="🚀 底部启动", showarrow=False, font=dict(color="#2ECC71"))
        fig.add_annotation(x=max_x, y=min_y, text="⚠️ 顶部回落", showarrow=False, font=dict(color="#E67E22"))
        
        fig.update_traces(textposition='top center', marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        fig.update_layout(
            height=700,
            xaxis_title="<-- 便宜 (低 Z-Score) | 昂贵 (高 Z-Score) -->",
            yaxis_title="<-- 资金流出 | 资金流入 (20日动量) -->",
            legend=dict(orientation="h", y=1.05, title=None),
            plot_bgcolor="#161616",
            font=dict(size=14)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 下方详细数据表
        st.markdown("### 📊 资产透视表")
        
        # 样式美化
        st.dataframe(
            df_plot.sort_values("Momentum", ascending=False), 
            use_container_width=True,
            column_config={
                "代码": st.column_config.TextColumn("Ticker"),
                "名称": st.column_config.TextColumn("Asset Name"),
                "Momentum": st.column_config.NumberColumn("20日动量 %", format="%.2f%%"),
                "Z-Score": st.column_config.ProgressColumn("估值位置 (Z-Score)", min_value=-3, max_value=3, format="%.2f"),
                "RSI": st.column_config.NumberColumn("RSI强度", format="%.0f")
            },
            hide_index=True
        )

else:
    st.info("⏳ 正在拉取全球50+核心资产数据，请稍候...")
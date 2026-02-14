import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="宏观全景雷达", layout="wide", page_icon="🔭")

st.title("🔭 宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场扫描：**Z-Score (估值)** vs **Momentum (动量)** | 颜色代表趋势强弱：🟥弱 -> 🟨平 -> 🟩强")

# --- 1. 定义超全资产池 (The Ultimate Pool) ---
ASSET_GROUPS = {
    "A: 全球国别": {
        "SPY": "🇺🇸 美股", "QQQ": "🇺🇸 纳指", "IWM": "🇺🇸 罗素", 
        "EEM": "🌏 新兴", "VGK": "🇪🇺 欧洲", "EWJ": "🇯🇵 日本", 
        "MCHI": "🇨🇳 中国", "KWEB": "🇨🇳 中概", 
        "INDA": "🇮🇳 印度", "VNM": "🇻🇳 越南", "EWZ": "🇧🇷 巴西"
    },
    "B: 大宗/货币": {
        "TLT": "🇺🇸 美债", "UUP": "💵 美元", 
        "FXY": "💴 日元", "CYB": "🇨🇳 人民币",
        "GLD": "🥇 黄金", "SLV": "🥈 白银", 
        "USO": "🛢️ 原油", "UNG": "🔥 天然气", 
        "CPER": "🥉 铜", "DBA": "🌽 农业", 
        "BTC-USD": "₿ BTC"
    },
    "C: 核心板块": {
        "XLK": "💻 科技", "XLF": "🏦 金融", "XLV": "💊 医疗", 
        "XLE": "⚡ 能源", "XLI": "🏗️ 工业", "XLP": "🛒 必选", 
        "XLY": "🛍️ 可选", "XLB": "🧱 材料", "XLU": "💡 公用", 
        "XLRE": "🏠 地产", "XLC": "📡 通讯"
    },
    "D: 风格赛道": {
        "MAGS": "👑 七姐妹", "SMH": "💾 半导体", 
        "IGV": "☁️ 软件", "XBI": "🧬 生科", 
        "ITA": "✈️ 军工", "URA": "☢️ 铀矿", 
        "PAVE": "🛣️ 基建", "MTUM": "🚀 动量", 
        "USMV": "🛡️ 低波"
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
                if isinstance(raw_data.columns, pd.MultiIndex):
                    df_t = raw_data[ticker]['Close'].dropna()
                else:
                    df_t = raw_data['Close'].dropna()

                if len(df_t) < 200: continue
                
                curr = df_t.iloc[-1]
                
                # Z-Score (1年)
                ma250 = df_t.rolling(250).mean().iloc[-1]
                std250 = df_t.rolling(250).std().iloc[-1]
                z_score = (curr - ma250) / std250 if std250 != 0 else 0
                
                # Momentum (20日)
                mom20 = (curr / df_t.iloc[-21] - 1) * 100
                
                metrics.append({
                    "代码": ticker, 
                    "名称": name, 
                    "组别": group_name,
                    "Z-Score": round(z_score, 2), 
                    "Momentum": round(mom20, 2)
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
        
        # --- UI 升级核心代码 ---
        fig = px.scatter(
            df_plot, 
            x="Z-Score", 
            y="Momentum", 
            # 1. 颜色映射到 Momentum (动量)，实现“红橙黄绿”热力效果
            color="Momentum", 
            text="名称",
            hover_data=["代码", "组别"],
            # 2. 颜色配置：RdYlGn (红-黄-绿)。
            # 如果想要 A股风格 (绿跌红涨)，把下面的 "RdYlGn" 改为 "RdYlGn_r" (_r表示反转)
            color_continuous_scale="RdYlGn", 
            # 3. 锁定颜色范围，防止极值破坏观感 (例如 -15% 到 +15%)
            range_color=[-15, 15] 
        )
        
        # 4. 辅助线 (极简灰色虚线)
        fig.add_hline(y=0, line_dash="dash", line_color="#444", opacity=0.5, layer="below")
        fig.add_vline(x=0, line_dash="dash", line_color="#444", opacity=0.5, layer="below")
        
        # 5. 极简小圆点风格
        fig.update_traces(
            textposition='top center', 
            marker=dict(
                size=10,         # 统一小尺寸
                line=dict(width=0), # 去掉边框！
                opacity=0.9      # 略微透明增加质感
            )
        )
        
        # 6. 背景与布局优化 (Bloomberg 风格)
        fig.update_layout(
            height=750,
            xaxis_title="<-- 便宜 (低 Z-Score) | 昂贵 (高 Z-Score) -->",
            yaxis_title="<-- 弱势 (流出) | 强势 (流入) -->",
            plot_bgcolor="#111111", # 深色背景
            paper_bgcolor="#111111",
            font=dict(color="#ddd", size=13),
            xaxis=dict(showgrid=True, gridcolor="#333"), # 弱化网格
            yaxis=dict(showgrid=True, gridcolor="#333"),
            coloraxis_colorbar=dict(title="20日动量%") # 色卡标题
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部数据表
        st.markdown("### 📊 资产透视表")
        st.dataframe(
            df_plot.sort_values("Momentum", ascending=False), 
            use_container_width=True,
            column_config={
                "Momentum": st.column_config.NumberColumn("20日动量 %", format="%.2f%%"),
                "Z-Score": st.column_config.ProgressColumn("估值位置", min_value=-3, max_value=3, format="%.2f")
            },
            hide_index=True
        )

else:
    st.info("⏳ 正在拉取全球核心资产数据，请稍候...")
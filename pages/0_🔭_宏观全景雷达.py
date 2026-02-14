import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="宏观全景雷达", layout="wide", page_icon="🔭")

st.title("🔭 宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场资产扫描：**Z-Score (估值)** vs **Momentum (动量)** | 不同颜色代表不同资产类别")

# --- 1. 定义三大资产池 (The Big Pool) ---
ASSET_GROUPS = {
    "A: 全球宏观": {
        "SPY": "美股", "QQQ": "纳指", "IWM": "罗素", "TLT": "20年美债", 
        "GLD": "黄金", "USO": "原油", "UUP": "美元", "BTC-USD": "比特币",
        "EEM": "新兴市场", "VGK": "欧洲", "EWJ": "日本"
    },
    "B: 美股板块": {
        "XLK": "科技", "XLF": "金融", "XLV": "医疗", "XLY": "可选", 
        "XLP": "必选", "XLE": "能源", "XLI": "工业", "XLB": "材料", 
        "XLU": "公用", "XLRE": "地产", "XLC": "通讯"
    },
    "C: 风格赛道": {
        "SMH": "半导体", "IGV": "软件", "XBI": "生科", "ITA": "军工",
        "KWEB": "中概互联", "ARKK": "创新", "MTUM": "动量", "USMV": "低波",
        "COIN": "Coinbase", "NVDA": "英伟达" 
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
                df_t = raw_data[ticker]['Close'].dropna()
                if len(df_t) < 250: continue
                
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
                    "组别": group_name, # 用于区分颜色
                    "Z-Score": round(z_score, 2), 
                    "Momentum": round(mom20, 2)
                })
            except: continue
    return pd.DataFrame(metrics)

# --- 4. 绘图与展示 ---
if not raw_data.empty:
    df_metrics = calculate_metrics()
    
    if not df_metrics.empty:
        # 核心散点图
        fig = px.scatter(
            df_metrics, 
            x="Z-Score", 
            y="Momentum", 
            color="组别", # 关键：不同组别不同颜色
            text="名称",
            hover_data=["代码", "组别"],
            size_max=60,
            # 自定义颜色映射
            color_discrete_map={
                "A: 全球宏观": "#3498DB", # 蓝
                "B: 美股板块": "#E74C3C", # 红
                "C: 风格赛道": "#2ECC71"  # 绿
            }
        )
        
        # 辅助线和标注
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_annotation(x=2.5, y=15, text="🔥 强势拥挤", showarrow=False, font=dict(color="red", size=12))
        fig.add_annotation(x=-2.5, y=-15, text="❄️ 弱势超跌", showarrow=False, font=dict(color="blue", size=12))
        
        fig.update_traces(textposition='top center', marker=dict(size=12, line=dict(width=1, color='DarkSlateGrey')))
        fig.update_layout(
            height=650, # 大屏展示
            xaxis_title="<-- 便宜 (低 Z-Score) | 昂贵 (高 Z-Score) -->",
            yaxis_title="<-- 资金流出 | 资金流入 (20日动量) -->",
            legend=dict(orientation="h", y=1.1, title=None), # 图例横排放在顶部
            plot_bgcolor="#161616"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 下方数据表 (可按组别筛选)
        st.markdown("### 📊 详细数据监控")
        filter_group = st.multiselect("筛选组别：", list(ASSET_GROUPS.keys()), default=list(ASSET_GROUPS.keys()))
        
        df_show = df_metrics[df_metrics['组别'].isin(filter_group)]
        st.dataframe(
            df_show.sort_values("Momentum", ascending=False), 
            use_container_width=True,
            column_config={
                "Momentum": st.column_config.NumberColumn("20日动量 %", format="%.2f%%"),
                "Z-Score": st.column_config.ProgressColumn("估值位置 (Z-Score)", min_value=-3, max_value=3, format="%.2f")
            }
        )

else:
    st.info("⏳ 正在初始化全景数据...")
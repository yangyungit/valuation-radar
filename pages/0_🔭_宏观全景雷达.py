import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 页面配置
st.set_page_config(page_title="宏观全景雷达", layout="wide")

st.title("宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场扫描：Z-Score (估值) vs Momentum (动量) | 颜色代表趋势强弱：红(弱) -> 黄(平) -> 绿(强)")

# --- 1. 定义资产池 ---
ASSET_GROUPS = {
    "A: 全球国别": {
        "SPY": "美股大盘", "QQQ": "纳指100", "IWM": "罗素小盘", 
        "EEM": "新兴市场", "VGK": "欧洲股市", "EWJ": "日本股市", 
        "MCHI": "中国大盘", "KWEB": "中概互联", 
        "INDA": "印度股市", "VNM": "越南股市", "EWZ": "巴西股市"
    },
    "B: 大宗/货币": {
        "TLT": "20年美债", "UUP": "美元指数", 
        "FXY": "日元汇率", "CYB": "人民币",
        "GLD": "黄金", "SLV": "白银", 
        "USO": "原油", "UNG": "天然气", 
        "CPER": "铜", "DBA": "农产品", 
        "BTC-USD": "比特币"
    },
    "C: 核心板块": {
        "XLK": "科技", "XLF": "金融", "XLV": "医疗", 
        "XLE": "能源", "XLI": "工业", "XLP": "必选消费", 
        "XLY": "可选消费", "XLB": "材料", "XLU": "公用事业", 
        "XLRE": "地产", "XLC": "通讯"
    },
    "D: 风格赛道": {
        "MAGS": "七姐妹", "SMH": "半导体", 
        "IGV": "软件SaaS", "XBI": "生物科技", 
        "ITA": "军工国防", "URA": "铀矿核能", 
        "PAVE": "基建工程", "MTUM": "动量因子", 
        "USMV": "低波防御"
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
        st.sidebar.header("筛选器")
        selected_groups = st.sidebar.multiselect("选择资产类别", list(ASSET_GROUPS.keys()), default=list(ASSET_GROUPS.keys()))
        df_plot = df_metrics[df_metrics['组别'].isin(selected_groups)]
        
        # --- 核心绘图 ---
        fig = px.scatter(
            df_plot, 
            x="Z-Score", 
            y="Momentum", 
            color="Momentum", 
            text="名称",
            hover_data=["代码", "组别"],
            color_continuous_scale="RdYlGn", 
            range_color=[-15, 15] 
        )
        
        # === 修复：增强十字辅助线可见度 ===
        # 使用白色 (#FFFFFF) 配合 0.4 的透明度，确保在深色背景下清晰可见
        fig.add_hline(y=0, line_dash="dash", line_color="#FFFFFF", opacity=0.4, line_width=1)
        fig.add_vline(x=0, line_dash="dash", line_color="#FFFFFF", opacity=0.4, line_width=1)
        
        # 极简小圆点风格
        fig.update_traces(
            textposition='top center', 
            marker=dict(
                size=8, 
                line=dict(width=0), 
                opacity=0.9
            )
        )
        
        # 象限标注
        max_y = df_plot['Momentum'].max()
        min_y = df_plot['Momentum'].min()
        max_x = df_plot['Z-Score'].max()
        min_x = df_plot['Z-Score'].min()

        fig.add_annotation(x=max_x, y=max_y, text="强势/拥挤", showarrow=False, font=dict(color="#E74C3C", size=12))
        fig.add_annotation(x=min_x, y=min_y, text="弱势/超跌", showarrow=False, font=dict(color="#3498DB", size=12))
        
        # 布局优化
        fig.update_layout(
            height=750,
            xaxis_title="便宜 (低 Z-Score)  <───>  昂贵 (高 Z-Score)",
            yaxis_title="资金流出 (弱势)  <───>  资金流入 (强势)",
            plot_bgcolor="#111111", 
            paper_bgcolor="#111111",
            font=dict(color="#ddd", size=12),
            # 网格线稍微调暗一点，不要抢了十字线的风头
            xaxis=dict(showgrid=True, gridcolor="#222"), 
            yaxis=dict(showgrid=True, gridcolor="#222"),
            coloraxis_colorbar=dict(title="20日动量%")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部数据表
        st.markdown("### 资产数据明细")
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
    st.info("正在初始化数据，请稍候...")
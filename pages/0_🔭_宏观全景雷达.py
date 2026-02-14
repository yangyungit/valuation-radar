import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 页面配置：移除 page_icon
st.set_page_config(page_title="宏观全景雷达", layout="wide")

st.title("宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场扫描：Z-Score (估值) vs Momentum (动量) | 颜色代表趋势强弱：红(弱) -> 黄(平) -> 绿(强)")

# --- 1. 定义终极资产池 (纯文字版) ---
ASSET_GROUPS = {
    "A: 全球国别 (Global)": {
        "SPY": "美股", "QQQ": "纳指", "IWM": "罗素小盘", 
        "EEM": "新兴市场", "VGK": "欧洲", "EWJ": "日本", 
        "MCHI": "中国大盘", "KWEB": "中概互联", 
        "INDA": "印度", "VNM": "越南", "EWZ": "巴西",
        "ARGT": "阿根廷", "EWY": "韩国"
    },
    "B: 大宗/货币 (Macro)": {
        "UUP": "美元", "FXY": "日元", "CYB": "人民币",
        "GLD": "黄金", "SLV": "白银", "GDX": "金矿",
        "USO": "原油", "UNG": "天然气", 
        "CPER": "铜", "DBA": "农产品", 
        "BTC-USD": "BTC"
    },
    "C: 核心板块 (Sectors)": {
        "XLK": "科技", "XLF": "金融", "XLV": "医疗", 
        "XLE": "能源", "XLI": "工业", "XLP": "必选", 
        "XLY": "可选", "XLB": "材料", "XLU": "公用", 
        "XLRE": "地产", "XLC": "通讯",
        "XHB": "房屋建筑", "JETS": "航空"
    },
    "D: 细分赛道 (Themes)": {
        "SMH": "半导体", "IGV": "软件", "CIBR": "网络安全",
        "SKYY": "云计算", "XBI": "生科", "ITA": "军工",
        "TAN": "太阳能", "URA": "铀矿", "PAVE": "基建",
        "BOTZ": "机器人", "QTUM": "量子", "METV": "元宇宙",
        "AIQ": "人工智能"
    },
    "E: 固收阶梯 (Fixed Income)": {
        "SHY": "1-3年美债", "IEF": "7-10年美债", "TLT": "20年美债",
        "LQD": "投资级债", "HYG": "垃圾债", "EMB": "新兴债",
        "MUB": "市政债", "TIP": "抗通胀债"
    },
    "F: 聪明钱因子 (Factors)": {
        "MTUM": "动量", "USMV": "低波", "VLUE": "价值",
        "QUAL": "质量", "IWF": "成长", "RSP": "等权"
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
                
                # Z-Score (1年均值回归)
                ma250 = df_t.rolling(250).mean().iloc[-1]
                std250 = df_t.rolling(250).std().iloc[-1]
                z_score = (curr - ma250) / std250 if std250 != 0 else 0
                
                # Momentum (20日短期趋势)
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
        # --- 侧边栏筛选器 ---
        with st.sidebar:
            st.header("资产筛选")
            st.info("通过勾选下方类别，控制雷达图中显示的资产范围。")
            
            all_groups = list(ASSET_GROUPS.keys())
            selected_groups = st.multiselect(
                "显示资产组别：", 
                all_groups, 
                default=all_groups
            )
            
            st.markdown("---")
            st.markdown("**图例说明：**")
            st.markdown("绿色：强势流入 (Momentum > 0)")
            st.markdown("红色：弱势流出 (Momentum < 0)")
            st.markdown("横轴：估值 (左便宜，右贵)")
            st.markdown("纵轴：趋势 (上强，下弱)")

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
            range_color=[-10, 10]
        )
        
        # 辅助线 (极简白色虚线)
        fig.add_hline(y=0, line_dash="dash", line_color="#FFFFFF", opacity=0.3, line_width=1)
        fig.add_vline(x=0, line_dash="dash", line_color="#FFFFFF", opacity=0.3, line_width=1)
        
        # 极简小圆点风格
        fig.update_traces(
            textposition='top center', 
            marker=dict(
                size=8, 
                line=dict(width=0), 
                opacity=0.9
            )
        )
        
        # 象限标注 (纯文字)
        max_y = max(df_plot['Momentum'].max(), 5)
        min_y = min(df_plot['Momentum'].min(), -5)
        max_x = max(df_plot['Z-Score'].max(), 2)
        min_x = min(df_plot['Z-Score'].min(), -2)

        fig.add_annotation(x=max_x, y=max_y, text="强势拥挤", showarrow=False, font=dict(color="#E74C3C", size=12))
        fig.add_annotation(x=min_x, y=min_y, text="弱势超跌", showarrow=False, font=dict(color="#3498DB", size=12))
        
        # 布局优化
        fig.update_layout(
            height=750,
            xaxis_title="便宜 (低 Z-Score)  <───>  昂贵 (高 Z-Score)",
            yaxis_title="资金流出 (弱势)  <───>  资金流入 (强势)",
            plot_bgcolor="#111111", 
            paper_bgcolor="#111111",
            font=dict(color="#ddd", size=12),
            xaxis=dict(showgrid=True, gridcolor="#222"), 
            yaxis=dict(showgrid=True, gridcolor="#222"),
            coloraxis_colorbar=dict(title="20日动量%")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部数据表
        st.markdown("### 资产深度透视")
        
        view_mode = st.radio("展示方式", ["全部汇总", "按组别分表"], horizontal=True)
        
        if view_mode == "全部汇总":
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
            for group in selected_groups:
                st.subheader(group)
                df_group = df_plot[df_plot['组别'] == group]
                st.dataframe(
                    df_group.sort_values("Momentum", ascending=False),
                    use_container_width=True,
                    column_config={
                        "Momentum": st.column_config.NumberColumn("动量 %", format="%.2f%%"),
                        "Z-Score": st.column_config.ProgressColumn("Z-Score", min_value=-3, max_value=3, format="%.2f")
                    },
                    hide_index=True
                )

else:
    st.info("正在拉取 70+ 全球核心资产数据，请稍候...")
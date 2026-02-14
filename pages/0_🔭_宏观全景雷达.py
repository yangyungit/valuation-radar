import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 页面配置
st.set_page_config(page_title="宏观全景雷达", layout="wide")

st.title("宏观全景雷达 (Macro Panoramic Radar)")
st.caption("全市场扫描：Z-Score (估值) vs Relative Strength (相对强度) | 基准：SPY (美股大盘)")

# --- 1. 定义终极资产池 ---
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
    start_date = end_date - timedelta(days=730) 
    
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data
    except: return pd.DataFrame()

raw_data = get_data()

# --- 3. 计算逻辑 (引入相对强度 REL) ---
def calculate_metrics():
    metrics = []
    
    # 0. 先计算基准 (SPY) 的动量
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            spy_df = raw_data['SPY']['Close'].dropna()
        else:
            spy_df = raw_data['Close'].dropna() # Fallback case
            
        spy_curr = spy_df.iloc[-1]
        spy_prev_20 = spy_df.iloc[-21]
        # 基准动量
        spy_mom20 = (spy_curr / spy_prev_20 - 1) * 100
    except:
        spy_mom20 = 0 # 如果获取不到SPY，则退化为绝对动量
    
    for group_name, tickers in ASSET_GROUPS.items():
        for ticker, name in tickers.items():
            try:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if ticker not in raw_data.columns.levels[0]: continue
                    df_t = raw_data[ticker]['Close'].dropna()
                else:
                    df_t = raw_data['Close'].dropna()

                if len(df_t) < 180: continue
                
                curr = df_t.iloc[-1]
                
                # Z-Score (1年均值回归)
                ma250 = df_t.rolling(250, min_periods=200).mean().iloc[-1]
                std250 = df_t.rolling(250, min_periods=200).std().iloc[-1]
                
                if pd.isna(ma250) or pd.isna(std250) or std250 == 0:
                    z_score = 0
                else:
                    z_score = (curr - ma250) / std250
                
                # Momentum (20日)
                abs_mom20 = (curr / df_t.iloc[-21] - 1) * 100
                
                # === 核心修改：计算相对强度 (REL) ===
                # REL = 个股涨幅 - SPY涨幅
                rel_mom20 = abs_mom20 - spy_mom20
                
                metrics.append({
                    "代码": ticker, 
                    "名称": name, 
                    "组别": group_name,
                    "Z-Score": round(z_score, 2), 
                    "相对强度": round(rel_mom20, 2), # Y轴数据
                    "绝对涨幅": round(abs_mom20, 2)   # 用于悬停显示
                })
            except: continue
            
    return pd.DataFrame(metrics), spy_mom20

# --- 4. 绘图与展示 ---
if not raw_data.empty:
    df_metrics, benchmark_mom = calculate_metrics()
    
    if not df_metrics.empty:
        # --- 侧边栏 ---
        with st.sidebar:
            st.header("资产筛选")
            
            # 显示当前基准状态
            st.metric("基准 (SPY) 20日涨跌幅", f"{benchmark_mom:.2f}%")
            if benchmark_mom < -2:
                st.error("大盘弱势，寻找抗跌资产 (Y > 0)")
            elif benchmark_mom > 2:
                st.success("大盘强势，寻找领涨龙头 (Y > 0)")
            
            all_groups = list(ASSET_GROUPS.keys())
            default_selection = ["E: 固收阶梯 (Fixed Income)", "F: 聪明钱因子 (Factors)", "A: 全球国别 (Global)", "B: 大宗/货币 (Macro)"]
            default_selection = [g for g in default_selection if g in all_groups]
            
            selected_groups = st.multiselect("显示资产组别：", all_groups, default=all_groups)
            
            st.markdown("---")
            st.markdown("**图例说明 (相对强度版)：**")
            st.markdown("绿色 (Y > 0)：**跑赢** 美股大盘")
            st.markdown("红色 (Y < 0)：**跑输** 美股大盘")
            st.markdown("中心虚线：与大盘持平")

        df_plot = df_metrics[df_metrics['组别'].isin(selected_groups)]
        
        # --- 核心绘图 ---
        fig = px.scatter(
            df_plot, 
            x="Z-Score", 
            y="相对强度",  # Y轴改为相对强度
            color="相对强度", # 颜色也由相对强度决定
            text="名称",
            hover_data=["代码", "绝对涨幅", "组别"],
            color_continuous_scale="RdYlGn", 
            range_color=[-10, 10]
        )
        
        # 辅助线
        fig.add_hline(y=0, line_dash="dash", line_color="#FFFFFF", opacity=0.5, line_width=1)
        fig.add_vline(x=0, line_dash="dash", line_color="#FFFFFF", opacity=0.3, line_width=1)
        
        # 极简小圆点
        fig.update_traces(
            textposition='top center', 
            marker=dict(
                size=8, 
                line=dict(width=0), 
                opacity=0.9
            )
        )
        
        # 象限标注 (根据相对强度逻辑修改)
        if not df_plot.empty:
            max_y = max(df_plot['相对强度'].max(), 5)
            min_y = min(df_plot['相对强度'].min(), -5)
            max_x = max(df_plot['Z-Score'].max(), 2)
            min_x = min(df_plot['Z-Score'].min(), -2)

            fig.add_annotation(x=max_x, y=max_y, text="领涨/拥挤 (跑赢SPY)", showarrow=False, font=dict(color="#E74C3C", size=12))
            fig.add_annotation(x=min_x, y=min_y, text="滞涨/弱势 (跑输SPY)", showarrow=False, font=dict(color="#3498DB", size=12))
            fig.add_annotation(x=min_x, y=max_y, text="抗跌/启动 (跑赢SPY)", showarrow=False, font=dict(color="#2ECC71", size=12))
            fig.add_annotation(x=max_x, y=min_y, text="补跌/崩盘 (跑输SPY)", showarrow=False, font=dict(color="#E67E22", size=12))
        
        # 布局优化
        fig.update_layout(
            height=800,
            title=dict(text=f"相对强度雷达 (基准: SPY {benchmark_mom:.2f}%)", x=0.5),
            xaxis_title="便宜 (低 Z-Score)  <───>  昂贵 (高 Z-Score)",
            yaxis_title="跑输大盘 (弱)  <───>  跑赢大盘 (强)",
            plot_bgcolor="#111111", 
            paper_bgcolor="#111111",
            font=dict(color="#ddd", size=12),
            xaxis=dict(showgrid=True, gridcolor="#222"), 
            yaxis=dict(showgrid=True, gridcolor="#222"),
            coloraxis_colorbar=dict(title="相对强度%")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部数据表
        st.markdown("### 资产深度透视 (Relative Strength)")
        
        view_mode = st.radio("展示方式", ["全部汇总", "按组别分表"], horizontal=True)
        
        # 定义列配置
        col_config = {
            "相对强度": st.column_config.NumberColumn("相对强度 (vs SPY)", format="%.2f%%"),
            "绝对涨幅": st.column_config.NumberColumn("绝对涨幅", format="%.2f%%"),
            "Z-Score": st.column_config.ProgressColumn("Z-Score", min_value=-3, max_value=3, format="%.2f")
        }

        if view_mode == "全部汇总":
            st.dataframe(
                df_plot.sort_values("相对强度", ascending=False), 
                use_container_width=True,
                column_config=col_config,
                hide_index=True
            )
        else:
            sorted_groups = sorted(selected_groups, key=lambda x: x[0])
            for group in sorted_groups:
                st.subheader(group)
                df_group = df_plot[df_plot['组别'] == group]
                st.dataframe(
                    df_group.sort_values("相对强度", ascending=False),
                    use_container_width=True,
                    column_config=col_config,
                    hide_index=True
                )
    else:
        st.warning("⚠️ 没有有效数据。请检查网络或数据源。")

else:
    st.info("⏳ 正在拉取 70+ 全球核心资产数据 (730天历史)，请稍候...")
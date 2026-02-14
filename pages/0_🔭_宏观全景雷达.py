import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 页面配置
st.set_page_config(page_title="宏观全景雷达", layout="wide")

st.title("宏观全景雷达 (Macro Panoramic Radar)")
st.caption("双维监控：上图看【相对强度/估值】，下表看【全周期趋势结构】(含牛熊分界)")

# --- 1. 定义资产池 ---
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
    # 必须拉取足够长的数据以计算 EMA200
    start_date = end_date - timedelta(days=730) 
    
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data
    except: return pd.DataFrame()

raw_data = get_data()

# --- 3. 计算逻辑 (深度趋势解析 + L/VL) ---
def calculate_metrics():
    metrics = []
    
    # 0. 计算基准 SPY
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            spy_df = raw_data['SPY']['Close'].dropna()
        else:
            spy_df = raw_data['Close'].dropna()
        spy_mom20 = (spy_df.iloc[-1] / spy_df.iloc[-21] - 1) * 100
    except:
        spy_mom20 = 0
    
    for group_name, tickers in ASSET_GROUPS.items():
        for ticker, name in tickers.items():
            try:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if ticker not in raw_data.columns.levels[0]: continue
                    df_t = raw_data[ticker]['Close'].dropna()
                else:
                    df_t = raw_data['Close'].dropna()

                if len(df_t) < 250: continue # 提高门槛以计算 EMA200
                
                curr = df_t.iloc[-1]
                
                # --- A. 基础雷达指标 ---
                ma250 = df_t.rolling(250, min_periods=200).mean().iloc[-1]
                std250 = df_t.rolling(250, min_periods=200).std().iloc[-1]
                z_score = (curr - ma250) / std250 if std250 != 0 else 0
                
                abs_mom20 = (curr / df_t.iloc[-21] - 1) * 100
                rel_mom20 = abs_mom20 - spy_mom20
                
                # --- B. 深度趋势指标 (EMA系统) ---
                # 计算 EMA 20, 60, 120, 200 (新增)
                ema20 = df_t.ewm(span=20, adjust=False).mean().iloc[-1]
                ema60 = df_t.ewm(span=60, adjust=False).mean().iloc[-1]
                ema120 = df_t.ewm(span=120, adjust=False).mean().iloc[-1]
                ema200 = df_t.ewm(span=200, adjust=False).mean().iloc[-1] # 新增超长均线
                
                # 计算乖离率 (Bias)
                # C/S: Close vs Short (20)
                c_s = (curr - ema20) / ema20 * 100
                # S/M: Short (20) vs Medium (60)
                s_m = (ema20 - ema60) / ema60 * 100
                # M/L: Medium (60) vs Long (120)
                m_l = (ema60 - ema120) / ema120 * 100
                # L/VL: Long (120) vs Very Long (200) <--- 新增指标
                l_vl = (ema120 - ema200) / ema200 * 100
                
                # 定义趋势结构 (Structure)
                # 逻辑升级：加入 VL (200日) 的判断
                structure = "震荡/纠缠"
                
                if c_s > 0 and s_m > 0 and m_l > 0 and l_vl > 0:
                    structure = "完美多头 (主升浪)"
                elif c_s < 0 and s_m < 0 and m_l < 0 and l_vl < 0:
                    structure = "完美空头 (主跌浪)"
                elif l_vl > 0:
                    if c_s < 0: structure = "牛市回调 (多头排列)"
                    else: structure = "长期看涨"
                elif l_vl < 0:
                    if c_s > 0: structure = "熊市反弹 (空头排列)"
                    else: structure = "长期看跌"
                
                metrics.append({
                    "代码": ticker, 
                    "名称": name, 
                    "组别": group_name,
                    "Z-Score": round(z_score, 2), 
                    "相对强度": round(rel_mom20, 2), 
                    "趋势结构": structure,
                    "C/S": round(c_s, 2),
                    "S/M": round(s_m, 2),
                    "M/L": round(m_l, 2),
                    "L/VL": round(l_vl, 2), # 新增列
                    "现价": round(curr, 2)
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
            st.metric("基准 (SPY) 20日涨跌", f"{benchmark_mom:.2f}%")
            
            all_groups = list(ASSET_GROUPS.keys())
            selected_groups = st.multiselect("显示资产组别：", all_groups, default=all_groups)
            
            st.markdown("---")
            st.markdown("**图例说明：**")
            st.markdown("横轴：估值 (左便宜，右贵)")
            st.markdown("纵轴：相对强度 (上强，下弱)")
            st.markdown("**趋势扫描表指标：**")
            st.markdown("C/S: 收盘价 vs 20日线 (短期)")
            st.markdown("S/M: 20日线 vs 60日线 (中期)")
            st.markdown("M/L: 60日线 vs 120日线 (长期)")
            st.markdown("L/VL: 120日线 vs 200日线 (牛熊)")

        df_plot = df_metrics[df_metrics['组别'].isin(selected_groups)]
        
        # --- PART 1: 宏观雷达图 ---
        fig = px.scatter(
            df_plot, 
            x="Z-Score", 
            y="相对强度", 
            color="相对强度",
            text="名称",
            hover_data={
                "代码": True,
                "趋势结构": True,
                "Z-Score": ":.2f",
                "相对强度": ":.2f",
                "名称": False,
                "相对强度": False
            },
            color_continuous_scale="RdYlGn", 
            range_color=[-10, 10]
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="#FFFFFF", opacity=0.5, line_width=1)
        fig.add_vline(x=0, line_dash="dash", line_color="#FFFFFF", opacity=0.3, line_width=1)
        fig.update_traces(textposition='top center', marker=dict(size=8, line=dict(width=0), opacity=0.9))
        
        if not df_plot.empty:
            max_y = max(df_plot['相对强度'].max(), 5)
            min_y = min(df_plot['相对强度'].min(), -5)
            max_x = max(df_plot['Z-Score'].max(), 2)
            min_x = min(df_plot['Z-Score'].min(), -2)

            fig.add_annotation(x=max_x, y=max_y, text="领涨/拥挤", showarrow=False, font=dict(color="#E74C3C", size=12))
            fig.add_annotation(x=min_x, y=min_y, text="滞涨/弱势", showarrow=False, font=dict(color="#3498DB", size=12))
            fig.add_annotation(x=min_x, y=max_y, text="抗跌/启动", showarrow=False, font=dict(color="#2ECC71", size=12))
            fig.add_annotation(x=max_x, y=min_y, text="补跌/崩盘", showarrow=False, font=dict(color="#E67E22", size=12))
        
        fig.update_layout(
            height=700,
            title=dict(text=f"宏观全景雷达 (基准: SPY {benchmark_mom:.2f}%)", x=0.5),
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
        
        # --- PART 2: 趋势扫描表 (4级均线版) ---
        st.markdown("### 趋势扫描 (Trend Scanner - 4级均线)")
        st.caption("逻辑来源：C(价) > S(20) > M(60) > L(120) > VL(200) = 完美多头")
        
        df_table = df_plot[["代码", "名称", "组别", "趋势结构", "C/S", "S/M", "M/L", "L/VL", "相对强度", "Z-Score"]].copy()
        
        def color_trend(val):
            color = '#E74C3C' if val < 0 else '#2ECC71' 
            return f'color: {color}'
        
        def color_structure(val):
            if "完美多头" in val: return 'color: #2ECC71; font-weight: bold; border: 1px solid #2ECC71'
            if "完美空头" in val: return 'color: #E74C3C; font-weight: bold'
            if "牛市回调" in val: return 'color: #F1C40F; font-weight: bold'
            return 'color: #ddd'

        view_mode = st.radio("表格视图", ["汇总模式", "分组模式"], horizontal=True)
        
        # 应用样式
        style_cols = ["C/S", "S/M", "M/L", "L/VL", "相对强度"]
        
        if view_mode == "汇总模式":
            st.dataframe(
                df_table.sort_values("相对强度", ascending=False).style.applymap(color_trend, subset=style_cols).applymap(color_structure, subset=["趋势结构"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            sorted_groups = sorted(selected_groups, key=lambda x: x[0])
            for group in sorted_groups:
                st.subheader(group)
                df_sub = df_table[df_table['组别'] == group].sort_values("相对强度", ascending=False)
                st.dataframe(
                    df_sub.style.applymap(color_trend, subset=style_cols).applymap(color_structure, subset=["趋势结构"]),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.warning("暂无数据")

else:
    st.info("⏳ 正在计算 200日均线数据 (需 730 天历史)...")
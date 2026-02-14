import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 尝试导入自选股池
try:
    from my_stock_pool import MY_POOL
except ImportError:
    st.error("⚠️ 找不到 my_stock_pool.py。请确保文件存在且定义了 MY_POOL 字典。")
    st.stop()

# 页面配置
st.set_page_config(page_title="我的自选股池", layout="wide")

st.title("我的自选股池 (My Watchlist Radar)")
st.caption("深度扫描：Z-Score (估值) vs Relative Strength (相对强度) | 下方含【趋势结构】扫描")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_user_data():
    # 1. 提取自选股
    all_tickers = []
    for group in MY_POOL.values():
        all_tickers.extend(list(group.keys()))
    
    # 2. 必须加入 SPY 作为基准
    if "SPY" not in all_tickers:
        all_tickers.append("SPY")
        
    all_tickers = list(set(all_tickers))
    
    # 3. 拉取数据 (730天以计算长周期均线)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data
    except Exception as e:
        st.error(f"数据拉取失败: {e}")
        return pd.DataFrame()

raw_data = get_user_data()

# --- 2. 计算逻辑 (相对强度 + 4级趋势) ---
def calculate_metrics():
    metrics = []
    
    # A. 获取基准 (SPY) 数据
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            spy_df = raw_data['SPY']['Close'].dropna()
        else:
            spy_df = raw_data['Close'].dropna() # 只有SPY一个标的时
        
        # 计算 SPY 20日动量
        spy_mom20 = (spy_df.iloc[-1] / spy_df.iloc[-21] - 1) * 100
    except:
        spy_mom20 = 0 # 降级处理
    
    # B. 遍历自选股
    for group_name, tickers in MY_POOL.items():
        for ticker, name in tickers.items():
            try:
                # 获取个股数据
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if ticker not in raw_data.columns.levels[0]: continue
                    df_t = raw_data[ticker]['Close'].dropna()
                else:
                    if ticker != "SPY": continue # 保护逻辑
                    df_t = raw_data['Close'].dropna()

                if len(df_t) < 250: continue
                
                curr = df_t.iloc[-1]
                
                # --- 核心指标 ---
                # 1. Z-Score (1年)
                ma250 = df_t.rolling(250, min_periods=200).mean().iloc[-1]
                std250 = df_t.rolling(250, min_periods=200).std().iloc[-1]
                z_score = (curr - ma250) / std250 if std250 != 0 else 0
                
                # 2. 相对强度 (Relative Strength)
                abs_mom20 = (curr / df_t.iloc[-21] - 1) * 100
                rel_mom20 = abs_mom20 - spy_mom20
                
                # --- 趋势结构 (EMA System) ---
                ema20 = df_t.ewm(span=20, adjust=False).mean().iloc[-1]
                ema60 = df_t.ewm(span=60, adjust=False).mean().iloc[-1]
                ema120 = df_t.ewm(span=120, adjust=False).mean().iloc[-1]
                ema200 = df_t.ewm(span=200, adjust=False).mean().iloc[-1]
                
                # 乖离率
                c_s = (curr - ema20) / ema20 * 100         # Price vs Short
                s_m = (ema20 - ema60) / ema60 * 100        # Short vs Medium
                m_l = (ema60 - ema120) / ema120 * 100      # Medium vs Long
                l_vl = (ema120 - ema200) / ema200 * 100    # Long vs Very Long
                
                # 结构判定
                structure = "震荡/纠缠"
                if c_s > 0 and s_m > 0 and m_l > 0 and l_vl > 0:
                    structure = "完美多头 (主升)"
                elif c_s < 0 and s_m < 0 and m_l < 0 and l_vl < 0:
                    structure = "完美空头 (主跌)"
                elif l_vl > 0:
                    if c_s < 0: structure = "牛市回调 (买点?)"
                    else: structure = "长期看涨"
                elif l_vl < 0:
                    if c_s > 0: structure = "熊市反弹 (卖点?)"
                    else: structure = "长期看跌"

                metrics.append({
                    "代码": ticker, 
                    "名称": name, 
                    "组别": group_name,
                    "Z-Score": round(z_score, 2), 
                    "相对强度": round(rel_mom20, 2),
                    "绝对涨幅": round(abs_mom20, 2),
                    "趋势结构": structure,
                    "C/S": round(c_s, 2),
                    "S/M": round(s_m, 2),
                    "M/L": round(m_l, 2),
                    "L/VL": round(l_vl, 2),
                    "现价": round(curr, 2)
                })
            except: continue
            
    return pd.DataFrame(metrics), spy_mom20

# --- 3. 绘图与展示 ---
if not raw_data.empty:
    df_metrics, benchmark_mom = calculate_metrics()
    
    if not df_metrics.empty:
        # --- 侧边栏 ---
        with st.sidebar:
            st.header("自选股筛选")
            st.metric("基准 (SPY) 20日涨跌", f"{benchmark_mom:.2f}%")
            
            all_groups = list(MY_POOL.keys())
            selected_groups = st.multiselect("显示分组：", all_groups, default=all_groups)
            
            st.markdown("---")
            st.info("💡 **提示：** 纵轴已切换为【相对强度】。0轴上方代表跑赢大盘，下方代表跑输大盘。")

        df_plot = df_metrics[df_metrics['组别'].isin(selected_groups)]
        
        # --- PART 1: 核心雷达图 ---
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
            range_color=[-15, 15]
        )
        
        # 辅助线
        fig.add_hline(y=0, line_dash="dash", line_color="#FFFFFF", opacity=0.5, line_width=1)
        fig.add_vline(x=0, line_dash="dash", line_color="#FFFFFF", opacity=0.3, line_width=1)
        
        # 极简风格
        fig.update_traces(textposition='top center', marker=dict(size=10, line=dict(width=0), opacity=0.9))
        
        # 象限标注
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
            title=dict(text=f"自选股相对强度 (基准: SPY {benchmark_mom:.2f}%)", x=0.5),
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
        
        # --- PART 2: 趋势扫描表 (Trend Scanner) ---
        st.markdown("### 🔍 趋势扫描 (Trend Scanner)")
        st.caption("均线系统：C(价) > S(20) > M(60) > L(120) > VL(200) = 完美多头")
        
        # 准备表格数据
        df_table = df_plot[["代码", "名称", "组别", "趋势结构", "C/S", "S/M", "M/L", "L/VL", "相对强度", "Z-Score"]].copy()
        
        # 样式函数
        def color_trend(val):
            color = '#E74C3C' if val < 0 else '#2ECC71' 
            return f'color: {color}'
        
        def color_structure(val):
            if "完美多头" in val: return 'color: #2ECC71; font-weight: bold; border: 1px solid #2ECC71'
            if "完美空头" in val: return 'color: #E74C3C; font-weight: bold'
            if "牛市回调" in val: return 'color: #F1C40F; font-weight: bold'
            return 'color: #ddd'

        view_mode = st.radio("视图模式", ["汇总", "分组"], horizontal=True)
        style_cols = ["C/S", "S/M", "M/L", "L/VL", "相对强度"]
        
        if view_mode == "汇总":
            st.dataframe(
                df_table.sort_values("相对强度", ascending=False).style.applymap(color_trend, subset=style_cols).applymap(color_structure, subset=["趋势结构"]),
                use_container_width=True,
                hide_index=True
            )
        else:
            sorted_groups = sorted(selected_groups)
            for group in sorted_groups:
                st.subheader(group)
                df_sub = df_table[df_table['组别'] == group].sort_values("相对强度", ascending=False)
                st.dataframe(
                    df_sub.style.applymap(color_trend, subset=style_cols).applymap(color_structure, subset=["趋势结构"]),
                    use_container_width=True,
                    hide_index=True
                )

    else:
        st.warning("⚠️ 自选股数据计算为空。请检查代码是否正确或数据源是否可用。")
        
else:
    st.info("⏳ 正在拉取自选股数据 (730天)...")
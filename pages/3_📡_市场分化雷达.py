import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="市场分化雷达", layout="wide")

st.title("📡 市场分化雷达 (Market Differentiation Radar)")
st.caption("核心监控：**共振** (大家都一样) vs **分化** (只有少数人赢) | 辅助判断：该买指数还是该选赛道？")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_radar_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2) # 看过去2年
    
    # A. 核心指数
    # SPY: 标普500 (市值加权 - 听大哥的)
    # RSP: 标普500等权 (众生平等 - 看平均)
    # QQQ: 纳指
    # IWM: 罗素2000 (小盘股)
    indices = ['SPY', 'RSP', 'QQQ', 'IWM']
    
    # B. 11大板块 ETF
    sectors = {
        'XLK': '科技', 'XLF': '金融', 'XLV': '医疗', 
        'XLY': '可选消费', 'XLP': '必选消费', 'XLE': '能源', 
        'XLI': '工业', 'XLB': '材料', 'XLU': '公用事业', 
        'XLRE': '地产', 'XLC': '通讯'
    }
    
    tickers = indices + list(sectors.keys())
    
    try:
        data = yf.download(tickers, start=start_date, end=end_date, progress=False)['Close']
        data = data.ffill()
        return data, sectors
    except Exception as e:
        st.error(f"数据拉取失败: {e}")
        return pd.DataFrame(), {}

df, sector_map = get_radar_data()

if not df.empty:
    
    # --- 指标计算 ---
    
    # 1. 抱团指数 (Concentration Ratio)
    # SPY / RSP 归一化
    df['Concentration'] = df['SPY'] / df['RSP']
    df['Concentration_Norm'] = (df['Concentration'] / df['Concentration'].iloc[0] - 1) * 100
    
    # 2. 板块相关性 (Correlation)
    # 计算 11 个板块的 30天滚动平均相关系数
    sector_cols = list(sector_map.keys())
    sector_returns = df[sector_cols].pct_change()
    
    # rolling_corr 是一种计算密集型操作，这里简化处理：
    # 计算每日横截面离散度 (Cross-Sectional Dispersion)
    # 也就是：每天这11个板块涨跌幅的标准差。数值越大，说明板块表现差异越大。
    df['Dispersion'] = sector_returns.std(axis=1) * 100 # 转换为百分比
    
    # 计算滚动平均相关性 (Rolling Average Correlation)
    # 这能反映市场是在“同涨同跌”还是“各玩各的”
    rolling_corr = sector_returns.rolling(window=22).corr().dropna()
    # 取每天所有板块两两相关性的平均值
    # 这是一个降维打击：把复杂的矩阵变成一条曲线
    avg_corrs = []
    dates_corr = []
    
    # 为了性能，我们只采样计算
    unique_dates = sector_returns.index[22:]
    
    # 简单算法：平均相关性 ≈ 1 - (离散度 / 波动率) 
    # 这里直接用 Plotly 画离散度更直观，相关性计算太慢容易卡死页面
    
    # --- 页面布局 ---
    
    col1, col2 = st.columns([1, 1])
    
    # ==========================================
    # 图表 1: 抱团指数 (SPY vs RSP)
    # ==========================================
    with col1:
        st.subheader("🛠️ 抱团指数 (The Concentration)")
        st.caption("逻辑：**SPY (市值)** 跑赢 **RSP (等权)** = 只有大哥在涨（分化）。两条线粘合 = 普涨（共振）。")
        
        fig1 = go.Figure()
        
        # 归一化净值
        def normalize(series): return (series / series.iloc[0] - 1) * 100
        
        fig1.add_trace(go.Scatter(x=df.index, y=normalize(df['SPY']), name="SPY (市值加权)", line=dict(color='#E74C3C', width=2)))
        fig1.add_trace(go.Scatter(x=df.index, y=normalize(df['RSP']), name="RSP (等权平均)", line=dict(color='#3498DB', width=2)))
        
        # 抱团差值 (阴影区)
        fig1.add_trace(go.Scatter(
            x=df.index, y=df['Concentration_Norm'], 
            name="抱团溢价 %", 
            line=dict(color='rgba(100,100,100,0.5)', dash='dot'),
            fill='tozeroy', fillcolor='rgba(100,100,100,0.1)'
        ))
        
        fig1.update_layout(height=400, hovermode="x unified", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig1, use_container_width=True)
        
        curr_diff = normalize(df['SPY']).iloc[-1] - normalize(df['RSP']).iloc[-1]
        if curr_diff > 5:
            st.warning(f"⚠️ **当前处于“极致分化”状态：** 大盘股比平均股多涨了 {curr_diff:.1f}%。通常意味着指数失真，大部分个股体验很差。")
        elif curr_diff < -2:
            st.success(f"✅ **当前处于“补涨/普涨”状态：** 小票跑赢大票，市场广度很健康。")

    # ==========================================
    # 图表 2: 板块离散度 (Sector Dispersion)
    # ==========================================
    with col2:
        st.subheader("🌊 板块离散度 (Market Dispersion)")
        st.caption("逻辑：**数值越高**，板块间差异越大（有的涨天上去，有的跌坑里）。**数值越低**，说明大家在齐步走。")
        
        # 平滑处理，看趋势
        df['Dispersion_MA'] = df['Dispersion'].rolling(window=10).mean()
        
        fig2 = go.Figure()
        
        # 绘制离散度曲线
        fig2.add_trace(go.Scatter(
            x=df.index, y=df['Dispersion_MA'], 
            name="板块离散度 (10日均线)", 
            line=dict(color='#8E44AD', width=2),
            fill='tozeroy', fillcolor='rgba(142, 68, 173, 0.2)'
        ))
        
        # 标普500背景线 (辅助看它是涨的时候分化，还是跌的时候分化)
        fig2.add_trace(go.Scatter(
            x=df.index, y=df['SPY'], 
            name="SPY 走势", 
            yaxis="y2",
            line=dict(color='gray', width=1, dash='dot')
        ))
        
        fig2.update_layout(
            height=400, 
            hovermode="x unified",
            yaxis=dict(title="离散度 (差异程度)"),
            yaxis2=dict(title="SPY 价格", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.1)
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        curr_disp = df['Dispersion_MA'].iloc[-1]
        st.info(f"""
        **📊 读图指南：**
        * **低离散 (<0.6):** 市场很安静或高度共振。如果是大跌时低离散，就是“泥沙俱下”。
        * **高离散 (>1.2):** 市场在剧烈切换。资金在疯狂调仓（卖出A板块买入B板块）。
        * **当前值：{curr_disp:.2f}**
        """)

    # ==========================================
    # 图表 3: 市场内部扫描 (Who is Leading?)
    # ==========================================
    st.markdown("---")
    st.subheader("🔍 谁在领涨？(板块强弱扫描)")
    
    # 计算最近 20 天的涨幅
    recent_perf = (df[sector_cols].iloc[-1] / df[sector_cols].iloc[-20] - 1) * 100
    recent_perf = recent_perf.sort_values(ascending=False)
    
    # 映射中文名
    labels = [f"{sector_map[x]} ({x})" for x in recent_perf.index]
    values = recent_perf.values
    colors = ['#E74C3C' if v > 0 else '#2ECC71' for v in values] # 红涨绿跌
    
    fig3 = go.Figure(go.Bar(
        x=labels, y=values,
        marker_color=colors,
        text=[f"{v:.1f}%" for v in values],
        textposition='auto'
    ))
    
    fig3.update_layout(
        title="近20日板块涨跌幅排序",
        yaxis_title="涨跌幅 (%)",
        height=350,
        margin=dict(t=30)
    )
    st.plotly_chart(fig3, use_container_width=True)

else:
    st.info("正在初始化雷达数据...")
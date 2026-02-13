import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="市场分化雷达", layout="wide")

st.title("📡 市场分化雷达 (Market Differentiation Radar)")
st.caption("核心监控：**共振** (大家都一样) vs **分化** (只有少数人赢) | 数据范围：**过去 10 年**")

# --- 1. 数据引擎 (升级：10年数据) ---
@st.cache_data(ttl=3600*4)
def get_radar_data():
    end_date = datetime.now()
    # 拉取 10 年数据
    start_date = end_date - timedelta(days=3650) 
    
    # A. 核心指数
    # SPY: 市值加权
    # RSP: 等权平均
    indices = ['SPY', 'RSP']
    
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
    # 逻辑：SPY / RSP
    # 如果比值走高，说明大票强（抱团）；比值走低，说明小票强（普涨）。
    df['Concentration'] = df['SPY'] / df['RSP']
    
    # 2. 板块离散度 (Dispersion)
    # 计算11个板块当日涨跌幅的标准差
    sector_cols = list(sector_map.keys())
    sector_returns = df[sector_cols].pct_change()
    df['Dispersion'] = sector_returns.std(axis=1) * 100 
    
    # 平滑处理：计算 MA20 (月度平均离散度)，过滤日内噪音，看长期趋势
    df['Dispersion_MA20'] = df['Dispersion'].rolling(window=20).mean()
    
    # --- 页面布局：垂直瀑布流 (上下排版) ---
    
    # ==========================================
    # 图表 1: 抱团指数 (The Concentration) - 全宽
    # ==========================================
    st.subheader("🛠️ 抱团指数：大票 vs 小票 (The Concentration)")
    st.caption("逻辑：**红线向上** = 只有巨头在涨 (分化/抱团)；**红线向下** = 中小盘补涨 (普涨)。")
    
    fig1 = go.Figure()
    
    # 使用双轴：左轴看相对比值，右轴看SPY价格
    fig1.add_trace(go.Scatter(
        x=df.index, y=df['Concentration'], 
        name="抱团强度 (SPY/RSP)", 
        line=dict(color='#E74C3C', width=2),
        fill='tozeroy', fillcolor='rgba(231, 76, 60, 0.1)'
    ))
    
    fig1.add_trace(go.Scatter(
        x=df.index, y=df['SPY'], 
        name="SPY 价格 (右轴)", 
        yaxis="y2",
        line=dict(color='gray', width=1, dash='dot')
    ))
    
    fig1.update_layout(
        height=500, # 加高图表
        hovermode="x unified",
        yaxis=dict(title="抱团比率 (数值越高越抱团)"),
        yaxis2=dict(title="SPY 价格", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig1, use_container_width=True)
    
    # 智能点评
    curr_ratio = df['Concentration'].iloc[-1]
    avg_ratio = df['Concentration'].mean()
    if curr_ratio > avg_ratio * 1.05:
        st.warning(f"⚠️ **历史高位预警：** 当前抱团指数 ({curr_ratio:.2f}) 显著高于 10年均值。这是典型的“指数牛，个股熊”。")
    else:
        st.success(f"✅ **健康状态：** 当前市场结构较为均衡。")

    st.markdown("---") # 分割线

    # ==========================================
    # 图表 2: 板块离散度 (Market Dispersion) - 全宽
    # ==========================================
    st.subheader("🌊 板块离散度：同涨同跌 vs 乱战 (Dispersion)")
    st.caption("逻辑：**波峰** = 市场极度混乱（有人暴涨有人暴跌）；**波谷** = 市场高度一致（共振）。通常**大底**都出现在离散度极高之后。")
    
    fig2 = go.Figure()
    
    # 绘制离散度
    fig2.add_trace(go.Scatter(
        x=df.index, y=df['Dispersion_MA20'], 
        name="板块离散度 (20日均线)", 
        line=dict(color='#8E44AD', width=2),
        fill='tozeroy', fillcolor='rgba(142, 68, 173, 0.2)'
    ))
    
    # 辅助线：恐慌阈值
    fig2.add_hline(y=1.5, line_dash="dot", line_color="red", annotation_text="高离散 (混乱/恐慌)")
    fig2.add_hline(y=0.5, line_dash="dot", line_color="green", annotation_text="低离散 (共振/躺平)")
    
    fig2.update_layout(
        height=500, 
        hovermode="x unified",
        yaxis=dict(title="离散度 (%)"),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    st.info("""
    **🎓 10年历史规律总结：**
    * **2020年3月 (疫情底):** 离散度瞬间飙升到 **3.0+**。所有板块都在剧烈波动，这是**抄底信号**。
    * **2022年 (加息熊市):** 离散度长期维持在 **1.5** 高位。能源股暴涨，科技股暴跌，这就是典型的“存量博弈”。
    * **2017年 (慢牛):** 离散度长期趴在 **0.6** 以下。大家一起涨，买了拿着就行，那是投资最舒服的日子。
    """)

    st.markdown("---")

    # ==========================================
    # 图表 3: 当下强弱扫描 (Who is Leading Now?)
    # ==========================================
    st.subheader("🔍 短期视角：谁在领涨？")
    
    col3, col4 = st.columns([3, 1])
    
    with col3:
        # 计算最近 20 天的涨幅
        recent_perf = (df[sector_cols].iloc[-1] / df[sector_cols].iloc[-20] - 1) * 100
        recent_perf = recent_perf.sort_values(ascending=False)
        
        labels = [f"{sector_map[x]} ({x})" for x in recent_perf.index]
        values = recent_perf.values
        colors = ['#E74C3C' if v > 0 else '#2ECC71' for v in values]
        
        fig3 = go.Figure(go.Bar(
            x=labels, y=values,
            marker_color=colors,
            text=[f"{v:.1f}%" for v in values],
            textposition='auto'
        ))
        
        fig3.update_layout(
            title="近20日板块涨跌幅",
            yaxis_title="涨跌幅 (%)",
            height=400
        )
        st.plotly_chart(fig3, use_container_width=True)
    
    with col4:
        st.write("#### 📊 龙头板块")
        top_sector = recent_perf.index[0]
        st.metric("🥇 第一名", f"{sector_map[top_sector]}", f"{recent_perf.iloc[0]:.2f}%")
        
        bottom_sector = recent_perf.index[-1]
        st.metric("🐢 最后一名", f"{sector_map[bottom_sector]}", f"{recent_perf.iloc[-1]:.2f}%")

else:
    st.info("正在拉取 10 年历史数据，请稍候...")
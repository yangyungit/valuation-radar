import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="市场分化雷达", layout="wide")

st.title("📡 市场分化雷达 (Market Differentiation Radar)")
st.caption("核心监控：**共振** (大家都一样) vs **分化** (只有少数人赢) | 数据范围：**过去 10 年**")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_radar_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650) # 10年
    
    # A. 核心指数
    indices = ['SPY', 'RSP']
    
    # B. 11大板块
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
    
    # 1. 归一化 (Normalize) - 让两条线从同一起跑线出发
    # (当前价格 / 起始价格 - 1) * 100
    df['SPY_Norm'] = (df['SPY'] / df['SPY'].iloc[0] - 1) * 100
    df['RSP_Norm'] = (df['RSP'] / df['RSP'].iloc[0] - 1) * 100
    
    # 计算差值用于警报
    curr_diff = df['SPY_Norm'].iloc[-1] - df['RSP_Norm'].iloc[-1]
    
    # 2. 板块离散度
    sector_cols = list(sector_map.keys())
    sector_returns = df[sector_cols].pct_change()
    df['Dispersion'] = sector_returns.std(axis=1) * 100 
    df['Dispersion_MA20'] = df['Dispersion'].rolling(window=20).mean()
    
    # --- 页面布局 ---
    
    # ==========================================
    # 图表 1: 抱团指数 (双线竞速版)     # ==========================================
    st.subheader("🛠️ 抱团指数：市值加权(红) vs 等权平均(蓝)")
    st.caption("视觉逻辑：**两条线粘合** = 普涨（健康）；**红线远高于蓝线** = 巨头吸血（分化）；**灰色阴影** = 撕裂程度。")
    
    fig1 = go.Figure()
    
    # 1. 绘制 SPY (大哥)
    fig1.add_trace(go.Scatter(
        x=df.index, y=df['SPY_Norm'], 
        name="SPY (市值加权) 累计涨幅%", 
        line=dict(color='#E74C3C', width=2)
    ))
    
    # 2. 绘制 RSP (平均)
    fig1.add_trace(go.Scatter(
        x=df.index, y=df['RSP_Norm'], 
        name="RSP (等权平均) 累计涨幅%", 
        line=dict(color='#3498DB', width=2),
        fill='tonexty', # 填充两线之间
        fillcolor='rgba(200, 200, 200, 0.2)' # 灰色阴影区
    ))
    
    fig1.update_layout(
        height=500, 
        hovermode="x unified",
        yaxis=dict(title="累计涨跌幅 (%)"),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig1, use_container_width=True)
    
    # 智能警报
    if curr_diff > 20:
        st.warning(f"⚠️ **极度分化预警：** 过去10年，大盘股跑赢平均股 **{curr_diff:.1f}%**。这通常是牛市末期或存量博弈的特征。")
    elif curr_diff < -10:
        st.success(f"✅ **中小盘优势期：** 平均股跑赢大盘股 **{abs(curr_diff):.1f}%**，市场广度极佳。")
    else:
        st.info(f"⚖️ **均衡状态：** 两者差距为 {curr_diff:.1f}%，市场结构相对健康。")

    st.markdown("---")

    # ==========================================
    # 图表 2: 板块离散度 (Market Dispersion)
    # ==========================================
    st.subheader("🌊 板块离散度：混乱程度 (Dispersion)")
    st.caption("逻辑：**波峰** = 市场混乱（有人暴涨有人暴跌）；**波谷** = 市场一致（躺平/共振）。")
    
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatter(
        x=df.index, y=df['Dispersion_MA20'], 
        name="板块离散度 (20日均线)", 
        line=dict(color='#8E44AD', width=2),
        fill='tozeroy', fillcolor='rgba(142, 68, 173, 0.2)'
    ))
    
    # 辅助线
    fig2.add_hline(y=1.5, line_dash="dot", line_color="red", annotation_text="高离散 (恐慌/剧烈切换)")
    fig2.add_hline(y=0.5, line_dash="dot", line_color="green", annotation_text="低离散 (共振/低波)")
    
    fig2.update_layout(
        height=500, 
        hovermode="x unified",
        yaxis=dict(title="离散度 (%)"),
        legend=dict(orientation="h", y=1.1)
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ==========================================
    # 图表 3: 强弱扫描
    # ==========================================
    st.subheader("🔍 短期视角：谁在领涨？")
    
    col3, col4 = st.columns([3, 1])
    
    with col3:
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
        st.write("#### 📊 强弱风向标")
        st.metric("🥇 领涨王", f"{sector_map[recent_perf.index[0]]}", f"{recent_perf.iloc[0]:.2f}%")
        st.metric("🐢 领跌王", f"{sector_map[recent_perf.index[-1]]}", f"{recent_perf.iloc[-1]:.2f}%")

else:
    st.info("正在拉取 10 年全景数据，请稍候...")
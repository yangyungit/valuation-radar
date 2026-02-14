import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全能市场雷达", layout="wide", page_icon="📡")

st.title("📡 全能市场雷达 (Market Radar Ultimate)")
st.caption("双层监控体系：**【上层】**看市场结构 (分化/共振)，**【下层】**看资产轮动 (全球/板块/赛道)。")

# ==========================================
# 1. 数据引擎 (Data Engine)
# ==========================================
@st.cache_data(ttl=3600*4)
def get_all_radar_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650) # 10年数据
    
    # --- A. 结构监控池 (Breadth) ---
    structure_tickers = ['SPY', 'RSP'] # 市值 vs 等权
    
    # --- B. 资产扫描池 (Scanner) ---
    # 1. 全球宏观
    global_assets = {
        "SPY": "美股", "QQQ": "纳指", "IWM": "罗素", "TLT": "20年美债", 
        "GLD": "黄金", "USO": "原油", "UUP": "美元", "BTC-USD": "比特币",
        "EEM": "新兴市场", "VGK": "欧洲", "EWJ": "日本"
    }
    # 2. 美股板块
    sectors = {
        'XLK': '科技', 'XLF': '金融', 'XLV': '医疗', 'XLY': '可选', 
        'XLP': '必选', 'XLE': '能源', 'XLI': '工业', 'XLB': '材料', 
        'XLU': '公用', 'XLRE': '地产', 'XLC': '通讯'
    }
    # 3. 风格赛道
    themes = {
        "SMH": "半导体", "IGV": "软件", "XBI": "生科", "ITA": "军工",
        "KWEB": "中概互联", "ARKK": "创新", "MTUM": "动量", "USMV": "低波",
        "COIN": "Coinbase", "NVDA": "英伟达" 
    }
    
    # 合并下载
    all_tickers = structure_tickers + list(global_assets.keys()) + list(sectors.keys()) + list(themes.keys())
    all_tickers = list(set(all_tickers)) # 去重
    
    try:
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, group_by='ticker')
        return data, global_assets, sectors, themes
    except Exception as e:
        st.error(f"数据拉取失败: {e}")
        return pd.DataFrame(), {}, {}, {}

raw_data, map_global, map_sector, map_theme = get_all_radar_data()

# ==========================================
# 2. 计算逻辑 (Logic Core)
# ==========================================
def calculate_scanner_metrics(ticker_map):
    """计算散点图所需的 Z-Score 和 Momentum"""
    metrics = []
    for ticker, name in ticker_map.items():
        try:
            df_t = raw_data[ticker]['Close'].dropna()
            if len(df_t) < 250: continue
            
            curr = df_t.iloc[-1]
            
            # Z-Score (1年估值位)
            ma250 = df_t.rolling(250).mean().iloc[-1]
            std250 = df_t.rolling(250).std().iloc[-1]
            z_score = (curr - ma250) / std250 if std250 != 0 else 0
            
            # Momentum (20日强度)
            mom20 = (curr / df_t.iloc[-21] - 1) * 100
            
            metrics.append({"代码": ticker, "名称": name, "Z-Score": round(z_score, 2), "Momentum": round(mom20, 2)})
        except: continue
    return pd.DataFrame(metrics)

def get_structure_df():
    """计算曲线图所需的 抱团指数 和 离散度"""
    # 提取收盘价
    df_close = pd.DataFrame()
    for t in raw_data.columns.levels[0]:
        df_close[t] = raw_data[t]['Close']
    df_close = df_close.ffill()
    
    # 1. 抱团指数
    df_res = pd.DataFrame()
    df_res['SPY_Norm'] = (df_close['SPY'] / df_close['SPY'].iloc[0] - 1) * 100
    df_res['RSP_Norm'] = (df_close['RSP'] / df_close['RSP'].iloc[0] - 1) * 100
    df_res['Concentration_Diff'] = df_res['SPY_Norm'] - df_res['RSP_Norm']
    
    # 2. 板块离散度
    sector_tickers = list(map_sector.keys())
    sec_rets = df_close[sector_tickers].pct_change()
    df_res['Dispersion'] = sec_rets.std(axis=1) * 100
    df_res['Dispersion_MA20'] = df_res['Dispersion'].rolling(20).mean()
    
    return df_res

# ==========================================
# 3. 页面渲染 (UI Rendering)
# ==========================================

if not raw_data.empty:
    df_struct = get_structure_df()
    
    # --- PART 1: 市场体温 (曲线图) ---
    st.header("1️⃣ 市场体温 (Market Structure)")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("🛠️ 抱团指数 (SPY vs RSP)")
        st.caption("红线在蓝线上方越远 = **抱团越严重** (只涨巨头)。")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=df_struct.index, y=df_struct['SPY_Norm'], name="SPY (市值)", line=dict(color='#E74C3C', width=2)))
        fig1.add_trace(go.Scatter(x=df_struct.index, y=df_struct['RSP_Norm'], name="RSP (等权)", line=dict(color='#3498DB', width=2), fill='tonexty'))
        fig1.update_layout(height=350, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig1, use_container_width=True)
        
    with col_chart2:
        st.subheader("🌊 离散度 (Dispersion)")
        st.caption("波峰 = **混乱/恐慌**；波谷 = **共振/一致**。")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_struct.index, y=df_struct['Dispersion_MA20'], name="离散度 (MA20)", line=dict(color='#8E44AD', width=2), fill='tozeroy'))
        fig2.add_hline(y=1.5, line_dash="dot", line_color="red")
        fig2.add_hline(y=0.5, line_dash="dot", line_color="green")
        fig2.update_layout(height=350, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # --- PART 2: 资产扫描 (散点图) ---
    st.header("2️⃣ 资产扫描 (Asset Scanner)")
    st.caption("四象限战法：**右上(强势)** | **右下(超跌)** | **左下(弱势)** | **左上(反转)**")
    
    # 三个 Tab 切换不同池子
    tab_global, tab_sector, tab_theme = st.tabs(["🌍 全球大类", "🏭 美股板块", "🚀 风格赛道"])
    
    def render_scatter(pool_map, key):
        df_metrics = calculate_scanner_metrics(pool_map)
        if df_metrics.empty:
            st.warning("数据不足")
            return
            
        fig = px.scatter(
            df_metrics, x="Z-Score", y="Momentum", text="名称", color="Momentum",
            color_continuous_scale="RdYlGn", size_max=60, hover_data=["代码"]
        )
        # 十字线
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        # 标注
        fig.add_annotation(x=2, y=10, text="🔥 强势", showarrow=False, font=dict(color="red"))
        fig.add_annotation(x=-2, y=-10, text="❄️ 弱势", showarrow=False, font=dict(color="blue"))
        
        fig.update_traces(textposition='top center', marker=dict(size=14, line=dict(width=1, color='DarkSlateGrey')))
        fig.update_layout(
            height=500, 
            xaxis_title="<-- 便宜 (低估值) | 昂贵 (高估值) -->",
            yaxis_title="<-- 资金流出 | 资金流入 -->",
            plot_bgcolor="#1e1e1e"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 数据表
        with st.expander(f"查看 {key} 详细数据"):
            st.dataframe(df_metrics.sort_values("Momentum", ascending=False).style.format("{:.2f}", subset=["Z-Score", "Momentum"]), use_container_width=True)

    with tab_global: render_scatter(map_global, "全球")
    with tab_sector: render_scatter(map_sector, "板块")
    with tab_theme: render_scatter(map_theme, "赛道")

else:
    st.info("⏳ 正在拉取全市场数据 (10年)，请稍候...")
import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("🌊 **视觉升级：** 引入 **Sankey (桑基图)**。不再看死板的市值，而是看资金在【央行 -> 财政 -> 市场】之间的**动态流转**。")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # B. 资产
    tickers = {
        "SPY": "🇺🇸 美股 (SPY)",
        "TLT": "📜 美债 (TLT)",
        "BTC-USD": "₿ 比特币 (BTC)"
    }
    try:
        df_assets = yf.download(list(tickers.keys()), start=start_date, end=end_date, progress=False)['Close']
        df_assets = df_assets.resample('D').ffill()
    except:
        df_assets = pd.DataFrame()

    if not df_macro.empty and df_macro.index.tz is not None: df_macro.index = df_macro.index.tz_localize(None)
    if not df_assets.empty and df_assets.index.tz is not None: df_assets.index = df_assets.index.tz_localize(None)

    df_all = pd.concat([df_macro, df_assets], axis=1)
    df_all = df_all.sort_index().ffill().dropna(how='all')
    
    if not df_all.empty:
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # === A. 准备时间轴 ===
    df_weekly = df.resample('W-FRI').last().iloc[-52:]
    available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
    if not available_dates: available_dates = [df.index[-1].strftime('%Y-%m-%d')]

    # === B. 布局：上图下控 ===
    # 建立两个容器：一个放 Sankey，一个放 Treemap (可选)，一个放滑块
    
    col_sankey, col_treemap = st.columns([2, 1])
    
    # 滑块放在最下面
    st.markdown("---")
    selected_date_str = st.select_slider(
        "📅 **拖动滑块：观察资金管道的粗细变化**",
        options=available_dates,
        value=available_dates[-1]
    )
    
    # === C. 计算选中日期的数据 ===
    curr_date = pd.to_datetime(selected_date_str)
    idx = df.index.get_indexer([curr_date], method='pad')[0]
    row = df.iloc[idx]
    
    # 获取核心数据
    fed = float(row.get('Fed_Assets', 0))
    tga = float(row.get('TGA', 0))
    rrp = float(row.get('RRP', 0))
    net_liq = float(row.get('Net_Liquidity', 0))
    
    # 简单的逻辑修正：如果数据有缺失，保证流出=流入
    # 实际上 Fed Assets = TGA + RRP + Currency + Reserves
    # 我们这里简化模型：Fed Assets ≈ TGA + RRP + Net Liquidity (Reserves)
    # 为了 Sankey 好看，我们强制配平
    total_flow = tga + rrp + net_liq
    if total_flow == 0: total_flow = 1 # 防止除0
    
    # === D. 绘制 Sankey (左侧大图) ===
    # 节点定义
    # 0: Fed Assets (源头)
    # 1: TGA (被锁死)
    # 2: RRP (被锁死)
    # 3: Net Liquidity (有效)
    # 4: Market Support (去向)
    
    with col_sankey:
        st.subheader("🌊 宏观液压图 (Hydraulic Flows)")
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 15,
                thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = ["🏛️ 美联储资产", "🔒 TGA (财政部)", "💤 RRP (逆回购)", "💧 净流动性", "📈 风险资产支撑"],
                color = ["#F1C40F", "#8E44AD", "#2E86C1", "#2ECC71", "#E74C3C"]
            ),
            link = dict(
                source = [0, 0, 0, 3], # 来源节点索引
                target = [1, 2, 3, 4], # 目标节点索引
                value =  [tga, rrp, net_liq, net_liq], # 流量值
                color =  ["#D7BDE2", "#AED6F1", "#ABEBC6", "#F1948A"] # 连线颜色 (淡化)
            )
        )])
        
        fig_sankey.update_layout(
            height=500,
            font=dict(size=14),
            margin=dict(t=20, l=10, r=10, b=20)
        )
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info(f"""
        **当前状态解读 ({selected_date_str}):**
        * 央行印了 **${fed:.2f}T** 的钱。
        * 其中 **${tga+rrp:.2f}T** 被 TGA 和 RRP **锁死**了 (紫色/蓝色管道)。
        * 只有 **${net_liq:.2f}T** 变成了真正的 **净流动性** (绿色管道)，流向市场。
        """)

    # === E. 绘制简版 Treemap (右侧辅助) ===
    with col_treemap:
        st.subheader("📦 资产池规模")
        # 这是一个简单的 snapshot，辅助看当前谁大
        vals = [
            row.get('M2', 0), row.get('SPY', 0), row.get('TLT', 0), row.get('BTC-USD', 0)
        ]
        lbls = ["M2", "美股", "美债", "比特币"]
        pars = ["", "root", "root", "root"]
        
        # 修正 treemap 结构
        # root -> [美股, 美债, 比特币] (M2 作为参考单独列出或不放)
        # 这里简单做个 Asset 只有的图
        
        fig_tree = go.Figure(go.Treemap(
            labels = ["资产池", "🇺🇸 美股", "📜 美债", "₿ BTC"],
            parents = ["", "资产池", "资产池", "资产池"],
            values = [0, row.get('SPY', 0), row.get('TLT', 0), row.get('BTC-USD', 0)],
            textinfo = "label+value",
            marker=dict(colors=["#333", "#E74C3C", "#3498DB", "#F39C12"])
        ))
        fig_tree.update_layout(height=500, margin=dict(t=20, l=10, r=10, b=20))
        st.plotly_chart(fig_tree, use_container_width=True)

else:
    st.info("⏳ 数据加载中...")
import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("逻辑: 边际定价原理 | 资金=因，资产=果 | 包含 TGA/RRP 分项拆解")

# --- 1. 坦克级数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) # 拉取2年数据
    
    # A. 宏观数据
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # B. 资产数据
    tickers = {
        "SPY": "🇺🇸 美股 (SPY)",
        "TLT": "📜 美债 (TLT)",
        "GLD": "🥇 黄金 (GLD)",
        "BTC-USD": "₿ 比特币 (BTC)",
        "USO": "🛢️ 原油 (USO)"
    }
    try:
        df_assets = yf.download(list(tickers.keys()), start=start_date, end=end_date, progress=False)['Close']
        df_assets = df_assets.resample('D').ffill()
    except:
        df_assets = pd.DataFrame()

    # C. 时区清洗
    if not df_macro.empty and df_macro.index.tz is not None:
        df_macro.index = df_macro.index.tz_localize(None)
    if not df_assets.empty and df_assets.index.tz is not None:
        df_assets.index = df_assets.index.tz_localize(None)

    # D. 合并
    df_all = pd.concat([df_macro, df_assets], axis=1)
    df_all = df_all.sort_index().ffill().dropna(how='all')
    
    # E. 计算指标
    if not df_all.empty:
        # 单位统一为 Billions
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all, tickers

# --- 2. 页面渲染 ---
df, asset_map = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # 获取最新日期
    curr_date = df.index[-1]
    prev_date = curr_date - timedelta(days=30)
    try:
        prev_idx_loc = df.index.get_indexer([prev_date], method='nearest')[0]
        prev_valid_date = df.index[prev_idx_loc]
    except:
        prev_valid_date = df.index[0]

    def get_val(col):
        return df.loc[curr_date, col] if col in df.columns else 0

    def get_pct(col):
        if col not in df.columns: return 0
        v1 = df.loc[curr_date, col]
        v0 = df.loc[prev_valid_date, col]
        return (v1 - v0) / v0 * 100 if v0 != 0 else 0

    # === Treemap (保持原样) ===
    treemap_data = [
        {"Name": "💰 M2 货币供应", "Cat": "Source", "Size": 22300, "Pct": get_pct('M2'), "Txt": f"${get_val('M2')/1000:.1f}T"},
        {"Name": "🖨️ 美联储资产", "Cat": "Source", "Size": get_val('Fed_Assets'), "Pct": get_pct('Fed_Assets'), "Txt": f"${get_val('Fed_Assets')/1000:.1f}T"},
        {"Name": "🏦 净流动性", "Cat": "Source", "Size": get_val('Net_Liquidity'), "Pct": get_pct('Net_Liquidity'), "Txt": f"${get_val('Net_Liquidity')/1000:.1f}T"},
        {"Name": "👜 财政部 TGA", "Cat": "Valve", "Size": get_val('TGA'), "Pct": get_pct('TGA'), "Txt": f"${get_val('TGA'):.0f}B"},
        {"Name": "♻️ 逆回购 RRP", "Cat": "Valve", "Size": get_val('RRP'), "Pct": get_pct('RRP'), "Txt": f"${get_val('RRP'):.0f}B"},
        {"Name": "🇺🇸 美股", "Cat": "Asset", "Size": 55000, "Pct": get_pct('SPY'), "Txt": "~$55T"},
        {"Name": "📜 美债", "Cat": "Asset", "Size": 52000, "Pct": get_pct('TLT'), "Txt": "~$52T"},
        {"Name": "🥇 黄金", "Cat": "Asset", "Size": 14000, "Pct": get_pct('GLD'), "Txt": "~$14T"},
        {"Name": "₿ 比特币", "Cat": "Asset", "Size": 2500, "Pct": get_pct('BTC-USD'), "Txt": "~$2.5T"}
    ]
    
    st.markdown("### 🗺️ 资金全景图 (Treemap)")
    fig_tree = px.treemap(
        pd.DataFrame(treemap_data), path=[px.Constant("全景资金池"), 'Cat', 'Name'], values='Size', color='Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'], range_color=[-5, 5],
        hover_data=['Txt', 'Pct']
    )
    fig_tree.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>30d: %{color:.2f}%", textfont=dict(size=14))
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=500)
    st.plotly_chart(fig_tree, use_container_width=True)

    # === 关键升级：带分项的趋势图 ===
    st.markdown("---")
    st.markdown("### 🔬 显微镜：解剖净流动性 (Deep Dive)")
    st.caption("这里展示【净流动性】是如何被 TGA、RRP 和 美联储资产 三个分项共同影响的。")
    
    # 截取过去1年
    df_chart = df.loc[df.index >= (curr_date - timedelta(days=365))].copy()
    
    # 归一化函数
    def normalize(series):
        return (series / series.iloc[0] - 1) * 100

    fig_line = go.Figure()
    
    # 1. 主角：净流动性 (绿色虚线，加粗)
    fig_line.add_trace(go.Scatter(
        x=df_chart.index, y=normalize(df_chart['Net_Liquidity']), 
        name='🏦 净流动性 (总水位)', 
        line=dict(color='#00FF00', width=4, dash='dot')
    ))
    
    # 2. 配角：三大分项 (细线，放在次要位置)
    fig_line.add_trace(go.Scatter(
        x=df_chart.index, y=normalize(df_chart['Fed_Assets']), 
        name='🖨️ 美联储资产 (印钞)', 
        line=dict(color='#FFFF00', width=1), # 黄色
        opacity=0.7
    ))
    
    fig_line.add_trace(go.Scatter(
        x=df_chart.index, y=normalize(df_chart['TGA']), 
        name='👜 TGA (政府存款)', 
        line=dict(color='#FF00FF', width=1), # 紫色
        opacity=0.7
    ))
    
    fig_line.add_trace(go.Scatter(
        x=df_chart.index, y=normalize(df_chart['RRP']), 
        name='♻️ 逆回购 (资金闲置)', 
        line=dict(color='#00FFFF', width=1), # 青色
        opacity=0.7
    ))

    # 3. 参照物：美股 (红色实线)
    fig_line.add_trace(go.Scatter(
        x=df_chart.index, y=normalize(df_chart['SPY']), 
        name='🇺🇸 美股 (SPY)', 
        line=dict(color='#FF4B4B', width=3)
    ))

    fig_line.update_layout(
        template="plotly_dark", 
        height=600, 
        hovermode="x unified", 
        yaxis_title="累计变动幅度 (%)",
        legend=dict(orientation="h", y=1.1)
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
    
    # --- 教学区 ---
    st.info("""
    💡 **如何像侦探一样看这张图？**
    
    1.  **先看绿色粗线 (净流动性)：** 它决定了美股 (红线) 的大方向。
    2.  **如果绿线跌了，去找原因：**
        * 是不是 **黄色细线 (Fed Assets)** 跌了？ -> 央行在缩表。
        * 是不是 **紫色细线 (TGA)** 暴涨了？ -> 财政部在抽血（收税/发债）。
        * 是不是 **青色细线 (RRP)** 暴涨了？ -> 市场恐慌，钱躲起来了。
    3.  **背离警告：** 如果红线 (美股) 还在涨，但绿线 (净流动性) 已经在跌，且是紫色 TGA 暴涨导致的，说明**财政抽水效应**正在发生，需警惕回调。
    """)

else:
    st.warning("⏳ 正在建立数据连接，请稍候...")
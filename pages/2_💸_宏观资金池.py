import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

# --- 侧边栏：视角切换 ---
with st.sidebar:
    st.header("🔭 观测模式")
    view_mode = st.radio(
        "选择方块大小 (Size) 代表什么？",
        ["🌍 真实市值 (Who is Big?)", "⚡ 剧烈程度 (Who is Moving?)"],
        index=0
    )
    
    if "真实" in view_mode:
        st.info("📦 **存量逻辑:**\n美股($55T) > 美联储($7T)。\n展示物理世界的真实体量对比。")
    else:
        st.success("💓 **心率逻辑:**\nSize = |30天涨跌幅%|\n如果TGA变动20%，美股变动2%，TGA的方块就是美股的10倍大。\n**谁动作大，谁就显眼。**")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")

# --- 1. 坦克级数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    
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

    # C. 清洗
    if not df_macro.empty and df_macro.index.tz is not None: df_macro.index = df_macro.index.tz_localize(None)
    if not df_assets.empty and df_assets.index.tz is not None: df_assets.index = df_assets.index.tz_localize(None)

    # D. 合并
    df_all = pd.concat([df_macro, df_assets], axis=1)
    df_all = df_all.sort_index().ffill().dropna(how='all')
    
    # E. 指标计算
    if not df_all.empty:
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
    
    curr_date = df.index[-1]
    prev_date = curr_date - timedelta(days=30)
    try:
        prev_idx_loc = df.index.get_indexer([prev_date], method='nearest')[0]
        prev_valid_date = df.index[prev_idx_loc]
    except:
        prev_valid_date = df.index[0]

    # 基础估值 (Base Cap in Billions)
    BASE_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

    def get_metrics(col, asset_type):
        if col not in df.columns: return 0, 0, 0
        v_curr = df.loc[curr_date, col]
        v_prev = df.loc[prev_valid_date, col]
        
        pct_change = (v_curr - v_prev) / v_prev * 100 if v_prev != 0 else 0
        
        # 1. 存量大小
        if asset_type == 'Macro': cap_size = v_curr 
        else: cap_size = BASE_CAPS.get(col, 100)
            
        # 2. 波动强度 (Intensity) = 绝对百分比变动
        # 给它加个底数 0.5，防止变动为0时方块消失
        intensity_size = abs(pct_change) + 0.5
            
        return v_curr, pct_change, cap_size, intensity_size

    # === 构建 Treemap 数据 ===
    data_list = []
    
    def add_item(name, col, cat, asset_type):
        val, pct, cap, intensity = get_metrics(col, asset_type)
        
        # 核心逻辑修正：根据模式选择 Size
        if "真实" in view_mode:
            final_size = cap # 存量模式
            mode_desc = "市值/规模"
        else:
            final_size = intensity # 剧烈程度模式
            mode_desc = "30天变动幅度"
            
        display_val = f"${val:.1f}B" if val < 10000 else f"${val/1000:.1f}T"
        if asset_type == 'Asset': display_val = f"~${cap/1000:.1f}T"
            
        data_list.append({
            "Name": name, "Category": cat, 
            "Size": final_size, "Pct": pct, 
            "Txt": display_val,
            "Intensity": f"{abs(pct):.2f}%"
        })

    # Source & Valve
    add_item("💰 M2 货币供应", "M2", "Source (水源)", "Macro")
    add_item("🖨️ 美联储资产", "Fed_Assets", "Source (水源)", "Macro")
    add_item("🏦 净流动性", "Net_Liquidity", "Source (水源)", "Macro")
    add_item("👜 财政部 TGA", "TGA", "Valve (调节阀)", "Macro")
    add_item("♻️ 逆回购 RRP", "RRP", "Valve (调节阀)", "Macro")
    
    # Assets
    add_item("🇺🇸 美股", "SPY", "Asset (资产)", "Asset")
    add_item("📜 美债", "TLT", "Asset (资产)", "Asset")
    add_item("🥇 黄金", "GLD", "Asset (资产)", "Asset")
    add_item("₿ 比特币", "BTC-USD", "Asset (资产)", "Asset")
    
    # === 绘制 Treemap ===
    st.markdown(f"### 🗺️ 资金全景图")
    
    fig_tree = px.treemap(
        pd.DataFrame(data_list), 
        path=[px.Constant("全景资金池"), 'Category', 'Name'], 
        values='Size', color='Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'], 
        range_color=[-5, 5],
        hover_data=['Txt', 'Pct', 'Intensity']
    )
    
    # Tooltip 动态文案
    hover_template = "<b>%{label}</b><br>当前数值: %{customdata[0]}<br>30天涨跌: %{color:.2f}%<br>变动剧烈度: %{customdata[2]}<extra></extra>"
    
    fig_tree.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%", hovertemplate=hover_template, textfont=dict(size=14))
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=550)
    st.plotly_chart(fig_tree, use_container_width=True)

    # === 深度分析 (K线图) ===
    st.markdown("---")
    st.markdown("### 🔬 净流动性分解 (The Breakdown)")
    
    df_chart = df.loc[df.index >= (curr_date - timedelta(days=365))].copy()
    def normalize(series): return (series / series.iloc[0] - 1) * 100

    fig_line = go.Figure()
    
    # 资金面
    fig_line.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['Net_Liquidity']), name='🏦 净流动性 (总水位)', line=dict(color='#00FF00', width=4, dash='dot')))
    fig_line.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['Fed_Assets']), name='🖨️ 美联储资产', line=dict(color='#FFFF00', width=1), opacity=0.7))
    fig_line.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['TGA']), name='👜 TGA (反向)', line=dict(color='#FF00FF', width=1), opacity=0.7))
    fig_line.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['RRP']), name='♻️ 逆回购 (反向)', line=dict(color='#00FFFF', width=1), opacity=0.7))
    
    # 资产面
    fig_line.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['SPY']), name='🇺🇸 美股', line=dict(color='#FF4B4B', width=2)))

    fig_line.update_layout(template="plotly_dark", height=500, hovermode="x unified", yaxis_title="累计变动 (%)", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig_line, use_container_width=True)

else:
    st.warning("⏳ 数据正在加载，请稍候...")
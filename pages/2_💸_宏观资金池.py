import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("🚀 **极速引擎 V3：** 修复动画渲染逻辑 | 逻辑：单根节点追踪 + 动态市值伸缩")

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
    
    # E. 指标
    if not df_all.empty:
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 强一致性动画帧生成器 ---
@st.cache_data(ttl=3600)
def generate_animation_frames(df):
    if df.empty: return pd.DataFrame()

    # 按周取样
    df_weekly = df.resample('W-FRI').last().iloc[-52:]

    frames = []
    
    # 静态参数
    LATEST_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }
    
    # 定义全员名单 (Root 必须统一)
    items = [
        ("💰 M2 货币", "M2", "Source", "Macro"),
        ("🖨️ 美联储", "Fed_Assets", "Source", "Macro"),
        ("🏦 净流动性", "Net_Liquidity", "Source", "Macro"),
        ("👜 TGA (财政)", "TGA", "Valve", "Macro"),
        ("♻️ RRP (逆回购)", "RRP", "Valve", "Macro"),
        ("🇺🇸 美股", "SPY", "Asset", "Asset"),
        ("📜 美债", "TLT", "Asset", "Asset"),
        ("🥇 黄金", "GLD", "Asset", "Asset"),
        ("₿ 比特币", "BTC-USD", "Asset", "Asset")
    ]
    
    latest_row = df.iloc[-1]

    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        
        # 找前值
        prev_date = date - timedelta(days=30)
        idx_curr = df.index.get_indexer([date], method='pad')[0]
        idx_prev = df.index.get_indexer([prev_date], method='pad')[0]
        
        row_curr = df.iloc[idx_curr]
        row_prev = df.iloc[idx_prev]

        for name, col, cat, asset_type in items:
            val_curr = 0.0
            pct = 0.0
            size = 0.1 

            if col in df.columns:
                val_curr = float(row_curr[col]) if not pd.isna(row_curr[col]) else 0.0
                val_prev = float(row_prev[col]) if not pd.isna(row_prev[col]) else 0.0
                val_latest = float(latest_row[col]) if not pd.isna(latest_row[col]) else 1.0
                
                if val_prev != 0:
                    pct = (val_curr - val_prev) / val_prev * 100
                
                # 动态 Size 逻辑 (保留你的需求)
                if asset_type == 'Macro':
                    size = abs(val_curr)
                else:
                    base_cap = float(LATEST_CAPS.get(col, 100))
                    if val_latest != 0:
                        size = base_cap * (val_curr / val_latest)
                    else:
                        size = base_cap
            
            display_val = f"${val_curr:,.0f}B"
            if size > 1000: display_val = f"${size/1000:.1f}T"
            if asset_type == 'Macro' and val_curr > 1000: display_val = f"${val_curr/1000:.1f}T"

            frames.append({
                "Date": date_str,
                "Root": "全球资金池", # <--- 关键修复：统一的根节点
                "Name": name,
                "Category": cat,
                "Size": max(size, 0.1), 
                "Color": pct,
                "Display": display_val
            })
            
    return pd.DataFrame(frames)

# --- 3. 页面渲染 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    with st.spinner("🎥 正在渲染前端动画引擎..."):
        df_anim = generate_animation_frames(df)
    
    if not df_anim.empty:
        # === Plotly 核心配置 ===
        # 关键修复：path必须包含 Root，且移除 ids 参数
        fig = px.treemap(
            df_anim,
            path=['Root', 'Category', 'Name'], 
            values='Size',
            color='Color',
            range_color=[-8, 8],
            color_continuous_scale=['#FF4B4B', '#1E1E1E', '#09AB3B'],
            hover_data=['Display', 'Color'],
            animation_frame="Date"
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%",
            textfont=dict(size=15),
            marker=dict(line=dict(width=1, color='black')) # 加点边框更清晰
        )
        
        # 优化滑块
        fig.update_layout(
            height=700,
            margin=dict(t=0, l=0, r=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            updatemenus=[dict(type="buttons", showactive=False, visible=False)],
            sliders=[{
                "currentvalue": {"prefix": "📅 历史回放: ", "font": {"size": 20}},
                "pad": {"t": 50},
                "len": 1.0,
                "x": 0, "y": 0,
                "transition": {"duration": 300, "easing": "cubic-in-out"}
            }]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.success("✅ 引擎就绪。请直接拖动滑块，体验丝滑变动。")
        
    else:
        st.error("数据处理异常")
else:
    st.info("⏳ 正在初始化...")
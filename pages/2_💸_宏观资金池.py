import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("🛡️ **稳定版内核：** 仅展示市值/规模的物理变化。无复杂计算，0延迟拖拽。")

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

# --- 2. 纯净版动画生成器 (Type Safe) ---
@st.cache_data(ttl=3600)
def generate_simple_frames(df):
    if df.empty: return pd.DataFrame()

    # 按周取样
    df_weekly = df.resample('W-FRI').last().iloc[-52:]
    latest_row = df.iloc[-1]
    
    frames = []
    
    # 静态基准
    LATEST_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }
    
    items = [
        ("💰 M2 货币", "M2", "Source (水源)", "Macro"),
        ("🖨️ 美联储", "Fed_Assets", "Source (水源)", "Macro"),
        ("🏦 净流动性", "Net_Liquidity", "Source (水源)", "Macro"),
        ("👜 TGA (财政)", "TGA", "Valve (调节阀)", "Macro"),
        ("♻️ RRP (逆回购)", "RRP", "Valve (调节阀)", "Macro"),
        ("🇺🇸 美股", "SPY", "Asset (资产)", "Asset"),
        ("📜 美债", "TLT", "Asset (资产)", "Asset"),
        ("🥇 黄金", "GLD", "Asset (资产)", "Asset"),
        ("₿ 比特币", "BTC-USD", "Asset (资产)", "Asset")
    ]
    
    for date in df_weekly.index:
        date_str = str(date.strftime('%Y-%m-%d')) # 强转 str
        row = df_weekly.loc[date]
        
        for name, col, cat, asset_type in items:
            val_curr = 0.0
            size = 0.1 

            if col in df.columns:
                # 强转 float，消除 numpy 类型隐患
                val_curr = float(row.get(col, 0)) if not pd.isna(row.get(col)) else 0.0
                val_latest = float(latest_row.get(col, 1)) if not pd.isna(latest_row.get(col)) else 1.0
                
                if asset_type == 'Macro':
                    size = abs(val_curr)
                else:
                    base = float(LATEST_CAPS.get(col, 100))
                    if val_latest != 0: 
                        size = base * (val_curr / val_latest)
                    else: 
                        size = base
            
            # 显示文本
            display_val = f"${val_curr:,.0f}B"
            if size > 1000: display_val = f"${size/1000:.1f}T"
            if asset_type == 'Macro' and val_curr > 1000: display_val = f"${val_curr/1000:.1f}T"

            frames.append({
                "Date": date_str,
                "Category": str(cat), 
                "Name": str(name),
                "Size": float(max(size, 0.1)), # 强转 float
                "Display": str(display_val)
            })
            
    return pd.DataFrame(frames)

# --- 3. 页面渲染 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    with st.spinner("🎥 正在组装时光机组件..."):
        df_anim = generate_simple_frames(df)
    
    if not df_anim.empty:
        # === 极简配置 ===
        # 移除 Root，只用 Category -> Name
        fig = px.treemap(
            df_anim,
            path=['Category', 'Name'], 
            values='Size',
            color='Category', 
            color_discrete_map={
                "Source (水源)": "#2E86C1", # 蓝
                "Valve (调节阀)": "#8E44AD", # 紫
                "Asset (资产)": "#D35400"   # 橙
            },
            hover_data=['Display'],
            animation_frame="Date"
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]}",
            textfont=dict(size=18),
            # 加粗边框，增加质感
            marker=dict(line=dict(width=2, color='white'))
        )
        
        fig.update_layout(
            height=700,
            margin=dict(t=0, l=0, r=0, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            updatemenus=[dict(type="buttons", showactive=False, visible=False)],
            sliders=[{
                "currentvalue": {"prefix": "📅 历史: ", "font": {"size": 20}},
                "pad": {"t": 50},
                "len": 1.0,
                "x": 0, "y": 0,
                # 线性过渡，最稳
                "transition": {"duration": 300, "easing": "linear"} 
            }]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.success("✅ 物理引擎已加载。拖动滑块观察【面积】变化。")
        
    else:
        st.error("数据加载失败")
else:
    st.info("⏳ 正在连接数据源...")
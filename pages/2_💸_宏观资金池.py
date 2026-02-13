import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

# --- 侧边栏 ---
with st.sidebar:
    st.header("🎮 时光机控制台")
    view_mode = st.radio(
        "选择方块大小 (Size) 代表什么？",
        ["🌍 真实市值 (Who is Big?)", "⚡ 剧烈程度 (Who is Moving?)"],
        index=0
    )
    
    st.info("""
    🕹️ **如何使用时光机：**
    1. 点击图表底部的 ▶️ **播放键**。
    2. 观察过去一年方块大小和颜色的律动。
    3. **TGA (紫色)** 变大通常意味着流动性收紧。
    """)

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)
    
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

# --- 2. 动画帧生成器 (修复版) ---
@st.cache_data(ttl=3600)
def generate_animation_frames(df, mode):
    if df.empty: return pd.DataFrame()

    # 重采样为周频 (每周五)
    df_weekly = df.resample('W-FRI').last()
    df_weekly = df_weekly.iloc[-52:] # 取最近一年

    frames = []
    
    # 基础估值
    BASE_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

    items = [
        ("💰 M2 货币供应", "M2", "Source (水源)", "Macro"),
        ("🖨️ 美联储资产", "Fed_Assets", "Source (水源)", "Macro"),
        ("🏦 净流动性", "Net_Liquidity", "Source (水源)", "Macro"),
        ("👜 财政部 TGA", "TGA", "Valve (调节阀)", "Macro"),
        ("♻️ 逆回购 RRP", "RRP", "Valve (调节阀)", "Macro"),
        ("🇺🇸 美股", "SPY", "Asset (资产)", "Asset"),
        ("📜 美债", "TLT", "Asset (资产)", "Asset"),
        ("🥇 黄金", "GLD", "Asset (资产)", "Asset"),
        ("₿ 比特币", "BTC-USD", "Asset (资产)", "Asset")
    ]

    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        
        # 找30天前
        prev_date = date - timedelta(days=30)
        try:
            prev_idx = df.index.get_indexer([prev_date], method='nearest')[0]
            val_prev_row = df.iloc[prev_idx]
        except:
            continue

        row_data = df_weekly.loc[date]

        for name, col, cat, asset_type in items:
            if col not in df.columns: continue
            
            val_curr = row_data[col]
            val_prev = val_prev_row[col]
            
            if pd.isna(val_curr) or val_curr == 0: continue
            
            pct = (val_curr - val_prev) / val_prev * 100 if val_prev != 0 else 0
            
            # Size 逻辑
            if "真实" in mode:
                if asset_type == 'Macro': size = abs(val_curr)
                else: size = BASE_CAPS.get(col, 100)
            else:
                size = abs(pct) + 0.1 
            
            display_val = f"${val_curr:.1f}B" if val_curr < 10000 else f"${val_curr/1000:.1f}T"
            if asset_type == 'Asset': display_val = f"~${BASE_CAPS.get(col,0)/1000:.1f}T"

            frames.append({
                "Date": date_str,
                "Root": "全球资金池", # <--- 关键修复：把Root直接写进数据里
                "Name": name,
                "Category": cat,
                "Size": size,
                "Color_Pct": pct,
                "Display": display_val
            })
            
    return pd.DataFrame(frames)

# --- 3. 页面渲染 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    df_anim = generate_animation_frames(df, view_mode)
    
    if not df_anim.empty:
        # 修复后的 Plotly 调用
        fig = px.treemap(
            df_anim,
            # 关键修复：用真实的 'Root' 列替代 px.Constant
            path=['Root', 'Category', 'Name'], 
            values='Size',
            color='Color_Pct',
            color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
            range_color=[-5, 5],
            hover_data=['Display', 'Color_Pct'],
            animation_frame="Date" 
            # 移除 animation_group="Name"，这在 treemap 里通常会导致问题
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%",
            textfont=dict(size=14)
        )
        
        # 优化滑块和播放器
        fig.update_layout(
            height=700,
            margin=dict(t=0, l=0, r=0, b=0),
            coloraxis_colorbar=dict(title="30天涨跌%"),
            sliders=[dict(currentvalue={"prefix": "📅 历史回放: "}, pad={"t": 50})],
            updatemenus=[dict(type="buttons", showactive=False, x=0.1, y=-0.1)]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.success(f"🎥 时光机加载完毕！请点击左下角 ▶️ 播放键，见证资金流转的历史。")
        
    else:
        st.warning("数据初始化中，请稍等...")
else:
    st.info("⏳ 正在建立数据连接...")
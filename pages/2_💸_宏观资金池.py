import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

# --- 侧边栏：控制台 ---
with st.sidebar:
    st.header("🎮 时光机控制台")
    view_mode = st.radio(
        "选择方块大小 (Size) 代表什么？",
        ["🌍 真实市值 (Who is Big?)", "⚡ 剧烈程度 (Who is Moving?)"],
        index=0
    )
    
    st.info("""
    🕹️ **如何使用时光机：**
    1. 图表底部会出现一个 **播放条**。
    2. 点击 ▶️ **播放**：自动演示过去一年的资金演变。
    3. **拖拽滑块**：手动定格在历史的某一周，查看当时谁大谁小。
    """)

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")

# --- 1. 数据引擎 (Tank Engine) ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) # 拉取过去400天
    
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
            
    return df_all

# --- 2. 动画数据生成器 (The Animator) ---
@st.cache_data(ttl=3600)
def generate_animation_frames(df, mode):
    """
    将宽表转换为长表，并按周重采样，生成适合 Plotly Animation 的格式
    """
    if df.empty: return pd.DataFrame()

    # 1. 重采样为周频 (每周五)，减少帧数以保证流畅度
    df_weekly = df.resample('W-FRI').last()
    
    # 只取最近52周（一年）
    df_weekly = df_weekly.iloc[-52:] 

    frames = []
    
    # 基础估值 (Base Cap in Billions)
    BASE_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

    # 定义要展示的项目
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

    # 遍历每一周
    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        
        # 找30天前的数据 (Rolling Window)
        prev_date = date - timedelta(days=30)
        # 即使找不到完全匹配的，也找最近的
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
            
            # 计算指标
            if pd.isna(val_curr) or val_curr == 0: continue
            
            pct = (val_curr - val_prev) / val_prev * 100 if val_prev != 0 else 0
            
            # 决定 Size
            if "真实" in mode:
                if asset_type == 'Macro': size = abs(val_curr) # 取绝对值防负数
                else: size = BASE_CAPS.get(col, 100)
            else:
                # 剧烈程度模式
                size = abs(pct) + 0.1 # +0.1 保证不消失
            
            # 文本显示
            display_val = f"${val_curr:.1f}B" if val_curr < 10000 else f"${val_curr/1000:.1f}T"
            if asset_type == 'Asset': display_val = f"~${BASE_CAPS.get(col,0)/1000:.1f}T"

            frames.append({
                "Date": date_str,
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
    
    # 生成动画数据
    df_anim = generate_animation_frames(df, view_mode)
    
    if not df_anim.empty:
        # 动态 Treemap
        fig = px.treemap(
            df_anim,
            path=[px.Constant("全景资金池"), 'Category', 'Name'],
            values='Size',
            color='Color_Pct',
            color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
            range_color=[-5, 5],
            hover_data=['Display', 'Color_Pct'],
            animation_frame="Date", # <--- 核心：按日期生成动画帧
            animation_group="Name"  # <--- 核心：保证方块平滑过渡
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%",
            textfont=dict(size=14)
        )
        
        fig.update_layout(
            height=650,
            margin=dict(t=0, l=0, r=0, b=0),
            coloraxis_colorbar=dict(title="30天涨跌%"),
            sliders=[dict(currentvalue={"prefix": "历史回放: "}, pad={"t": 50})] # 调整滑块位置
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.success(f"🎥 已生成 {len(df_anim['Date'].unique())} 周的历史快照。点击下方 ▶️ 播放键查看演变。")

    else:
        st.warning("数据不足以生成动画，请稍后再试。")

else:
    st.info("⏳ 正在启动时光机引擎... (首次加载需下载历史数据)")
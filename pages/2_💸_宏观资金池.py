import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("当前模式：**纯净版 (真实市值)** | 拖动下方滑块回看历史资金流向")

# --- 1. 数据引擎 (Tank Engine) ---
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

# --- 2. 极简动画帧生成器 ---
@st.cache_data(ttl=3600)
def generate_simple_frames(df):
    if df.empty: return pd.DataFrame()

    # 按周取样
    df_weekly = df.resample('W-FRI').last().iloc[-52:]

    frames = []
    
    # 固定的市值基准 (Billions)
    BASE_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

    # 定义全量对象
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

    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        
        # 找前值
        prev_date = date - timedelta(days=30)
        try:
            prev_idx = df.index.get_indexer([prev_date], method='nearest')[0]
            val_prev_row = df.iloc[prev_idx]
        except:
            val_prev_row = df_weekly.loc[date]

        row_data = df_weekly.loc[date]

        for name, col, cat, asset_type in items:
            # 默认安全值
            val_curr = 0.0
            pct = 0.0
            size = 1.0 # 默认给1，防止0报错

            if col in df.columns:
                val_curr = float(row_data[col]) if not pd.isna(row_data[col]) else 0.0
                val_prev = float(val_prev_row[col]) if not pd.isna(val_prev_row[col]) else 0.0
                
                # 计算30天涨跌
                if val_prev != 0:
                    pct = (val_curr - val_prev) / val_prev * 100
                
                # 计算大小 (Market Cap)
                if asset_type == 'Macro':
                    size = abs(val_curr)
                else:
                    size = float(BASE_CAPS.get(col, 100))

            # 严格确保 Size 不为 0
            size = max(size, 0.1)

            frames.append({
                "Date": date_str,
                "Root": "全球资金池", # 根节点
                "Name": name,
                "Category": cat,
                "Size": size,
                "Color": pct,
                "Display_Val": f"{val_curr:,.0f}"
            })
            
    return pd.DataFrame(frames)

# --- 3. 页面渲染 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    df_anim = generate_simple_frames(df)
    
    if not df_anim.empty:
        # 绘制图表
        fig = px.treemap(
            df_anim,
            path=['Root', 'Category', 'Name'], 
            values='Size',
            color='Color',
            # 这里的 range_color 必须是固定的数字，不能有 None
            range_color=[-5, 5],
            color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
            hover_data=['Display_Val', 'Color'],
            animation_frame="Date" 
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{color:.2f}%",
            textfont=dict(size=15)
        )
        
        fig.update_layout(
            height=700,
            margin=dict(t=20, l=10, r=10, b=10),
            sliders=[dict(currentvalue={"prefix": "📅 历史回放: "}, pad={"t": 50})]
        )
        
        st.plotly_chart(fig, use_container_width=True)
        st.success("🎥 时光机已启动。请点击下方 ▶️ 播放键或拖动滑块。")
        
    else:
        st.warning("数据处理中...")
else:
    st.info("⏳ 正在拉取最新数据...")
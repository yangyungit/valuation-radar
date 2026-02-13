import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("控制模式：**手动回溯** | 拖动滑块查看任意历史时刻的资金分布")

# --- 1. 数据引擎 (保持不变，因为它是好的) ---
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

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # === A. 准备时间轴数据 ===
    # 按周五取样，生成可选的日期列表
    df_weekly = df.resample('W-FRI').last().iloc[-52:] # 最近52周
    available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
    
    # 如果数据不够，就取全部
    if not available_dates:
        available_dates = [df.index[-1].strftime('%Y-%m-%d')]

    # === B. 核心交互：Streamlit 原生滑块 ===
    # 这就是"机械控制"的核心，绝不会崩
    st.markdown("### 📅 历史回放控制台")
    selected_date_str = st.select_slider(
        "拖动滑块选择时间：",
        options=available_dates,
        value=available_dates[-1] # 默认选最新
    )
    
    # === C. 计算选中那一周的数据 ===
    curr_date = pd.to_datetime(selected_date_str)
    
    # 找前值 (30天前)
    prev_date = curr_date - timedelta(days=30)
    try:
        prev_idx = df.index.get_indexer([prev_date], method='nearest')[0]
        val_prev_row = df.iloc[prev_idx]
    except:
        val_prev_row = df.iloc[0]

    row_data = df.loc[curr_date] if curr_date in df.index else df.iloc[-1]
    
    # 构建绘图数据 List
    plot_data = []
    
    BASE_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

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

    for name, col, cat, asset_type in items:
        if col in df.columns:
            val_curr = float(row_data[col]) if not pd.isna(row_data[col]) else 0.0
            val_prev = float(val_prev_row[col]) if not pd.isna(val_prev_row[col]) else 0.0
            
            # 涨跌幅
            pct = 0.0
            if val_prev != 0:
                pct = (val_curr - val_prev) / val_prev * 100
            
            # 市值大小
            if asset_type == 'Macro':
                size = abs(val_curr)
            else:
                size = float(BASE_CAPS.get(col, 100))
            
            # 文本
            display_val = f"${val_curr:,.0f}B"
            if val_curr > 1000: display_val = f"${val_curr/1000:.1f}T"
            if asset_type == 'Asset': display_val = f"~${size/1000:.1f}T"

            plot_data.append({
                "Root": "全球资金池",
                "Category": cat,
                "Name": name,
                "Size": max(size, 0.1), # 防止0
                "Color": pct,
                "Display": display_val
            })
            
    # === D. 绘制静态图 ===
    if plot_data:
        df_plot = pd.DataFrame(plot_data)
        
        fig = px.treemap(
            df_plot,
            path=['Root', 'Category', 'Name'],
            values='Size',
            color='Color',
            range_color=[-5, 5],
            color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
            hover_data=['Display', 'Color']
        )
        
        fig.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%",
            textfont=dict(size=16)
        )
        
        fig.update_layout(
            height=600,
            margin=dict(t=10, l=10, r=10, b=10),
            title=f"📅 当前展示时间: {selected_date_str}"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 增加一点文字解读
        if 'TGA' in row_data:
            tga_val = row_data['TGA']
            st.info(f"📊 **数据快照 ({selected_date_str}):** 此时财政部 TGA 余额为 **${tga_val:.0f}B**。")
    else:
        st.error("该日期暂无数据")

else:
    st.info("⏳ 正在初始化数据引擎...")
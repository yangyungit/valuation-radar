import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("逻辑升级：方块大小随价格**实时伸缩** | 布局优化：滑块置底")

# --- 1. 数据引擎 (拉取2年数据以保证计算不中断) ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    # 关键修改：拉取 730 天数据，确保哪怕滑到一年前，也能算出那时的"30天前"涨幅
    start_date = end_date - timedelta(days=730)
    
    # A. 宏观 (FRED)
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # B. 资产 (Yahoo)
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
            
    return df_all, tickers

# --- 2. 页面逻辑 ---
df, asset_map = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # === A. 准备时间轴 (最近52周) ===
    df_weekly = df.resample('W-FRI').last().iloc[-52:]
    available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
    
    if not available_dates:
        available_dates = [df.index[-1].strftime('%Y-%m-%d')]

    # 默认选中最新日期
    default_idx = len(available_dates) - 1
    
    # 占位符：图表容器 (先占位，稍后填充)
    chart_container = st.empty()
    
    # === B. 控制条 (放在图表下方) ===
    st.markdown("---")
    col_slider, col_info = st.columns([3, 1])
    
    with col_slider:
        selected_date_str = st.select_slider(
            "📅 **拖动滑块回溯历史：**",
            options=available_dates,
            value=available_dates[default_idx]
        )
    
    # === C. 计算逻辑 (动态市值核心) ===
    curr_date = pd.to_datetime(selected_date_str)
    
    # 1. 获取当前数据行
    # 使用 asof 确保即使选中的是周五但只有周四数据也能取到
    idx_loc = df.index.get_indexer([curr_date], method='pad')[0]
    row_data = df.iloc[idx_loc]

    # 2. 获取30天前数据行 (用于计算涨跌幅)
    prev_date = curr_date - timedelta(days=30)
    prev_idx_loc = df.index.get_indexer([prev_date], method='pad')[0]
    val_prev_row = df.iloc[prev_idx_loc]

    # 3. 获取最新数据行 (用于计算资产市值的缩放比例)
    latest_row = df.iloc[-1]

    # 基础估值锚点 (最新市值 Billions)
    LATEST_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500, "USO": 2000
    }

    plot_data = []
    
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
            # 取值 (加 float 强转)
            val_curr = float(row_data[col]) if not pd.isna(row_data[col]) else 0.0
            val_prev = float(val_prev_row[col]) if not pd.isna(val_prev_row[col]) else 0.0
            val_latest = float(latest_row[col]) if not pd.isna(latest_row[col]) else 1.0 # 防止除以0

            # 1. 计算涨跌幅 (消灭 NaN)
            pct = 0.0
            if val_prev != 0:
                pct = (val_curr - val_prev) / val_prev * 100
            
            # 2. 计算动态 Size (核心修复!)
            size = 1.0
            if asset_type == 'Macro':
                # 宏观数据直接用数值
                size = abs(val_curr)
            else:
                # 资产数据：动态缩放
                # 逻辑：历史市值 = 最新基准市值 * (历史价格 / 最新价格)
                # 这样当价格下跌时，方块面积会真实缩小！
                base_cap = float(LATEST_CAPS.get(col, 100))
                if val_latest != 0:
                    size = base_cap * (val_curr / val_latest)
                else:
                    size = base_cap

            # 3. 文本显示
            display_val = f"${val_curr:,.0f}B"
            if size > 1000: display_val = f"${size/1000:.1f}T" # 统一用Size来显示Trillion级别，更直观
            if asset_type == 'Macro' and val_curr > 1000: display_val = f"${val_curr/1000:.1f}T"

            plot_data.append({
                "Root": "全球资金池",
                "Category": cat,
                "Name": name,
                "Size": max(size, 0.1), 
                "Color": pct,
                "Display": display_val
            })

    # === D. 渲染图表 (填充到上方的容器) ===
    with chart_container:
        if plot_data:
            df_plot = pd.DataFrame(plot_data)
            
            # 动态标题
            net_liq_val = row_data.get('Net_Liquidity', 0)
            st.metric("🏦 当周净流动性水位", f"${net_liq_val/1000:.2f}T", f"{net_liq_val - val_prev_row.get('Net_Liquidity', 0):.0f}B (30d chg)")

            fig = px.treemap(
                df_plot,
                path=['Root', 'Category', 'Name'],
                values='Size',
                color='Color',
                range_color=[-8, 8], #稍微扩大颜色范围，避免太敏感
                color_continuous_scale=['#FF4B4B', '#1E1E1E', '#09AB3B'], # 深灰底色更高级
                hover_data=['Display', 'Color']
            )
            
            fig.update_traces(
                texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>%{color:.2f}%",
                textfont=dict(size=16)
            )
            
            fig.update_layout(
                height=600,
                margin=dict(t=0, l=0, r=0, b=0),
                paper_bgcolor='rgba(0,0,0,0)', # 透明背景
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 右侧信息栏 (显示选中日期的具体数值)
            with col_info:
                st.caption(f"📅 **{selected_date_str}**")
                if 'TGA' in row_data:
                    st.write(f"👜 **TGA:** ${row_data['TGA']:.0f}B")
                if 'RRP' in row_data:
                    st.write(f"♻️ **RRP:** ${row_data['RRP']:.0f}B")
                st.write(f"🇺🇸 **美股:** {row_data.get('SPY', 0):.2f}")

        else:
            st.error("数据加载异常，请刷新页面。")

else:
    st.info("⏳ 正在初始化时光机引擎...")
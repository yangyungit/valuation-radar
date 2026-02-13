import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("逻辑: 方块大小=真实市值 | 颜色=30天流向 | 曲线=过去1年累计涨幅对比")

# --- 1. 数据获取与清洗 (Data Engine) ---
@st.cache_data(ttl=3600*12)
def get_combined_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400) # 多拉一点保证覆盖
    
    # A. 获取宏观数据 (FRED)
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
    try:
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        # 强制日频化并填充
        df_macro = df_macro.resample('D').ffill().dropna()
        
        # 关键修复1：强制剥离时区 (如果有时区的话)，防止 TypeError
        if df_macro.index.tz is not None:
            df_macro.index = df_macro.index.tz_localize(None)
        
        # 单位统一为 Billions (十亿)
        df_macro['Fed_Assets'] = df_macro['WALCL'] / 1000
        df_macro['TGA'] = df_macro['WTREGEN'] / 1000
        df_macro['RRP'] = df_macro['RRPONTSYD']
        df_macro['M2'] = df_macro['M2SL']
        df_macro['Net_Liquidity'] = df_macro['Fed_Assets'] - df_macro['TGA'] - df_macro['RRP']
    except:
        df_macro = pd.DataFrame()

    # B. 获取资产数据 (Yahoo)
    tickers = {
        "SPY": "🇺🇸 美股 (SPY)",
        "TLT": "📜 美债 (TLT)",
        "GLD": "🥇 黄金 (GLD)",
        "BTC-USD": "₿ 比特币 (BTC)",
        "USO": "🛢️ 原油 (USO)"
    }
    try:
        df_assets = yf.download(list(tickers.keys()), start=start_date, end=end_date, progress=False)['Close']
        df_assets = df_assets.resample('D').ffill().dropna()
        
        # 关键修复2：强制剥离时区 (Yahoo 数据经常带 UTC)
        if df_assets.index.tz is not None:
            df_assets.index = df_assets.index.tz_localize(None)
            
    except:
        df_assets = pd.DataFrame()

    return df_macro, df_assets, tickers

# --- 2. 数据处理 ---
df_macro, df_assets, asset_map = get_combined_data()

if not df_macro.empty and not df_assets.empty:
    
    # --- 准备 Snapshot 数据 (用于 Treemap) ---
    curr_date = df_macro.index[-1]
    
    # 寻找30天前的日期
    try:
        # 使用 searchsorted 替代 get_loc，兼容性更好
        target_date = curr_date - timedelta(days=30)
        idx = df_macro.index.searchsorted(target_date)
        # 确保索引不越界
        idx = max(0, min(idx, len(df_macro)-1))
        prev_date = df_macro.index[idx]
    except:
        prev_date = df_macro.index[0]

    def calc_change(df, col, curr_date, prev_date):
        try:
            # 使用 asof 或直接索引 (最稳妥的方式)
            if curr_date in df.index and prev_date in df.index:
                curr_val = df.loc[curr_date][col]
                prev_val = df.loc[prev_date][col]
            else:
                # 如果找不到确切日期，找最近的 (Backfill/Pad)
                curr_val = df[col].asof(curr_date)
                prev_val = df[col].asof(prev_date)

            if pd.isna(prev_val) or prev_val == 0: return 0
            return (curr_val - prev_val) / prev_val * 100
        except: 
            return 0

    # === Treemap 数据构建 (真实市值比例) ===
    # Size 单位: Billions
    treemap_data = [
        # Source
        {
            "Name": "💰 M2 货币供应", "Category": "Source (水源)", "Size": 22300, 
            "Change_Pct": calc_change(df_macro, 'M2', curr_date, prev_date),
            "Display": f"${df_macro['M2'].iloc[-1]/1000:.1f}T"
        },
        {
            "Name": "🖨️ 美联储资产", "Category": "Source (水源)", "Size": df_macro['Fed_Assets'].iloc[-1],
            "Change_Pct": calc_change(df_macro, 'Fed_Assets', curr_date, prev_date),
            "Display": f"${df_macro['Fed_Assets'].iloc[-1]/1000:.1f}T"
        },
        {
            "Name": "🏦 净流动性", "Category": "Source (水源)", "Size": df_macro['Net_Liquidity'].iloc[-1],
            "Change_Pct": calc_change(df_macro, 'Net_Liquidity', curr_date, prev_date),
            "Display": f"${df_macro['Net_Liquidity'].iloc[-1]/1000:.1f}T"
        },
        # Valve
        {
            "Name": "👜 财政部 TGA", "Category": "Valve (调节阀)", "Size": df_macro['TGA'].iloc[-1],
            "Change_Pct": calc_change(df_macro, 'TGA', curr_date, prev_date),
            "Display": f"${df_macro['TGA'].iloc[-1]:.0f}B"
        },
        {
            "Name": "♻️ 逆回购 RRP", "Category": "Valve (调节阀)", "Size": df_macro['RRP'].iloc[-1],
            "Change_Pct": calc_change(df_macro, 'RRP', curr_date, prev_date),
            "Display": f"${df_macro['RRP'].iloc[-1]:.0f}B"
        },
        # Assets (Size 估算值)
        {
            "Name": "🇺🇸 美国股市", "Category": "Asset (资产池)", "Size": 55000,
            "Change_Pct": calc_change(df_assets, 'SPY', curr_date, prev_date), "Display": "~$55T"
        },
        {
            "Name": "📜 美国债市", "Category": "Asset (资产池)", "Size": 52000,
            "Change_Pct": calc_change(df_assets, 'TLT', curr_date, prev_date), "Display": "~$52T"
        },
        {
            "Name": "🥇 黄金市场", "Category": "Asset (资产池)", "Size": 14000,
            "Change_Pct": calc_change(df_assets, 'GLD', curr_date, prev_date), "Display": "~$14T"
        },
        {
            "Name": "₿ 加密货币", "Category": "Asset (资产池)", "Size": 2500,
            "Change_Pct": calc_change(df_assets, 'BTC-USD', curr_date, prev_date), "Display": "~$2.5T"
        }
    ]
    
    # --- 3. 绘制 Treemap ---
    df_tree = pd.DataFrame(treemap_data)
    
    fig_tree = px.treemap(
        df_tree,
        path=[px.Constant("全球资金全景"), 'Category', 'Name'],
        values='Size',
        color='Change_Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
        color_continuous_midpoint=0,
        range_color=[-5, 5],
        hover_data=['Display', 'Change_Pct']
    )
    fig_tree.update_traces(
        textinfo="label+text+value",
        texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>30天: %{color:.2f}%",
        textfont=dict(size=14)
    )
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=500)
    
    st.plotly_chart(fig_tree, use_container_width=True)

    # --- 4. 绘制历史趋势对比图 (Line Chart) ---
    st.markdown("### 🌊 资金 vs 资产：谁在领跑？(1 Year Trends)")
    st.caption("所有指标均归一化为百分比涨跌幅 (Rebased to 0%)，以观察相关性与背离。")
    
    # 合并数据
    df_chart = pd.DataFrame(index=df_macro.index)
    df_chart['🏦 净流动性 (Net Liq)'] = df_macro['Net_Liquidity']
    df_chart['🖨️ 美联储资产'] = df_macro['Fed_Assets']
    
    # 映射资产数据到同一张表
    for ticker_code, name in asset_map.items():
        if ticker_code in df_assets.columns:
            # 使用 asof 对齐数据，防止索引微小差异
            df_chart[name] = df_assets[ticker_code].asof(df_chart.index)
            
    # 截取最近1年
    one_year_ago = df_chart.index[-1] - timedelta(days=365)
    df_chart = df_chart[df_chart.index >= one_year_ago]
    
    # 归一化处理 (Normalize)
    # 确保第一行不为 NaN 或 0
    df_chart = df_chart.fillna(method='bfill').fillna(method='ffill')
    df_norm = df_chart.apply(lambda x: (x / x.iloc[0] - 1) * 100 if x.iloc[0] != 0 else 0)
    
    # 绘图
    fig_line = go.Figure()
    
    # 1. 核心资金线 (加粗/虚线)
    fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['🏦 净流动性 (Net Liq)'], 
                                  name='🏦 净流动性 (燃料)', line=dict(color='#00FF00', width=4, dash='dot')))
    
    # 2. 核心资产线
    fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['🇺🇸 美股 (SPY)'], 
                                  name='🇺🇸 美股', line=dict(color='#FF4B4B', width=2)))
    fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['₿ 比特币 (BTC)'], 
                                  name='₿ 比特币', line=dict(color='orange', width=2)))
    fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['🥇 黄金 (GLD)'], 
                                  name='🥇 黄金', line=dict(color='gold', width=2)))
    fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['📜 美债 (TLT)'], 
                                  name='📜 美债', line=dict(color='cornflowerblue', width=2)))

    fig_line.update_layout(
        template="plotly_dark",
        height=500,
        hovermode="x unified",
        yaxis_title="累计涨跌幅 (%)",
        legend=dict(orientation="h", y=1.1)
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
    
    # --- 5. 宏观对冲观察 ---
    st.info("""
    💡 **如何观察背离 (Divergence):**
    * **✅ 健康牛市:** 绿色虚线 (净流动性) 向上，红色线 (美股) 也向上。说明有真金白银在推。
    * **⚠️ 危险信号:** 绿色虚线 **向下** (央行在抽水)，但红色线还在 **拼命向上**。这就是典型的“流动性背离”，通常预示着崩盘风险。
    """)

else:
    st.info("⏳ 正在拉取全球宏观数据，首次加载可能需要10秒...")
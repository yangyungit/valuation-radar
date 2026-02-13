import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("状态：已启用强制时区对齐 | 逻辑：全数据并轨处理")

# --- 1. 坦克级数据引擎 (Robust Data Engine) ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=400)
    
    # === A. 获取宏观数据 (FRED) ===
    # 就算获取失败，也先创建一个空表，防止崩溃
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        # 强制清洗：日频 + 填充
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # === B. 获取资产数据 (Yahoo) ===
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

    # === C. 核心修复：时区大清洗 (Timezone Stripping) ===
    # 不管有没有时区，统统去掉，变成纯净的日期
    if not df_macro.empty and df_macro.index.tz is not None:
        df_macro.index = df_macro.index.tz_localize(None)
        
    if not df_assets.empty and df_assets.index.tz is not None:
        df_assets.index = df_assets.index.tz_localize(None)

    # === D. 数据熔炉 (Merge) ===
    # 把两张表强行拼在一起，按日期对齐
    df_all = pd.concat([df_macro, df_assets], axis=1)
    df_all = df_all.sort_index().ffill().dropna(how='all') # 排序、填充、去全空行
    
    # === E. 计算衍生指标 ===
    if not df_all.empty:
        # 单位换算 Billion
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        
        # 净流动性公式
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all, tickers

# --- 2. 页面逻辑 ---
df, asset_map = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # 获取最新一天和30天前的数据 (使用 index 查找，绝对安全)
    curr_date = df.index[-1]
    prev_date = curr_date - timedelta(days=30)
    
    # 如果找不到确切的30天前，就找这张表里离那天最近的一天
    # get_indexer with method='nearest' 是处理日期的神器
    try:
        prev_idx_loc = df.index.get_indexer([prev_date], method='nearest')[0]
        prev_valid_date = df.index[prev_idx_loc]
    except:
        prev_valid_date = df.index[0]

    # 通用计算函数
    def get_change(col):
        if col not in df.columns: return 0
        v_curr = df.loc[curr_date, col]
        v_prev = df.loc[prev_valid_date, col]
        if pd.isna(v_prev) or v_prev == 0: return 0
        return (v_curr - v_prev) / v_prev * 100

    def get_val(col):
        if col not in df.columns: return 0
        return df.loc[curr_date, col]

    # === Treemap 数据构建 ===
    treemap_data = [
        # Source
        {"Name": "💰 M2 货币供应", "Cat": "Source", "Size": 22300, "Pct": get_change('M2'), "Txt": f"${get_val('M2')/1000:.1f}T"},
        {"Name": "🖨️ 美联储资产", "Cat": "Source", "Size": get_val('Fed_Assets'), "Pct": get_change('Fed_Assets'), "Txt": f"${get_val('Fed_Assets')/1000:.1f}T"},
        {"Name": "🏦 净流动性", "Cat": "Source", "Size": get_val('Net_Liquidity'), "Pct": get_change('Net_Liquidity'), "Txt": f"${get_val('Net_Liquidity')/1000:.1f}T"},
        # Valve
        {"Name": "👜 财政部 TGA", "Cat": "Valve", "Size": get_val('TGA'), "Pct": get_change('TGA'), "Txt": f"${get_val('TGA'):.0f}B"},
        {"Name": "♻️ 逆回购 RRP", "Cat": "Valve", "Size": get_val('RRP'), "Pct": get_change('RRP'), "Txt": f"${get_val('RRP'):.0f}B"},
        # Assets (Size为估值, Pct为真实)
        {"Name": "🇺🇸 美股", "Cat": "Asset", "Size": 55000, "Pct": get_change('SPY'), "Txt": "~$55T"},
        {"Name": "📜 美债", "Cat": "Asset", "Size": 52000, "Pct": get_change('TLT'), "Txt": "~$52T"},
        {"Name": "🥇 黄金", "Cat": "Asset", "Size": 14000, "Pct": get_change('GLD'), "Txt": "~$14T"},
        {"Name": "₿ 比特币", "Cat": "Asset", "Size": 2500, "Pct": get_change('BTC-USD'), "Txt": "~$2.5T"}
    ]
    
    # 绘制 Treemap
    df_tree = pd.DataFrame(treemap_data)
    fig_tree = px.treemap(
        df_tree, path=[px.Constant("全景资金池"), 'Cat', 'Name'], values='Size', color='Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'], range_color=[-5, 5],
        hover_data=['Txt', 'Pct']
    )
    fig_tree.update_traces(texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>30d: %{color:.2f}%", textfont=dict(size=15))
    fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=500)
    st.plotly_chart(fig_tree, use_container_width=True)

    # === 历史趋势图 (Line Chart) ===
    st.markdown("### 🌊 1年期趋势对比 (Normalized)")
    
    # 截取过去1年
    df_chart = df.loc[df.index >= (curr_date - timedelta(days=365))].copy()
    
    # 归一化 (从0开始)
    df_norm = pd.DataFrame()
    
    # 1. 核心资金线
    if 'Net_Liquidity' in df_chart.columns:
        start_val = df_chart['Net_Liquidity'].iloc[0]
        if start_val != 0:
            df_norm['🏦 净流动性'] = (df_chart['Net_Liquidity'] / start_val - 1) * 100
            
    # 2. 核心资产线
    target_assets = ['SPY', 'BTC-USD', 'GLD', 'TLT']
    for t in target_assets:
        if t in df_chart.columns:
            start_val = df_chart[t].iloc[0]
            if start_val != 0:
                name = asset_map.get(t, t)
                df_norm[name] = (df_chart[t] / start_val - 1) * 100
                
    # 绘图
    if not df_norm.empty:
        fig_line = go.Figure()
        
        # 资金线 (绿色虚线)
        if '🏦 净流动性' in df_norm.columns:
            fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm['🏦 净流动性'], name='🏦 净流动性', line=dict(color='#00FF00', width=4, dash='dot')))
            
        # 资产线
        colors = {'🇺🇸 美股 (SPY)': '#FF4B4B', '₿ 比特币 (BTC)': 'orange', '🥇 黄金 (GLD)': 'gold', '📜 美债 (TLT)': '#4488EE'}
        for col in df_norm.columns:
            if col != '🏦 净流动性':
                c = colors.get(col, 'grey')
                fig_line.add_trace(go.Scatter(x=df_norm.index, y=df_norm[col], name=col, line=dict(color=c, width=2)))
                
        fig_line.update_layout(template="plotly_dark", height=500, hovermode="x unified", yaxis_title="累计涨跌幅 (%)", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_line, use_container_width=True)

else:
    st.warning("⏳ 正在建立数据连接... 如果长时间无反应，可能是 FRED 接口暂时拥堵，请稍后再试。")
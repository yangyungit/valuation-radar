import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("逻辑修正: 方块大小代表【总市值/规模】，颜色代表【30天资金流向】 | 单位: Billions (十亿美元)")

# --- 1. 宏观数据引擎 (FRED) ---
@st.cache_data(ttl=3600*12)
def get_macro_data():
    start_date = datetime.now() - timedelta(days=730) 
    end_date = datetime.now()
    
    # FRED Code
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
    
    try:
        df = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df = df.resample('D').ffill().dropna()
        
        # 统一单位: Billions
        df['Fed_Assets'] = df['WALCL'] / 1000   
        df['TGA'] = df['WTREGEN'] / 1000        
        df['RRP'] = df['RRPONTSYD']             
        df['M2'] = df['M2SL']                   
        
        df['Net_Liquidity'] = df['Fed_Assets'] - df['TGA'] - df['RRP']
        return df
    except:
        return pd.DataFrame()

# --- 2. 资产数据引擎 (YFinance + 市值估算) ---
@st.cache_data(ttl=3600)
def get_asset_changes():
    # 这里我们只取 ETF 的涨跌幅作为"体温计"
    # 但方块的大小 (Size) 我们将手动赋予"真实宏观规模"
    tickers = {
        "SPY": "美股 (S&P 500 Proxy)",
        "TLT": "美债 (Treasury Proxy)",
        "GLD": "黄金 (Gold Proxy)",
        "BTC-USD": "比特币 (Crypto)",
        "USO": "原油 (Oil)",
        "BIL": "现金 (Cash)"
    }
    
    try:
        data = yf.download(list(tickers.keys()), period="3mo", progress=False)['Close']
        changes = {}
        
        for ticker in tickers:
            if ticker in data.columns:
                series = data[ticker].dropna()
                if len(series) < 5: 
                    changes[ticker] = 0
                    continue
                
                latest = series.iloc[-1]
                # 强行找30天前，找不到就找最接近的
                try:
                    target = series.index[-1] - timedelta(days=30)
                    idx = series.index.searchsorted(target)
                    idx = max(0, min(idx, len(series)-1))
                    prev = series.iloc[idx]
                except:
                    prev = series.iloc[0]
                    
                if prev == 0: changes[ticker] = 0
                else: changes[ticker] = (latest - prev) / prev * 100
                
        return changes
    except:
        return {}

# --- 3. 构建真实比例模型 ---
df_macro = get_macro_data()
asset_changes = get_asset_changes()

if not df_macro.empty:
    curr = df_macro.iloc[-1]
    
    # 计算宏观指标变动 %
    def get_macro_pct(col):
        try:
            target = df_macro.index[-1] - timedelta(days=30)
            idx = df_macro.index.searchsorted(target)
            idx = max(0, min(idx, len(df_macro)-1))
            prev = df_macro.iloc[idx][col]
            if prev == 0: return 0
            return (curr[col] - prev) / prev * 100
        except: return 0

    # === 核心修正：手动定义各大池子的"真实规模" (Market Cap Estimates) ===
    # 单位: Billions (十亿美元)
    # 这些数字是根据 2024-2025 的宏观概算，确保视觉比例正确
    
    treemap_data = [
        # --- 源头 (Source) ---
        {
            "Name": "💰 M2 货币供应", "Category": "Source (水源)",
            "Size": curr['M2'],  # 实时数据 (~21,000B)
            "Change_Pct": get_macro_pct('M2'),
            "Label_Val": f"${curr['M2']/1000:.1f}T" # 显示为 Trillion
        },
        {
            "Name": "🖨️ 美联储资产", "Category": "Source (水源)",
            "Size": curr['Fed_Assets'], # 实时数据 (~7,000B)
            "Change_Pct": get_macro_pct('Fed_Assets'),
            "Label_Val": f"${curr['Fed_Assets']/1000:.1f}T"
        },
        {
            "Name": "🏦 净流动性", "Category": "Source (水源)",
            "Size": curr['Net_Liquidity'], # 实时数据
            "Change_Pct": get_macro_pct('Net_Liquidity'),
            "Label_Val": f"${curr['Net_Liquidity']/1000:.1f}T"
        },

        # --- 调节阀 (Valves) ---
        {
            "Name": "👜 财政部 TGA", "Category": "Valve (调节阀)",
            "Size": curr['TGA'], 
            "Change_Pct": get_macro_pct('TGA'),
            "Label_Val": f"${curr['TGA']:.0f}B"
        },
        {
            "Name": "♻️ 逆回购 RRP", "Category": "Valve (调节阀)",
            "Size": curr['RRP'], 
            "Change_Pct": get_macro_pct('RRP'),
            "Label_Val": f"${curr['RRP']:.0f}B"
        },

        # --- 资产池 (Market Cap Estimates) ---
        # 这里我们用固定的"宏观估值"作为Size，用ETF涨跌幅作为Color
        {
            "Name": "🇺🇸 美国股市", "Category": "Asset (资产池)",
            "Size": 55000, # 估算 $55 Trillion (视觉上应该是Fed的8倍)
            "Change_Pct": asset_changes.get('SPY', 0),
            "Label_Val": "~$55.0T"
        },
        {
            "Name": "📜 美国债市", "Category": "Asset (资产池)",
            "Size": 52000, # 估算 $52 Trillion
            "Change_Pct": asset_changes.get('TLT', 0), # 用TLT代表债市方向
            "Label_Val": "~$52.0T"
        },
        {
            "Name": "🥇 黄金市场", "Category": "Asset (资产池)",
            "Size": 14000, # 估算 $14 Trillion
            "Change_Pct": asset_changes.get('GLD', 0),
            "Label_Val": "~$14.0T"
        },
        {
            "Name": "₿ 加密货币", "Category": "Asset (资产池)",
            "Size": 2500,  # 估算 $2.5 Trillion
            "Change_Pct": asset_changes.get('BTC-USD', 0),
            "Label_Val": "~$2.5T"
        }
    ]
    
    df_tree = pd.DataFrame(treemap_data)

    # --- 绘制图表 ---
    fig = px.treemap(
        df_tree,
        path=[px.Constant("全球资金全景"), 'Category', 'Name'],
        values='Size', # 现在 Size 代表真实的万亿级市值
        color='Change_Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
        color_continuous_midpoint=0,
        range_color=[-5, 5],
        hover_data=['Label_Val', 'Change_Pct'],
    )
    
    fig.update_traces(
        textinfo="label+text+value",
        texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>30天: %{color:.2f}%",
        textfont=dict(size=14)
    )
    fig.update_layout(height=700, margin=dict(t=20, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("""
    ---
    ### 📊 比例说明 (Scale)
    * **方块大小 (Area):** 代表该资产类别的**总市值 (Market Cap)**。
        * 你会发现 **股市** 和 **债市** 的方块非常巨大（约 $50T+），而 **美联储资产** 相对较小（$7T）。这才是真实的金融世界比例。
    * **颜色 (Color):** 代表该资产近期 (30天) 的**资金流向**。
    * **数据源:** 宏观数据来自 FRED，资产涨跌幅代理自 Yahoo Finance。
    """)
    
else:
    st.info("⏳ 正在获取 FRED 数据，请稍候...")
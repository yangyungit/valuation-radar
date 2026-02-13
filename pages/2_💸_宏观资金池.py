import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("数据来源: Federal Reserve (FRED) & Yahoo Finance | 实时更新")

# --- 1. 核心引擎：从 FRED 获取宏观“水源”数据 ---
@st.cache_data(ttl=3600*12)
def get_macro_data():
    start_date = datetime.now() - timedelta(days=400) 
    end_date = datetime.now()

    # FRED 代码
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD']
    
    try:
        df = web.DataReader(macro_codes, 'fred', start_date, end_date)
        
        # 关键修正：重采样为日频 (Daily) 并填充空值 (Forward Fill)
        # 这样能保证每一天都有数，不会出现 NaN
        df = df.resample('D').ffill().dropna()
        
        # 单位换算：全部统一为 Billion (十亿)
        # WALCL 原单位是 Million -> /1000
        # WTREGEN, RRP 原单位是 Billion -> 不动
        df['Fed_Assets'] = df['WALCL'] / 1000
        df['TGA'] = df['WTREGEN'] 
        df['RRP'] = df['RRPONTSYD']
        
        # 核心公式：净流动性 = 央行资产 - TGA(政府存款) - RRP(逆回购)
        df['Net_Liquidity'] = df['Fed_Assets'] - df['TGA'] - df['RRP']
        
        return df
    except Exception as e:
        st.error(f"连接美联储数据库失败: {e}")
        return pd.DataFrame()

# --- 2. 市场引擎：从 YFinance 获取资产“蓄水池” ---
@st.cache_data(ttl=3600)
def get_asset_data():
    assets = {
        "🇺🇸 美股 (S&P 500)": "SPY",
        "🇺🇸 美债 (20Y Treasury)": "TLT",
        "🥇 黄金 (Gold)": "GLD",
        "₿ 比特币 (Bitcoin)": "BTC-USD",
        "🛢️ 原油 (Oil)": "USO",
        "💵 美元现金 (Cash)": "BIL" 
    }
    
    tickers = list(assets.values())
    try:
        data = yf.download(tickers, period="2mo", progress=False)['Close']
        
        records = []
        for name, ticker in assets.items():
            if ticker in data.columns:
                series = data[ticker].dropna()
                if len(series) < 2: continue
                
                latest = series.iloc[-1]
                # 找 30 天前的数据（或者最近的一个）
                lookback_idx = max(0, len(series) - 22) # 约一个月交易日
                prev = series.iloc[lookback_idx] 
                
                change_pct = (latest - prev) / prev * 100
                
                # 视觉权重 (为了图表好看，手动设定的大小)
                if "SPY" in ticker: size = 4000
                elif "TLT" in ticker: size = 4500
                elif "BIL" in ticker: size = 1000
                elif "GLD" in ticker: size = 800
                elif "BTC" in ticker: size = 300
                else: size = 200
                
                records.append({
                    "Name": name,
                    "Type": "Asset Class (资产池)",
                    "Value": latest,
                    "Display_Value": f"${latest:.2f}",
                    "Change_Pct": change_pct,
                    "Size": size
                })
        return pd.DataFrame(records)
    except:
        return pd.DataFrame()

# --- 3. 数据融合与可视化 ---
df_macro = get_macro_data()
df_assets = get_asset_data()

if not df_macro.empty and not df_assets.empty:
    
    # --- A. 处理宏观数据 (计算月度变化) ---
    curr = df_macro.iloc[-1]
    # 往回找 30 天
    try:
        target_date = df_macro.index[-1] - timedelta(days=30)
        idx = df_macro.index.searchsorted(target_date)
        prev = df_macro.iloc[idx]
    except:
        prev = df_macro.iloc[0]

    def get_change(col):
        if prev[col] == 0: return 0
        return (curr[col] - prev[col]) / prev[col] * 100

    # 构建宏观数据块
    macro_blocks = [
        {
            "Name": "🏦 净流动性 (Net Liquidity)", 
            "Type": "Source (水源)",
            "Value": curr['Net_Liquidity'],
            "Display_Value": f"${curr['Net_Liquidity']:.0f}B",
            "Change_Pct": get_change('Net_Liquidity'),
            "Size": 6000
        },
        {
            "Name": "🖨️ 美联储资产 (Fed Assets)", 
            "Type": "Source (水源)",
            "Value": curr['Fed_Assets'],
            "Display_Value": f"${curr['Fed_Assets']:.0f}B",
            "Change_Pct": get_change('Fed_Assets'),
            "Size": 7500
        },
        {
            "Name": "👜 财政部TGA (Government)", 
            "Type": "Valve (调节阀)",
            "Value": curr['TGA'],
            "Display_Value": f"${curr['TGA']:.0f}B",
            "Change_Pct": get_change('TGA'),
            "Size": 1500
        },
        {
            "Name": "♻️ 逆回购RRP (Parking)", 
            "Type": "Valve (调节阀)",
            "Value": curr['RRP'],
            "Display_Value": f"${curr['RRP']:.0f}B",
            "Change_Pct": get_change('RRP'),
            "Size": 1500
        }
    ]
    
    df_all = pd.concat([pd.DataFrame(macro_blocks), df_assets], ignore_index=True)
    
    # --- B. 绘制 Treemap ---
    fig = px.treemap(
        df_all,
        path=[px.Constant("全球资金全景"), 'Type', 'Name'],
        values='Size',
        color='Change_Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'], # 红-深灰-绿
        color_continuous_midpoint=0,
        range_color=[-5, 5],
        hover_data=['Display_Value', 'Change_Pct'],
    )
    
    fig.update_traces(
        textinfo="label+value+percent entry",
        texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>月变动: %{color:.2f}%",
        textfont=dict(size=14)
    )
    fig.update_layout(height=600, margin=dict(t=0, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
    
    # --- C. 核心解释 (Cheat Sheet) ---
    st.markdown("---")
    st.subheader("📖 宏观指标速查 (The Playbook)")
    
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.info("🖨️ **美联储资产 (Fed Assets)**")
        st.markdown("""
        * **含义:** 央行印了多少钱。
        * **绿色 (涨):** 央行扩表/放水 → **利好**
        * **红色 (跌):** 央行缩表/收水 → **利空**
        """)
        
    with c2:
        st.warning("👜 **财政部账户 (TGA)**")
        st.markdown("""
        * **含义:** 财政部的支付宝余额。
        * **绿色 (涨):** 政府把钱存起来不花 → **抽水 (利空)**
        * **红色 (跌):** 政府花钱/发福利 → **放水 (利好)**
        """)

    with c3:
        st.warning("♻️ **逆回购 (RRP)**")
        st.markdown("""
        * **含义:** 机构觉得外面风险大，把钱存回美联储。
        * **绿色 (涨):** 资金回流央行闲置 → **抽水 (利空)**
        * **红色 (跌):** 资金从央行流出买资产 → **放水 (利好)**
        """)

    with c4:
        st.success("🏦 **净流动性 (Net Liquidity)**")
        st.markdown("""
        * **含义:** **真正流向市场的钱**。
        * **公式:** `Fed资产 - TGA - RRP`
        * **绿色 (涨):** 市场钱变多了 → **资产大涨**
        * **红色 (跌):** 市场钱变少了 → **资产回调**
        """)

else:
    st.info("⏳ 正在校准美联储数据，请稍候...")
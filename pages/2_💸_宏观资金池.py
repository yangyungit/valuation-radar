import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("数据源: Federal Reserve (FRED) & Yahoo Finance | 修正版: 单位统一为 Billion")

# --- 1. 核心引擎：从 FRED 获取宏观数据 (已修复单位问题) ---
@st.cache_data(ttl=3600*12)
def get_macro_data():
    # 拉取 2 年数据，确保一定能找到同比数据
    start_date = datetime.now() - timedelta(days=730) 
    end_date = datetime.now()

    # FRED 代码
    # WALCL: 美联储总资产 (Millions)
    # WTREGEN: 财政部 TGA 账户 (Millions) -> 注意：这也是 Millions
    # RRPONTSYD: 隔夜逆回购 (Billions) -> 注意：这是 Billions
    # M2SL: M2 广义货币 (Billions, 月更)
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
    
    try:
        df = web.DataReader(macro_codes, 'fred', start_date, end_date)
        
        # 1. 强力填充：先用前值填补空缺，再丢弃开头没数的行
        df = df.resample('D').ffill().dropna()
        
        # 2. 单位统一修正 (全部转为 Billions 十亿)
        df['Fed_Assets'] = df['WALCL'] / 1000    # Million -> Billion
        df['TGA'] = df['WTREGEN'] / 1000         # Million -> Billion (之前这里漏了除以1000)
        df['RRP'] = df['RRPONTSYD']              # 已经是 Billion
        df['M2'] = df['M2SL']                    # 已经是 Billion
        
        # 3. 计算净流动性 (Net Liquidity)
        # 公式: 央行总资产 - TGA - RRP
        df['Net_Liquidity'] = df['Fed_Assets'] - df['TGA'] - df['RRP']
        
        return df
    except Exception as e:
        st.error(f"连接美联储数据库失败: {e}")
        return pd.DataFrame()

# --- 2. 市场引擎：从 YFinance 获取资产数据 ---
@st.cache_data(ttl=3600)
def get_asset_data():
    assets = {
        "🇺🇸 美股 (SPY)": "SPY",
        "🇺🇸 美债 (TLT)": "TLT",
        "🥇 黄金 (GLD)": "GLD",
        "₿ 比特币 (BTC)": "BTC-USD",
        "🛢️ 原油 (USO)": "USO"
    }
    
    tickers = list(assets.values())
    try:
        # 下载 6 个月数据
        data = yf.download(tickers, period="6mo", progress=False)['Close']
        
        records = []
        for name, ticker in assets.items():
            if ticker in data.columns:
                series = data[ticker].dropna()
                if len(series) < 30: continue
                
                latest = series.iloc[-1]
                
                # 寻找 30 天前的价格
                try:
                    target_date = series.index[-1] - timedelta(days=30)
                    idx = series.index.searchsorted(target_date)
                    # 防止索引越界
                    idx = max(0, min(idx, len(series)-1))
                    prev = series.iloc[idx]
                except:
                    prev = series.iloc[0]
                
                change_pct = (latest - prev) / prev * 100
                
                # 视觉权重 (为了图表美观设定的虚拟大小)
                if "SPY" in ticker: size = 4000
                elif "TLT" in ticker: size = 4500
                elif "GLD" in ticker: size = 800
                elif "BTC" in ticker: size = 300
                else: size = 200
                
                records.append({
                    "Name": name,
                    "Type": "Asset Class (资产)",
                    "Value": latest,
                    "Display_Value": f"${latest:.2f}",
                    "Change_Pct": change_pct,
                    "Size": size
                })
        return pd.DataFrame(records)
    except:
        return pd.DataFrame()

# --- 3. 页面渲染 ---
df_macro = get_macro_data()
df_assets = get_asset_data()

if not df_macro.empty and not df_assets.empty:
    
    # --- 计算宏观数据的 30 天变化 ---
    curr = df_macro.iloc[-1]
    
    # 找 30 天前
    try:
        target_date = df_macro.index[-1] - timedelta(days=30)
        idx = df_macro.index.searchsorted(target_date)
        idx = max(0, min(idx, len(df_macro)-1))
        prev = df_macro.iloc[idx]
    except:
        prev = df_macro.iloc[0]

    def get_pct_change(col):
        if prev[col] == 0: return 0
        return (curr[col] - prev[col]) / prev[col] * 100
    
    # 构建 Treemap 数据 (加入 M2)
    macro_blocks = [
        {
            "Name": "🏦 净流动性 (Net Liquidity)", 
            "Type": "Source (水源)",
            "Value": curr['Net_Liquidity'],
            "Display_Value": f"${curr['Net_Liquidity']:.0f}B",
            "Change_Pct": get_pct_change('Net_Liquidity'),
            "Size": 6000
        },
        {
            "Name": "🖨️ 美联储资产 (Fed Assets)", 
            "Type": "Source (水源)",
            "Value": curr['Fed_Assets'],
            "Display_Value": f"${curr['Fed_Assets']:.0f}B",
            "Change_Pct": get_pct_change('Fed_Assets'),
            "Size": 5000
        },
        {
            "Name": "💰 M2 货币供应 (Money Supply)", 
            "Type": "Source (水源)",
            "Value": curr['M2'],
            "Display_Value": f"${curr['M2']:.0f}B",
            "Change_Pct": get_pct_change('M2'),
            "Size": 4000
        },
        {
            "Name": "👜 财政部 TGA (Gov)", 
            "Type": "Valve (调节阀)",
            "Value": curr['TGA'],
            "Display_Value": f"${curr['TGA']:.0f}B",
            "Change_Pct": get_pct_change('TGA'),
            "Size": 1500
        },
        {
            "Name": "♻️ 逆回购 RRP (Parking)", 
            "Type": "Valve (调节阀)",
            "Value": curr['RRP'],
            "Display_Value": f"${curr['RRP']:.0f}B",
            "Change_Pct": get_pct_change('RRP'),
            "Size": 1500
        }
    ]
    
    df_all = pd.concat([pd.DataFrame(macro_blocks), df_assets], ignore_index=True)
    
    # 绘制 Treemap
    fig = px.treemap(
        df_all,
        path=[px.Constant("全球资金全景"), 'Type', 'Name'],
        values='Size',
        color='Change_Pct',
        color_continuous_scale=['#FF4B4B', '#262730', '#09AB3B'],
        color_continuous_midpoint=0,
        range_color=[-5, 5],
        hover_data=['Display_Value', 'Change_Pct'],
    )
    
    fig.update_traces(
        textinfo="label+value+percent entry",
        texttemplate="<b>%{label}</b><br>%{customdata[0]}<br>30天变动: %{color:.2f}%",
        textfont=dict(size=14)
    )
    fig.update_layout(height=650, margin=dict(t=0, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # --- 底部：深度宏观解释 (Cheat Sheet) ---
    st.markdown("---")
    st.subheader("🧐 宏观机制硬核解读")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 1. 钱从哪来？(水源)")
        st.info(f"""
        * **美联储资产 (Fed Assets):** 印钞机的总开关。
        * **M2 货币供应:** 老百姓和企业的存款总和。(虽然大，但流动性较慢)
        * **🏦 净流动性 (Net Liquidity):** **金融市场的“高能燃油”**。
            * 公式 = Fed资产 - TGA - RRP。
            * 它是银行系统真正可以用来加杠杆、买股票的闲钱。
            * **与美股关系:** 极度正相关。净流动性涨，标普500通常会涨。
        """)

    with c2:
        st.markdown("### 2. 钱去哪了？(调节)")
        st.warning(f"""
        * **👜 财政部 TGA (政府金库):** * 如果它**变红 (下跌)**：说明政府在花钱，资金流入市场 -> **利好**。
            * 如果它**变绿 (上涨)**：说明政府在收税/发债存钱，资金被抽走 -> **利空**。
        * **♻️ 逆回购 RRP (资金避风港):**
            * 如果它**变红 (下跌)**：说明钱不愿意躺平了，流出来买资产 -> **利好**。
            * 如果它**变绿 (上涨)**：说明市场风险大，钱都躲回美联储了 -> **利空**。
        """)
        
else:
    st.info("⏳ 正在重新连接美联储 (FRED) 获取最新数据，请稍候...")
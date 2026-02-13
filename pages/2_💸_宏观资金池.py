import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性传导 (Global Liquidity Transmission)")
st.markdown("""
> **"Follow the Money"** —— 真正的宏观数据源。
> * **源头 (Source):** 直接接入 FRED (美联储) 数据库，监控印钞机水位。
> * **去向 (Destination):** 接入实时市场数据，监控资产价格变动。
""")

# --- 1. 核心引擎：从 FRED 获取宏观“水源”数据 ---
@st.cache_data(ttl=3600*12)
def get_macro_data():
    start_date = datetime.now() - timedelta(days=365) # 拉取1年数据
    end_date = datetime.now()

    # FRED 代码对照表
    # WALCL: 美联储总资产 (周更)
    # WTREGEN: 财政部TGA账户 (周更) - 政府存的钱
    # RRPONTSYD: 隔夜逆回购 (日更) - 市场闲置回流的钱
    # M2SL: M2广义货币供应 (月更)
    
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
    
    try:
        # 使用 pandas_datareader 直接从 FRED 抓取
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        
        # 数据清洗：因为不同数据更新频率不同（日/周/月），我们需要对齐
        df_macro = df_macro.ffill().dropna() # 向前填充
        
        # 计算“净流动性” (Net Liquidity)
        # 单位换算：FRED数据通常是 Million (百万) 或 Billion (十亿)
        # WALCL(百万), WTREGEN(十亿->转换), RRP(十亿->转换)
        # 统一转换为 "Billion (十亿)"
        
        df_macro['Fed_Assets_B'] = df_macro['WALCL'] / 1000
        df_macro['TGA_B'] = df_macro['WTREGEN'] 
        df_macro['RRP_B'] = df_macro['RRPONTSYD']
        
        # 核心公式：净流动性 = 央行资产 - TGA(抽水) - RRP(回收)
        df_macro['Net_Liquidity'] = df_macro['Fed_Assets_B'] - df_macro['TGA_B'] - df_macro['RRP_B']
        
        return df_macro
    except Exception as e:
        st.error(f"连接美联储数据库失败: {e}")
        return pd.DataFrame()

# --- 2. 市场引擎：从 YFinance 获取资产“蓄水池” ---
@st.cache_data(ttl=3600)
def get_asset_data():
    # 这里我们用核心ETF代表各大类资产
    assets = {
        "🇺🇸 美股 (S&P 500)": "SPY",
        "🇺🇸 美债 (20Y Treasury)": "TLT",
        "🥇 黄金 (Gold)": "GLD",
        "₿ 比特币 (Bitcoin)": "BTC-USD",
        "🛢️ 原油 (Oil)": "USO",
        "💵 美元现金 (Cash)": "BIL" 
    }
    
    tickers = list(assets.values())
    data = yf.download(tickers, period="1mo", progress=False)['Close']
    
    records = []
    for name, ticker in assets.items():
        if ticker in data.columns:
            series = data[ticker].dropna()
            if len(series) < 2: continue
            
            latest = series.iloc[-1]
            prev = series.iloc[0] # 1个月前的价格
            change_pct = (latest - prev) / prev * 100
            
            # 预估池子大小 (Size) - 为了图表比例好看，我们手动设定这一层的权重
            # 真实世界比例：债 > 股 > 黄金 > 币
            # 这里我们用“视觉权重”
            if "SPY" in ticker: size = 4000
            elif "TLT" in ticker: size = 4500
            elif "BIL" in ticker: size = 1000
            elif "GLD" in ticker: size = 800
            elif "BTC" in ticker: size = 300
            else: size = 200
            
            records.append({
                "Name": name,
                "Type": "Asset Class",
                "Value": round(latest, 2),
                "Change_Pct": round(change_pct, 2),
                "Size": size
            })
            
    return pd.DataFrame(records)

# --- 3. 数据融合与可视化 ---
df_macro = get_macro_data()
df_assets = get_asset_data()

if not df_macro.empty and not df_assets.empty:
    
    # --- A. 处理宏观数据 ---
    latest_macro = df_macro.iloc[-1]
    prev_macro = df_macro.iloc[-20] # 约1个月前
    
    # 计算宏观变化率
    def calc_macro_change(col):
        return (latest_macro[col] - prev_macro[col]) / prev_macro[col] * 100

    # 构建宏观数据块
    macro_blocks = [
        {
            "Name": "🏦 净流动性 (Net Liquidity)", 
            "Type": "Source (水源)",
            "Value": f"${latest_macro['Net_Liquidity']:.0f}B",
            "Change_Pct": calc_macro_change('Net_Liquidity'),
            "Size": 6000 # 权重最大，因为它是源头
        },
        {
            "Name": "🖨️ 美联储资产 (Fed Assets)", 
            "Type": "Source (水源)",
            "Value": f"${latest_macro['Fed_Assets_B']:.0f}B",
            "Change_Pct": calc_macro_change('Fed_Assets_B'),
            "Size": 7500
        },
        {
            "Name": "👜 财政部账户 (TGA)", 
            "Type": "Valve (调节阀)",
            "Value": f"${latest_macro['TGA_B']:.0f}B",
            # 注意：TGA 变大其实是抽水（坏事），但在图上我们还是按数值增减显示颜色
            # 并在Tooltip里解释
            "Change_Pct": calc_macro_change('TGA_B'),
            "Size": 1500
        },
        {
            "Name": "♻️ 逆回购 (RRP)", 
            "Type": "Valve (调节阀)",
            "Value": f"${latest_macro['RRP_B']:.0f}B",
            "Change_Pct": calc_macro_change('RRP_B'),
            "Size": 1500
        }
    ]
    
    df_all = pd.concat([pd.DataFrame(macro_blocks), df_assets], ignore_index=True)
    
    # --- B. 绘制 Treemap ---
    
    st.markdown("### 🗺️ 资金全景图")
    st.caption("颜色越绿 = 资金增加/流入 | 颜色越红 = 资金减少/流出")

    fig = px.treemap(
        df_all,
        path=[px.Constant("全球资金池"), 'Type', 'Name'],
        values='Size',
        color='Change_Pct',
        color_continuous_scale=['#FF4B4B', '#31333F', '#09AB3B'], # 红-灰-绿
        color_continuous_midpoint=0,
        range_color=[-5, 5],
        hover_data=['Value', 'Change_Pct'],
    )
    
    fig.update_traces(
        textinfo="label+value+percent entry",
        texttemplate="<b>%{label}</b><br>变动: %{color:.2f}%",
        textfont=dict(size=15)
    )
    
    fig.update_layout(height=600, margin=dict(t=20, l=10, r=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    
    # --- C. 核心数据仪表盘 ---
    st.markdown("### 📟 核心监控台 (The Fed Monitor)")
    
    # 逻辑判断
    liq_change = calc_macro_change('Net_Liquidity')
    if liq_change > 0:
        status = "🟢 宽松 (Pumping)"
    else:
        status = "🔴 紧缩 (Draining)"
        
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("美联储净流动性 (Net Liquidity)", 
                  f"${latest_macro['Net_Liquidity']:.0f} B", 
                  f"{liq_change:.2f}%",
                  delta_color="normal")
        st.caption(f"当前状态: {status}")
        
    with c2:
        # TGA 增加是红色信号（抽水）
        tga_change = calc_macro_change('TGA_B')
        st.metric("财政部 TGA 余额", 
                  f"${latest_macro['TGA_B']:.0f} B", 
                  f"{tga_change:.2f}%",
                  delta_color="inverse") # 设为 inverse：涨了反而显示红色
        st.caption("注：TGA 增加 = 市场资金减少")
        
    with c3:
        # RRP 增加是红色信号（资金闲置）
        rrp_change = calc_macro_change('RRP_B')
        st.metric("逆回购 RRP 余额", 
                  f"${latest_macro['RRP_B']:.0f} B", 
                  f"{rrp_change:.2f}%",
                  delta_color="inverse")
        st.caption("注：RRP 增加 = 资金回笼")

    # --- D. 趋势图 ---
    with st.expander("📈 查看净流动性历史趋势 (1 Year Trend)"):
        st.line_chart(df_macro['Net_Liquidity'])
        st.markdown("**公式：** Net Liquidity = Fed Assets (WALCL) - TGA (WTREGEN) - RRP (RRPONTSYD)")

else:
    st.info("⏳ 正在连接美联储数据库，请稍候...")
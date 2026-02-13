import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性监控", layout="wide")

st.title("💸 全球流动性全景 (Global Liquidity Monitor)")
st.caption("数据源: St. Louis Fed (FRED) & Yahoo Finance | 窗口: 30天变化")

# --- 1. 核心引擎：从 FRED 获取宏观“水源”数据 ---
@st.cache_data(ttl=3600*12)
def get_macro_data():
    # 拉取足够长的数据以防开头是空值
    start_date = datetime.now() - timedelta(days=400) 
    end_date = datetime.now()

    # FRED 代码
    # WALCL: 美联储总资产 (百万美元)
    # WTREGEN: 财政部 TGA 账户 (十亿美元)
    # RRPONTSYD: 隔夜逆回购 (十亿美元)
    # M2SL: M2 广义货币 (十亿美元，月更)
    macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
    
    try:
        df = web.DataReader(macro_codes, 'fred', start_date, end_date)
        
        # 1. 强制日频化 (消灭 NaN 的关键步骤)
        # ffill(): 用昨天的数据填补今天的空缺
        df = df.resample('D').ffill().dropna()
        
        # 2. 单位统一：全部转为 Billion (十亿美元)
        df['Fed_Assets'] = df['WALCL'] / 1000 # Million -> Billion
        df['TGA'] = df['WTREGEN']             # 已经是 Billion
        df['RRP'] = df['RRPONTSYD']           # 已经是 Billion
        
        # 3. 计算净流动性 (Net Liquidity)
        # 公式: 央行总资产 - TGA(政府存款) - RRP(闲置资金)
        df['Net_Liquidity'] = df['Fed_Assets'] - df['TGA'] - df['RRP']
        
        return df
    except Exception as e:
        st.error(f"连接美联储数据库失败: {e}")
        return pd.DataFrame()

# --- 2. 市场引擎：从 YFinance 获取资产“蓄水池” ---
@st.cache_data(ttl=3600)
def get_asset_data():
    assets = {
        "🇺🇸 美股 (SPY)": "SPY",
        "🇺🇸 美债 (TLT)": "TLT",
        "🥇 黄金 (GLD)": "GLD",
        "₿ 比特币 (BTC)": "BTC-USD",
        "🛢️ 原油 (USO)": "USO",
        "💵 美元现金 (BIL)": "BIL" 
    }
    
    tickers = list(assets.values())
    try:
        # 下载过去2个月的数据，确保能算出30天变化
        data = yf.download(tickers, period="3mo", progress=False)['Close']
        
        records = []
        for name, ticker in assets.items():
            if ticker in data.columns:
                series = data[ticker].dropna()
                if len(series) < 30: continue
                
                latest = series.iloc[-1]
                # 强制找30个自然日之前的数据点（大约20-22个交易日）
                # 这样比固定iloc更准确
                try:
                    target_date = series.index[-1] - timedelta(days=30)
                    # 找到离目标日期最近的一天
                    idx = series.index.searchsorted(target_date)
                    prev = series.iloc[idx]
                except:
                    prev = series.iloc[0]
                
                change_pct = (latest - prev) / prev * 100
                
                # 视觉权重 (Visual Size)
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
    except Exception as e:
        return pd.DataFrame()

# --- 3. 自动分析师 (AI Analyst) ---
def generate_analysis(curr, prev):
    # 计算变化
    liq_change = curr['Net_Liquidity'] - prev['Net_Liquidity']
    fed_change = curr['Fed_Assets'] - prev['Fed_Assets']
    tga_change = curr['TGA'] - prev['TGA']
    rrp_change = curr['RRP'] - prev['RRP']
    
    analysis = []
    
    # 1. 总基调
    if liq_change > 50: # 增加超过500亿
        analysis.append(f"🟢 **整体局势: 宽松 (Risk-On)**。过去30天，市场净流动性增加了 **${liq_change:.1f}B**，这对风险资产（股票/加密货币）是直接利好。")
    elif liq_change < -50:
        analysis.append(f"🔴 **整体局势: 紧缩 (Risk-Off)**。过去30天，市场净流动性减少了 **${abs(liq_change):.1f}B**，资金正在撤离，需警惕回调风险。")
    else:
        analysis.append(f"⚪ **整体局势: 平衡 (Neutral)**。过去30天流动性变化不大 (${liq_change:.1f}B)，市场处于存量博弈状态。")
        
    # 2. 归因分析
    analysis.append("\n**驱动因素分析:**")
    
    if fed_change < -10:
        analysis.append(f"- 🖨️ **美联储缩表:** 央行资产减少了 ${abs(fed_change):.1f}B，这是基础货币收缩的主因。")
    elif fed_change > 10:
        analysis.append(f"- 🖨️ **美联储扩表:** 央行资产增加了 ${fed_change:.1f}B，正在注入基础货币。")
        
    if tga_change > 20:
        analysis.append(f"- 👜 **财政部吸血:** TGA账户增加了 ${tga_change:.1f}B，政府发债/收税从市场抽走了大量资金（利空）。")
    elif tga_change < -20:
        analysis.append(f"- 👜 **财政部放水:** TGA账户减少了 ${abs(tga_change):.1f}B，政府支出的钱流回了市场（利好）。")
        
    if rrp_change > 20:
        analysis.append(f"- ♻️ **逆回购回笼:** RRP增加了 ${rrp_change:.1f}B，资金选择回流央行躺平，不愿进入市场（利空）。")
    elif rrp_change < -20:
        analysis.append(f"- ♻️ **逆回购释放:** RRP减少了 ${abs(rrp_change):.1f}B，原本躺平的资金开始进入市场寻找机会（利好）。")
        
    return "\n".join(analysis)

# --- 4. 页面渲染 ---
df_macro = get_macro_data()
df_assets = get_asset_data()

if not df_macro.empty and not df_assets.empty:
    
    # 获取最新和30天前的数据
    curr_macro = df_macro.iloc[-1]
    try:
        # 严格对齐30天前
        target_date = df_macro.index[-1] - timedelta(days=30)
        idx = df_macro.index.searchsorted(target_date)
        prev_macro = df_macro.iloc[idx]
    except:
        prev_macro = df_macro.iloc[0]

    def get_pct_change(col):
        val_curr = curr_macro[col]
        val_prev = prev_macro[col]
        if val_prev == 0: return 0
        return (val_curr - val_prev) / val_prev * 100

    # 构建 Treemap 数据
    macro_blocks = [
        {
            "Name": "🏦 净流动性 (Net Liquidity)", 
            "Type": "Source (水源)",
            "Value": curr_macro['Net_Liquidity'],
            "Display_Value": f"${curr_macro['Net_Liquidity']:.0f}B",
            "Change_Pct": get_pct_change('Net_Liquidity'),
            "Size": 6000
        },
        {
            "Name": "🖨️ 美联储资产 (Fed Assets)", 
            "Type": "Source (水源)",
            "Value": curr_macro['Fed_Assets'],
            "Display_Value": f"${curr_macro['Fed_Assets']:.0f}B",
            "Change_Pct": get_pct_change('Fed_Assets'),
            "Size": 7500
        },
        {
            "Name": "👜 财政部TGA (Gov)", 
            "Type": "Valve (调节阀)",
            "Value": curr_macro['TGA'],
            "Display_Value": f"${curr_macro['TGA']:.0f}B",
            "Change_Pct": get_pct_change('TGA'),
            "Size": 1500
        },
        {
            "Name": "♻️ 逆回购RRP (Parking)", 
            "Type": "Valve (调节阀)",
            "Value": curr_macro['RRP'],
            "Display_Value": f"${curr_macro['RRP']:.0f}B",
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
    fig.update_layout(height=600, margin=dict(t=0, l=0, r=0, b=0))
    st.plotly_chart(fig, use_container_width=True)
    
    # --- 🤖 AI 宏观分析报告 ---
    st.markdown("### 🤖 宏观局势自动解读 (AI Macro Analyst)")
    
    analysis_text = generate_analysis(curr_macro, prev_macro)
    
    # 根据基调给个背景色
    if "宽松" in analysis_text:
        st.success(analysis_text)
    elif "紧缩" in analysis_text:
        st.error(analysis_text)
    else:
        st.info(analysis_text)

    # --- 核心指标解释 ---
    st.markdown("---")
    st.caption("📖 **指标说明:** TGA(财政部账户)和RRP(逆回购)数值**上涨**显示为**红色**，因为这意味着资金从市场流出(利空)；反之显示绿色。")

else:
    st.info("⏳ 正在校准美联储数据，首次加载约需 5 秒...")
import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("全景视角：**【财政+央行】双引擎监控**。现在你可以清晰看到，是谁在偷偷放水。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=3650) 
    
    # A. 宏观数据
    try:
        # 新增 GFDEBTN (联邦政府总债务) -> 用于计算财政赤字注入
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'BOGMBASE', 'M1SL', 'M2SL', 'CURRCIR', 'GFDEBTN']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # B. 资产数据
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

    if not df_macro.empty and df_macro.index.tz is not None: df_macro.index = df_macro.index.tz_localize(None)
    if not df_assets.empty and df_assets.index.tz is not None: df_assets.index = df_assets.index.tz_localize(None)

    df_all = pd.concat([df_macro, df_assets], axis=1)
    df_all = df_all.sort_index().ffill().dropna(how='all')
    
    if not df_all.empty:
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        if 'M1SL' in df_all.columns: df_all['M1'] = df_all['M1SL']
        if 'BOGMBASE' in df_all.columns: df_all['M0'] = df_all['BOGMBASE'] / 1000
        if 'CURRCIR' in df_all.columns: df_all['Currency'] = df_all['CURRCIR'] / 1000
        
        # === 核心逻辑：计算财政注入 (Fiscal Injection) ===
        # 逻辑：财政部每增加 $1 国债，如果不趴在 TGA 里，就是流向了市场。
        # 我们用过去 12 个月的债务增量，代表“年化财政赤字注入规模”
        if 'GFDEBTN' in df_all.columns:
            df_all['Total_Debt'] = df_all['GFDEBTN'] / 1000 # 换算成 Trillion
            # 计算同比增量 (YoY Change)作为当前的注入速度
            df_all['Fiscal_Injection'] = df_all['Total_Debt'].diff(365)
            df_all['Fiscal_Injection'] = df_all['Fiscal_Injection'].fillna(method='bfill')

        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    tab_treemap, tab_waterfall, tab_corr = st.tabs(["🏰 市值时光机", "🏭 货币流水线 (含财政)", "📈 趋势叠加"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (Treemap)
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 资产池存量变化")
        # 复用之前的逻辑
        ids = ["root", "cat_source", "cat_valve", "cat_asset", "m0", "fed", "m2", "m1", "m2_other", "tga", "rrp", "spy", "tlt", "gld", "btc", "uso"]
        parents = ["", "root", "root", "root", "cat_source", "cat_source", "cat_source", "m2", "m2", "cat_valve", "cat_valve", "cat_asset", "cat_asset", "cat_asset", "cat_asset", "cat_asset"]
        labels = ["全球资金池", "Source", "Valve", "Asset", "🌱 M0", "🖨️ Fed", "💰 M2", "💧 M1", "🏦 定存", "👜 TGA", "♻️ RRP", "🇺🇸 SPY", "📜 TLT", "🥇 GLD", "₿ BTC", "🛢️ USO"]
        colors = ["#333", "#2E86C1", "#8E44AD", "#D35400", "#1ABC9C", "#5DADE2", "#2980B9", "#3498DB", "#AED6F1", "#AF7AC5", "#AF7AC5", "#E59866", "#E59866", "#E59866", "#E59866", "#E59866"]
        
        df_weekly = df.resample('W-FRI').last().iloc[-52:]
        latest_row = df.iloc[-1]
        LATEST_CAPS = {"M2": 22300, "SPY": 55000, "TLT": 52000, "GLD": 14000, "BTC-USD": 2500, "USO": 2000}
        
        frames = []
        steps = []
        for date in df_weekly.index:
            date_str = date.strftime('%Y-%m-%d')
            row = df_weekly.loc[date]
            vals = {}
            def get_val(col): return float(row.get(col, 0)) if not pd.isna(row.get(col)) else 0.0
            def get_asset_size(col):
                curr = get_val(col)
                last = float(latest_row.get(col, 1))
                base = LATEST_CAPS.get(col, 100)
                return base * (curr / last) if last != 0 else base

            vals['m0'] = get_val('M0')
            vals['m1'] = get_val('M1')
            vals['m2'] = get_val('M2')
            vals['fed'] = get_val('Fed_Assets')
            vals['m2_other'] = max(0, vals['m2'] - vals['m1'])
            vals['m2'] = vals['m1'] + vals['m2_other']
            vals['tga'] = abs(get_val('TGA'))
            vals['rrp'] = abs(get_val('RRP'))
            vals['spy'] = get_asset_size('SPY')
            vals['tlt'] = get_asset_size('TLT')
            vals['gld'] = get_asset_size('GLD')
            vals['btc'] = get_asset_size('BTC-USD')
            vals['uso'] = get_asset_size('USO')
            
            vals['cat_source'] = vals['m0'] + vals['fed'] + vals['m2']
            vals['cat_valve'] = vals['tga'] + vals['rrp']
            vals['cat_asset'] = vals['spy'] + vals['tlt'] + vals['gld'] + vals['btc'] + vals['uso']
            vals['root'] = vals['cat_source'] + vals['cat_valve'] + vals['cat_asset']
            
            final_values = [vals['root'], vals['cat_source'], vals['cat_valve'], vals['cat_asset'], vals['m0'], vals['fed'], vals['m2'], vals['m1'], vals['m2_other'], vals['tga'], vals['rrp'], vals['spy'], vals['tlt'], vals['gld'], vals['btc'], vals['uso']]
            text_list = [f"${v/1000:.1f}T" if v > 1000 else f"${v:,.0f}B" for v in final_values]
            frames.append(go.Frame(name=date_str, data=[go.Treemap(ids=ids, parents=parents, values=final_values, labels=labels, text=text_list, branchvalues="total")]))
            steps.append(dict(method="animate", args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))], label=date_str))

        if frames:
            fig_tree = go.Figure(data=[go.Treemap(ids=ids, parents=parents, labels=labels, values=frames[-1].data[0].values, text=frames[-1].data[0].text, textinfo="label+text", branchvalues="total", marker=dict(colors=colors), hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>", pathbar=dict(visible=False))], frames=frames)
            fig_tree.update_layout(height=600, margin=dict(t=0, l=0, r=0, b=0), sliders=[dict(active=len(steps)-1, currentvalue={"prefix": "📅 历史: "}, pad={"t": 50}, steps=steps)], updatemenus=[dict(type="buttons", showactive=False, visible=False)])
            st.plotly_chart(fig_tree, use_container_width=True)

    # ==========================================
    # PROJECT 2: 货币流水线 (Sankey with Fiscal)
    # ==========================================
    with tab_waterfall:
        st.markdown("##### 🏭 双引擎流水线：央行(Monetary) + 财政(Fiscal)")
        st.caption("注意观察：**【财政赤字】** 是如何绕过央行，直接向经济体(M2)暴力注资的。这就是为什么加息也没把经济搞崩的原因。")
        
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider("选择时间点：", options=available_dates, value=available_dates[-1], key="layer_slider")
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
        # --- 数据准备 ---
        fed_assets = float(row.get('Fed_Assets', 0))
        tga = float(row.get('TGA', 0))
        rrp = float(row.get('RRP', 0))
        m0 = float(row.get('M0', 0))
        currency = float(row.get('Currency', 0))
        reserves = m0 - currency
        
        m1 = float(row.get('M1', 0))
        m2 = float(row.get('M2', 0))
        
        # 核心：财政赤字注入量 (年化)
        fiscal_injection = float(row.get('Fiscal_Injection', 0))
        if fiscal_injection < 0: fiscal_injection = 0 # 保护
        
        # 倒挤信贷创造
        # M2 的来源 = 现金 + 财政注入 + 银行信贷创造
        # 所以：信贷创造 = M2 - (现金 + 财政注入)
        bank_credit_creation = m2 - currency - fiscal_injection
        
        # 资产端
        spy_price = float(row.get('SPY', 0))
        latest_spy = float(latest_row.get('SPY', 1))
        asset_pool_base = 100000 
        asset_pool_curr = asset_pool_base * (spy_price/latest_spy) if latest_spy else asset_pool_base
        valuation_leverage = asset_pool_curr - m2 * 0.5 

        # --- 节点定义 ---
        # 0: Fed
        # 1: Fiscal (财政部) <--- NEW!
        # 2: TGA/RRP (Leak)
        # 3: M0
        # 4: Currency
        # 5: Reserves
        # 6: Bank Credit (信贷)
        # 7: M2
        # 8: Valuation
        # 9: Assets
        
        label_list = [
            f"🏛️ 央行 (Fed)<br>${fed_assets/1000:.1f}T",    # 0
            f"🦅 财政部 (Fiscal)<br>赤字注入 ${fiscal_injection/1000:.1f}T/yr", # 1 (NEW)
            f"🔒 损耗 (TGA/RRP)<br>${(tga+rrp)/1000:.1f}T", # 2
            f"🌱 基础货币 (M0)<br>${m0/1000:.1f}T",       # 3
            f"💵 现金<br>${currency/1000:.1f}T",             # 4
            f"🏦 准备金<br>${reserves/1000:.1f}T",     # 5
            f"⚡ 银行信贷创造<br>+${bank_credit_creation/1000:.1f}T",# 6
            f"🌊 广义货币 (M2)<br>${m2/1000:.1f}T",       # 7
            f"📈 市场情绪溢价<br>+${valuation_leverage/1000:.1f}T", # 8
            f"🏙️ 资产终局<br>${asset_pool_curr/1000:.1f}T" # 9
        ]
        
        # 坐标锁定 (5阶段)
        # X: Source(0) -> M0(0.25) -> Components(0.4) -> M2(0.7) -> Assets(1.0)
        node_x = [0.001, 0.4,   0.2, 0.2, 0.4, 0.4, 0.4, 0.7, 0.7, 0.999]
        node_y = [0.5,   0.1,   0.9, 0.4, 0.3, 0.6, 0.9, 0.5, 0.1, 0.5] 
        
        color_list = [
            "#F1C40F", # Fed 黄
            "#E74C3C", # Fiscal 红 (NEW!)
            "#8E44AD", # Leak 紫
            "#2ECC71", # M0 绿
            "#1ABC9C", # Currency 青
            "#95A5A6", # Reserves 灰
            "#BDC3C7", # Credit 灰
            "#2E86C1", # M2 蓝
            "#BDC3C7", # Valuation 灰
            "#E74C3C"  # Assets 红
        ]
        
        fig_sankey = go.Figure(data=[go.Sankey(
            arrangement = "snap", 
            node = dict(pad = 10, thickness = 20, line = dict(color = "black", width = 0.5), label = label_list, color = color_list, x = node_x, y = node_y), 
            link = dict(
                source = [0,       0,   3,        3,        4,  6,                    1,                7,      7,      8], 
                target = [2,       3,   4,        5,        7,  7,                    7,                9,      9,      9],
                value =  [tga+rrp, m0,  currency, reserves, currency, bank_credit_creation, fiscal_injection, m2*0.5, m2*0.5, valuation_leverage],
                # 关键连线解释：
                # 1 -> 7: 财政部 (Node 1) 直接连向 M2 (Node 7)。这是赤字注入！
                # 6 -> 7: 银行信贷 (Node 6) 连向 M2。
                
                label =  ["损耗", "M0", "现金", "准备金", "现金", "信贷扩张", "赤字支出(暴力注入)", "实体经济", "金融分流", "估值放大"],
                color =  ["#D7BDE2", "#ABEBC6", "#A2D9CE", "#D5DBDB", "#A2D9CE", "#D5DBDB", "#F5B7B1", "#AED6F1", "#AED6F1", "#E6B0AA"]
            )
        )])
        
        fig_sankey.update_layout(height=650, font=dict(size=14))
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info(f"""
        **🦅 财政部 (Fiscal) 正在做什么？**
        * 当前的年化赤字注入速度约为：**${fiscal_injection/1000:.2f}T / 年**。
        * **看图重点：** 注意那个红色的 **“财政部”** 节点。它像一个外挂的增压泵，即使上面的黄色 **“央行”** 管道在变细（缩表），红色的赤字管道依然在源源不断地往蓝色的 **M2** 里注水。
        * **结论：** 只要财政赤字不减，市场里的钱就不会少。
        """)

    # ==========================================
    # PROJECT 3: 趋势相关性 (Trend Overlay)
    # ==========================================
    with tab_corr:
        st.markdown("##### 📈 寻找“鳄鱼嘴”：资金与资产的背离")
        
        col_ctrl1, col_ctrl2 = st.columns([1, 3])
        with col_ctrl1:
            lookback_days = st.selectbox("📅 观测周期", [365, 730, 1095, 1825, 3650], index=3, format_func=lambda x: f"过去 {x/365:.0f} 年" if x >= 365 else f"过去 {x} 天")
            chart_mode = st.radio("👀 观测模式", ["双轴叠加 (看背离)", "归一化跑分 (看强弱)"], index=0)
        
        df_chart = df.iloc[-lookback_days:].copy()
        
        fig_trend = make_subplots(specs=[[{"secondary_y": True}]])
        
        if chart_mode == "双轴叠加 (看背离)":
            fig_trend.add_trace(
                go.Scatter(x=df_chart.index, y=df_chart['Net_Liquidity'], name="💧 净流动性 (左轴)", 
                           fill='tozeroy', line=dict(color='rgba(46, 204, 113, 0.5)', width=0), hovertemplate="$%{y:.2f}B"),
                secondary_y=False
            )
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=df_chart['SPY'], name="🇺🇸 美股 SPY (右轴)", line=dict(color='#E74C3C', width=2)), secondary_y=True)
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=df_chart['BTC-USD'], name="₿ 比特币 (右轴)", line=dict(color='#F39C12', width=2)), secondary_y=True)
            
            fig_trend.update_yaxes(title_text="净流动性 (Billions)", secondary_y=False, showgrid=False)
            fig_trend.update_yaxes(title_text="资产价格 ($)", secondary_y=True, showgrid=True)
            
        else:
            def normalize(series): return (series / series.iloc[0] - 1) * 100
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['Net_Liquidity']), name="💧 净流动性 %", line=dict(color='#2ECC71', width=3)))
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['SPY']), name="🇺🇸 美股 %", line=dict(color='#E74C3C', width=2)))
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['BTC-USD']), name="₿ 比特币 %", line=dict(color='#F39C12', width=2)))
            fig_trend.add_trace(go.Scatter(x=df_chart.index, y=normalize(df_chart['M2']), name="💰 M2 %", line=dict(color='#3498DB', width=1, dash='dot')))
            fig_trend.update_yaxes(title_text="累计涨跌幅 (%)")
        
        fig_trend.update_layout(height=600, hovermode="x unified", legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"), margin=dict(t=0, l=10, r=10, b=10))
        st.plotly_chart(fig_trend, use_container_width=True)
        
        with col_ctrl2:
            st.warning(f"**分析提示：** 如果看到绿色阴影（央行流动性）下降，但资产价格坚挺，请去 Tab 2 看看红色的【财政赤字】是不是在疯狂注水。")

else:
    st.info("⏳ 正在拉取十年宏观数据 (含财政部债务)...")
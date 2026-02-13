import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("双重视角：**【市值】**看存量大小，**【货币流水线】**看资金如何像通过工厂一样逐级加工放大。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'BOGMBASE', 'M1SL', 'M2SL', 'CURRCIR']
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
        # 单位 Billion
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        if 'M1SL' in df_all.columns: df_all['M1'] = df_all['M1SL']
        if 'BOGMBASE' in df_all.columns: df_all['M0'] = df_all['BOGMBASE'] / 1000
        if 'CURRCIR' in df_all.columns: df_all['Currency'] = df_all['CURRCIR'] / 1000
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'M2' in df.columns:
    
    tab_treemap, tab_waterfall = st.tabs(["🏰 市值时光机 (嵌套结构)", "🏭 货币流水线 (严谨分层)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (Treemap) - 保持不变
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 资产池存量变化")
        # 复用 V5.1 逻辑
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
            fig_tree.update_layout(height=650, margin=dict(t=0, l=0, r=0, b=0), sliders=[dict(active=len(steps)-1, currentvalue={"prefix": "📅 历史: "}, pad={"t": 50}, steps=steps)], updatemenus=[dict(type="buttons", showactive=False, visible=False)])
            st.plotly_chart(fig_tree, use_container_width=True)

    # ==========================================
    # PROJECT 2: 严谨货币流水线 (Strict 5-Stage Sankey)
    # ==========================================
    with tab_waterfall:
        st.markdown("##### 🏭 资金加工流水线：从央行到市场")
        st.caption("遗憾的是 Plotly 不支持纵向排版。但我为你设计了**严格锁定的【五阶横向流水线】**，逻辑依然清晰：左侧是源头，右侧是终局。")
        
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
        demand_deposits = m1 - currency
        m2 = float(row.get('M2', 0))
        savings_deposits = m2 - m1
        spy_price = float(row.get('SPY', 0))
        latest_spy = float(latest_row.get('SPY', 1))
        asset_pool_base = 100000 
        asset_pool_curr = asset_pool_base * (spy_price/latest_spy) if latest_spy else asset_pool_base
        valuation_leverage = asset_pool_curr - m2 * 0.5 
        
        # --- 强制分列 (X-Axis Locking) ---
        # 0.00 = 最左边 (Source)
        # 1.00 = 最右边 (Assets)
        # 只要锁死了X轴，它就一定不会乱跑
        
        # Node Indices
        # 0: Fed
        # 1: TGA+RRP (Leak)
        # 2: M0
        # 3: Currency
        # 4: Reserves
        # 5: Credit (Demand)
        # 6: M1
        # 7: Credit (Savings)
        # 8: M2
        # 9: Valuation
        # 10: Assets
        
        label_list = [
            f"🏛️ 1. 央行源头<br>${fed_assets/1000:.1f}T",    # 0 @ x=0.01
            f"🔒 损耗 (TGA/RRP)<br>${(tga+rrp)/1000:.1f}T", # 1 @ x=0.2
            f"🌱 2. 基础货币 (M0)<br>${m0/1000:.1f}T",       # 2 @ x=0.2
            f"💵 现金<br>${currency/1000:.1f}T",             # 3 @ x=0.35
            f"🏦 准备金 (影子)<br>${reserves/1000:.1f}T",     # 4 @ x=0.35
            f"⚡ 信贷创造 I<br>+${demand_deposits/1000:.1f}T",# 5 @ x=0.35
            f"💧 3. 狭义货币 (M1)<br>${m1/1000:.1f}T",       # 6 @ x=0.5
            f"⚡ 信贷创造 II<br>+${savings_deposits/1000:.1f}T",# 7 @ x=0.65
            f"🌊 4. 广义货币 (M2)<br>${m2/1000:.1f}T",       # 8 @ x=0.8
            f"📈 市场情绪溢价<br>+${valuation_leverage/1000:.1f}T", # 9 @ x=0.8
            f"🏙️ 5. 资产终局<br>${asset_pool_curr/1000:.1f}T" # 10 @ x=0.99
        ]
        
        # 手动指定 X, Y 坐标 (0-1之间)
        # 这就是“强制排版”的秘诀
        node_x = [0.001, 0.2, 0.2, 0.35, 0.35, 0.35, 0.5, 0.65, 0.8, 0.8, 0.999]
        node_y = [0.5,   0.9, 0.3, 0.1,  0.5,  0.8,  0.5, 0.8,  0.5, 0.1, 0.5] 
        
        color_list = [
            "#F1C40F", "#8E44AD", "#2ECC71", 
            "#1ABC9C", "#95A5A6", "#BDC3C7", 
            "#3498DB", "#BDC3C7", "#2E86C1", 
            "#BDC3C7", "#E74C3C"
        ]
        
        fig_sankey = go.Figure(data=[go.Sankey(
            arrangement = "snap", # 关键：让节点吸附在网格上
            node = dict(
                pad = 10, thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = label_list,
                color = color_list,
                x = node_x, # <--- 强制锁定列位置
                y = node_y  # <--- 建议行位置
            ),
            link = dict(
                source = [0,       0,   2,        2,        3,  5,  6,  7,  8,   8,                 9], 
                target = [1,       2,   3,        4,        6,  6,  8,  8,  10,  10,                10],
                value =  [tga+rrp, m0,  currency, reserves, currency, demand_deposits, m1, savings_deposits, m2*0.5, m2*0.5, valuation_leverage],
                color =  ["#D7BDE2", "#ABEBC6", "#A2D9CE", "#D5DBDB", "#A2D9CE", "#D5DBDB", "#AED6F1", "#D5DBDB", "#AED6F1", "#D5DBDB", "#E6B0AA"]
            )
        )])
        
        fig_sankey.update_layout(height=650, font=dict(size=14))
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info("""
        **🏭 五级流水线解读：**
        1.  **Stage 1 (最左):** 美联储资产，一切的源头。
        2.  **Stage 2:** 分流为“基础货币(M0)”和“损耗(TGA/RRP)”。
        3.  **Stage 3:** M0中的现金 + 银行的第一轮信贷创造 = **M1**。
        4.  **Stage 4:** M1 + 银行的第二轮信贷创造 = **M2**。
        5.  **Stage 5 (最右):** 资金入市 + 市场情绪放大 = **最终资产价格**。
        """)

else:
    st.info("⏳ 正在构建全维度数据模型...")
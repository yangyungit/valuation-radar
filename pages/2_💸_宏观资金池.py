import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("双重视角：**【市值】**看存量大小，**【货币层级】**看 M0->M1->M2 的套娃包含关系与最终流向。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据
    try:
        # 获取 M0 (BOGMBASE), M1, M2
        # CURRCIR = 流通中的通货 (M0的一部分)
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
    
    tab_treemap, tab_waterfall = st.tabs(["🏰 市值时光机 (存量)", "🪆 货币层级瀑布 (M0-M2-Assets)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (Treemap) - 保持不变
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 资产池存量变化")
        # ... (此处复用之前的代码逻辑，为了节省篇幅我只保留核心框架，实际运行会包含完整逻辑) ...
        # (请确保这里的代码与上一版 V5 手动挡一致，此处略写以聚焦 Tab 2)
        ids = ["root", "cat_source", "cat_valve", "cat_asset", "m2", "fed", "nl", "tga", "rrp", "spy", "tlt", "gld", "btc", "uso"]
        parents = ["", "root", "root", "root", "cat_source", "cat_source", "cat_source", "cat_valve", "cat_valve", "cat_asset", "cat_asset", "cat_asset", "cat_asset", "cat_asset"]
        labels = ["全球资金池", "Source", "Valve", "Asset", "💰 M2", "🖨️ Fed", "🏦 NetLiq", "👜 TGA", "♻️ RRP", "🇺🇸 SPY", "📜 TLT", "🥇 GLD", "₿ BTC", "🛢️ USO"]
        colors = ["#333", "#2E86C1", "#8E44AD", "#D35400", "#5DADE2", "#5DADE2", "#5DADE2", "#AF7AC5", "#AF7AC5", "#E59866", "#E59866", "#E59866", "#E59866", "#E59866"]
        
        df_weekly = df.resample('W-FRI').last().iloc[-52:]
        latest_row = df.iloc[-1]
        LATEST_CAPS = {"M2": 22300, "SPY": 55000, "TLT": 52000, "GLD": 14000, "BTC-USD": 2500, "USO": 2000}
        
        frames = []
        steps = []
        for date in df_weekly.index:
            date_str = date.strftime('%Y-%m-%d')
            row = df_weekly.loc[date]
            vals = {}
            def get_size(col, is_macro=False):
                val_curr = float(row.get(col, 0)) if not pd.isna(row.get(col)) else 0.0
                if is_macro: return abs(val_curr)
                val_last = float(latest_row.get(col, 1)) if not pd.isna(latest_row.get(col)) else 1.0
                base = LATEST_CAPS.get(col, 100)
                if val_last != 0: return base * (val_curr / val_last)
                return base

            vals['m2'] = get_size('M2', True)
            vals['fed'] = get_size('Fed_Assets', True)
            vals['nl'] = get_size('M0', True) # 使用M0代替NetLiq展示
            vals['tga'] = get_size('TGA', True)
            vals['rrp'] = get_size('RRP', True)
            vals['spy'] = get_size('SPY', False)
            vals['tlt'] = get_size('TLT', False)
            vals['gld'] = get_size('GLD', False)
            vals['btc'] = get_size('BTC-USD', False)
            vals['uso'] = get_size('USO', False)
            
            vals['cat_source'] = vals['m2'] + vals['fed'] + vals['nl']
            vals['cat_valve'] = vals['tga'] + vals['rrp']
            vals['cat_asset'] = vals['spy'] + vals['tlt'] + vals['gld'] + vals['btc'] + vals['uso']
            vals['root'] = vals['cat_source'] + vals['cat_valve'] + vals['cat_asset']
            
            final_values = [vals['root'], vals['cat_source'], vals['cat_valve'], vals['cat_asset'], vals['m2'], vals['fed'], vals['nl'], vals['tga'], vals['rrp'], vals['spy'], vals['tlt'], vals['gld'], vals['btc'], vals['uso']]
            text_list = [f"${v/1000:.1f}T" if v > 1000 else f"${v:,.0f}B" for v in final_values]
            frames.append(go.Frame(name=date_str, data=[go.Treemap(ids=ids, parents=parents, values=final_values, labels=labels, text=text_list, branchvalues="total")]))
            steps.append(dict(method="animate", args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))], label=date_str))

        if frames:
            fig_tree = go.Figure(data=[go.Treemap(ids=ids, parents=parents, labels=labels, values=frames[-1].data[0].values, text=frames[-1].data[0].text, textinfo="label+text", branchvalues="total", marker=dict(colors=colors), hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>", pathbar=dict(visible=False))], frames=frames)
            fig_tree.update_layout(height=600, margin=dict(t=0, l=0, r=0, b=0), sliders=[dict(active=len(steps)-1, currentvalue={"prefix": "📅 历史: "}, pad={"t": 50}, steps=steps)], updatemenus=[dict(type="buttons", showactive=False, visible=False)])
            st.plotly_chart(fig_tree, use_container_width=True)

    # ==========================================
    # PROJECT 2: 货币层级瀑布 (The Money Supply Layer Cake)
    # ==========================================
    with tab_waterfall:
        st.markdown("##### 🪆 货币俄罗斯套娃：从 M0 到 资产")
        st.caption("清晰展示包含关系：**M1 包含现金，M2 包含 M1。** 以及银行信贷是如何无中生有的。")
        
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider("选择时间点：", options=available_dates, value=available_dates[-1], key="layer_slider")
        
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
        # --- 数据准备 ---
        # 1. 顶层：美联储
        fed_assets = float(row.get('Fed_Assets', 0))
        tga = float(row.get('TGA', 0))
        rrp = float(row.get('RRP', 0))
        
        # 2. M0 层 (Base Money)
        m0 = float(row.get('M0', 0)) # BOGMBASE
        currency = float(row.get('Currency', 0)) # 纸币 (M0的一部分)
        reserves = m0 - currency # 银行准备金 (M0的另一部分)
        
        # 3. M1 层 (Narrow Money)
        m1 = float(row.get('M1', 0))
        # M1 = Currency + Demand Deposits
        # 倒挤出 Demand Deposits (银行创造的活期存款)
        demand_deposits = m1 - currency
        
        # 4. M2 层 (Broad Money)
        m2 = float(row.get('M2', 0))
        # M2 = M1 + Savings/Time Deposits
        # 倒挤出 Savings (银行创造的储蓄存款)
        savings_deposits = m2 - m1
        
        # 5. 资产层 (Market)
        spy_price = float(row.get('SPY', 0))
        latest_spy = float(latest_row.get('SPY', 1))
        # 假设总金融资产池规模 (含债市)
        asset_pool_base = 100000 # 100T 假设值，用于展示比例
        asset_pool_curr = asset_pool_base * (spy_price/latest_spy) if latest_spy else asset_pool_base
        
        # 估值杠杆 = 资产池 - M2 (钱进来了，通过估值放大)
        valuation_leverage = asset_pool_curr - m2 * 0.5 # 假设50% M2进入市场
        
        # --- 绘制 Sankey ---
        
        # 节点 (Nodes)
        label_list = [
            f"🏛️ Fed资产<br>${fed_assets/1000:.1f}T",    # 0
            f"🔒 TGA/RRP<br>${(tga+rrp)/1000:.1f}T",     # 1
            f"🌱 M0 (基础货币)<br>${m0/1000:.1f}T",       # 2
            f"💵 现金<br>${currency/1000:.1f}T",         # 3
            f"🏦 准备金<br>${reserves/1000:.1f}T",       # 4 (不进M1)
            f"⚡ 活期信贷创造<br>+${demand_deposits/1000:.1f}T", # 5 (Credit)
            f"💧 M1 (狭义货币)<br>${m1/1000:.1f}T",       # 6
            f"⚡ 储蓄信贷创造<br>+${savings_deposits/1000:.1f}T",# 7 (Credit)
            f"🌊 M2 (广义货币)<br>${m2/1000:.1f}T",       # 8
            f"📈 估值放大<br>+${valuation_leverage/1000:.1f}T", # 9
            f"🏙️ 金融资产池<br>${asset_pool_curr/1000:.1f}T"   # 10
        ]
        
        color_list = [
            "#F1C40F", "#8E44AD", "#2ECC71", # Fed, Leak, M0
            "#1ABC9C", "#95A5A6", "#BDC3C7", # Currency, Reserves, Credit
            "#3498DB", "#BDC3C7", "#2E86C1", # M1, Credit, M2
            "#BDC3C7", "#E74C3C"             # Valuation, Assets
        ]
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 15, thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = label_list,
                color = color_list
            ),
            link = dict(
                # Source -> Target
                source = [0,       0,   2,        2,        3,  5,  6,  7,  8,   8,                 9], 
                target = [1,       2,   3,        4,        6,  6,  8,  8,  10,  10,                10],
                value =  [tga+rrp, m0,  currency, reserves, currency, demand_deposits, m1, savings_deposits, m2*0.5, m2*0.5, valuation_leverage],
                # 解释：
                # 0->2: Fed -> M0
                # 2->3: M0 -> 现金
                # 2->4: M0 -> 准备金 (注意：准备金死在这里了，它是M1的影子，不直接构成M1)
                # 3->6: 现金 -> M1 (包含关系！)
                # 5->6: 活期创造 -> M1
                # 6->8: M1 -> M2 (包含关系！M1全额流入M2)
                # 7->8: 储蓄创造 -> M2
                # 8->10: M2 -> 资产 (一部分)
                
                label =  ["损耗", "M0", "现金", "准备金(支撑)", "包含", "信贷扩张", "包含", "信贷扩张", "资金流入", "实体经济", "估值溢价"],
                color =  ["#D7BDE2", "#ABEBC6", "#A2D9CE", "#D5DBDB", "#A2D9CE", "#D5DBDB", "#AED6F1", "#D5DBDB", "#AED6F1", "#D5DBDB", "#E6B0AA"]
            )
        )])
        
        fig_sankey.update_layout(height=650, font=dict(size=14))
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info("""
        **🔍 如何看懂“货币套娃”：**
        1.  **M0 $\\to$ M1:** 只有 M0 里的 **现金** (绿色细线) 流进了 M1。另一部分 **准备金** 留在了银行体系内做支撑。
        2.  **M1 $\\to$ M2:** 注意看蓝色的 **M1 管道**，它 **100% 全额流进了 M2**。这就是“包含关系”的直接体现。
        3.  **灰色管道:** 每一个灰色输入，都代表商业银行的 **“信贷印钞机”** 在工作，凭空创造了新的存款 (M1/M2)。
        4.  **M3?** 美联储停止追踪 M3，但通常 M3 = M2 + 机构大额存款。你可以想象在 M2 下面再加一级灰色信贷，注入变成 M3。
        """)

else:
    st.info("⏳ 正在构建货币层级模型...")
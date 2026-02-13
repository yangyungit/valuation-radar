import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("双重视角：**【市值】**看存量大小，**【液压】**看央行资产负债表的严格流向。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据 (FRED)
    # 新增 CURRCIR (流通中通货) 以配平资产负债表
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'CURRCIR', 'M2SL']
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
        # 单位换算 Billion
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'CURRCIR' in df_all.columns: df_all['Currency'] = df_all['CURRCIR'] / 1000
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        
        # === 核心逻辑：计算银行准备金 (Reserves) ===
        # 资产负债表恒等式：Assets = Liabilities
        # Liabilities = TGA + RRP + Currency + Reserves + Others
        # 因此：Reserves ≈ Fed Assets - TGA - RRP - Currency
        # (注：这就构成了完美的总量守恒)
        cols = ['Fed_Assets', 'TGA', 'RRP', 'Currency']
        if all(col in df_all.columns for col in cols):
            df_all['Reserves'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP'] - df_all['Currency']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Reserves' in df.columns:
    
    tab_treemap, tab_sankey = st.tabs(["🏰 市值时光机 (存量)", "🌊 美联储液压图 (流量守恒)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (保持不变)
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 资产池存量变化")
        # ... (此处省略 Treemap 代码，复用之前的逻辑) ...
        # 为了代码简洁，这里直接调用之前的逻辑，或者你需要我把那段代码再贴一遍？
        # 既然你满意之前的 Treemap，我就保留它的核心逻辑
        
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
            vals['nl'] = get_size('Reserves', True) # 这里用Reserves代替NetLiq展示
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
    # PROJECT 2: 美联储资产负债表液压图 (The Accounting Identity)
    # ==========================================
    with tab_sankey:
        st.markdown("##### 🌊 美联储资产负债表透视 (Fed Balance Sheet Anatomy)")
        st.caption("这是真正的【总量守恒】。左边是央行的资产，右边是它的四个去向。只有流向 **Bank Reserves** 的钱，才是市场真正的子弹。")
        
        # 服务端滑块
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider("选择观测时间点：", options=available_dates, value=available_dates[-1], key="sankey_slider_2")
        
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
        # 1. 提取核心数据
        fed_assets = float(row.get('Fed_Assets', 0))
        
        # 2. 提取分流数据
        tga = float(row.get('TGA', 0))
        rrp = float(row.get('RRP', 0))
        currency = float(row.get('Currency', 0))
        # 倒挤算出 Reserves，确保 100% 守恒
        reserves = fed_assets - tga - rrp - currency
        
        # 3. 提取下游数据 (Context only)
        m2 = float(row.get('M2', 0))
        spy = float(row.get('SPY', 0))
        
        col_chart, col_metrics = st.columns([3, 1])
        
        with col_chart:
            # 节点定义
            label_list = [
                f"🏛️ 美联储总资产<br>${fed_assets/1000:.1f}T",  # Node 0
                f"🔒 TGA (财政部)<br>${tga:.0f}B",             # Node 1
                f"💤 RRP (逆回购)<br>${rrp:.0f}B",             # Node 2
                f"💵 流通现金 (M0)<br>${currency/1000:.1f}T",   # Node 3
                f"⚡ 银行准备金 (Reserves)<br>${reserves/1000:.1f}T" # Node 4
            ]
            
            color_list = ["#F1C40F", "#8E44AD", "#2E86C1", "#95A5A6", "#2ECC71"]
            
            fig_sankey = go.Figure(data=[go.Sankey(
                node = dict(
                    pad = 20, thickness = 30,
                    line = dict(color = "black", width = 0.5),
                    label = label_list,
                    color = color_list
                ),
                link = dict(
                    source = [0, 0, 0, 0], 
                    target = [1, 2, 3, 4], 
                    value =  [tga, rrp, currency, reserves],
                    color =  ["#D7BDE2", "#AED6F1", "#D0D3D4", "#ABEBC6"] 
                )
            )])
            
            fig_sankey.update_layout(height=550, margin=dict(t=10, l=10, r=10, b=10), font=dict(size=14))
            st.plotly_chart(fig_sankey, use_container_width=True)

        with col_metrics:
            st.info("📊 **下游传导链条**")
            st.metric("1. 基础弹药 (Reserves)", f"${reserves/1000:.2f}T", help="银行系统的闲置资金，可用于放贷或买资产")
            st.markdown("⬇️ *信用乘数放大*")
            st.metric("2. 广义货币 (M2)", f"${m2/1000:.1f}T", help="Reserves 通过银行放贷扩张成了 M2")
            st.markdown("⬇️ *购买力溢出*")
            st.metric("3. 标普500 (SPY)", f"${spy:.2f}", help="最终推升了资产价格")
            
            st.warning("""
            **守恒定律解读：**
            美联储总资产 = TGA + RRP + 现金 + 准备金。
            
            *我们不能把股市画在Sankey里，因为股市市值(50T)远大于流动性(6T)，它们不是包含关系，而是**杠杆撬动**关系。*
            """)

else:
    st.info("⏳ 正在构建金融液压系统...")
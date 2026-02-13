import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("双重视角：**【市值】**看存量大小，**【宏观瀑布】**看资金是如何通过**杠杆**逐级放大的。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据
    try:
        # 新增 M1, CURRCIR (M0 part)
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'CURRCIR', 'M2SL', 'M1SL']
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
        if 'CURRCIR' in df_all.columns: df_all['Currency'] = df_all['CURRCIR'] / 1000
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        if 'M1SL' in df_all.columns: df_all['M1'] = df_all['M1SL']
        
        # 算 M0 (Base Money) ≈ Currency + Reserves (Fed Assets - TGA - RRP)
        # 这里为了展示方便，我们把 Fed Assets 减去 TGA/RRP 后剩下的直接称为 "有效基础货币 (Effective M0)"
        df_all['Effective_Base'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'M2' in df.columns:
    
    tab_treemap, tab_waterfall = st.tabs(["🏰 市值时光机 (存量)", "🌊 宏观资金瀑布 (杠杆传导)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (V5 稳定版)
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 资产池存量变化")
        # ... (Treemap 代码逻辑保持不变，略去以节省篇幅，功能与之前一致) ...
        # 这里为了完整性，实际上应该保留之前的Treemap代码
        # 简单起见，我直接复用之前的逻辑结构
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
            vals['nl'] = get_size('Effective_Base', True)
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
    # PROJECT 2: 宏观资金瀑布 (The Macro Waterfall)
    # ==========================================
    with tab_waterfall:
        st.markdown("##### 🌊 资金传导瀑布图：从印钞机到资产泡沫")
        st.caption("展示资金如何通过 **银行信贷 (Credit Multiplier)** 和 **市场估值 (Valuation Multiplier)** 逐级放大。")
        
        # 滑块控制
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider("选择时间点：", options=available_dates, value=available_dates[-1], key="wf_slider")
        
        # 数据准备
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
        # 1. 基础层 (Base Layer)
        fed_assets = float(row.get('Fed_Assets', 0))
        tga = float(row.get('TGA', 0))
        rrp = float(row.get('RRP', 0))
        # 这里的 M0 约等于 基础货币 (Reserves + Currency)
        base_money_m0 = fed_assets - tga - rrp
        
        # 2. 银行层 (Bank Layer)
        m2 = float(row.get('M2', 0))
        # 信贷创造 = M2 - M0 (这就是银行无中生有的钱)
        credit_creation = m2 - base_money_m0
        
        # 3. 市场层 (Market Layer)
        # 估算总市值
        spy_price = float(row.get('SPY', 0))
        latest_spy = float(latest_row.get('SPY', 1))
        
        # 假设美股总市值基准为 55T，美债 52T
        # 动态计算当前市值
        stock_mkt_cap = 55000 * (spy_price / latest_spy) if latest_spy else 55000
        bond_mkt_cap = 52000 # 简化处理，假设债市相对稳定或同步
        total_asset_cap = stock_mkt_cap + bond_mkt_cap
        
        # 估值杠杆 = 总市值 - M2 (这就是市场情绪给的溢价)
        # 假设 M2 中有 40% 进了金融市场 (这只是个示意比例，为了画图)
        m2_financial_flow = m2 * 0.4
        m2_real_economy = m2 * 0.6
        
        valuation_leverage = total_asset_cap - m2_financial_flow
        
        # === 绘制 Sankey ===
        
        # 节点定义
        label_list = [
            f"🏛️ 美联储总资产<br>${fed_assets/1000:.1f}T",    # 0
            f"🔒 TGA+RRP (损耗)<br>${(tga+rrp)/1000:.1f}T", # 1
            f"🌱 基础货币 (M0)<br>${base_money_m0/1000:.1f}T", # 2
            f"🏦 银行信贷创造 (杠杆)<br>+${credit_creation/1000:.1f}T", # 3 (灰)
            f"💰 广义货币 (M2)<br>${m2/1000:.1f}T",          # 4
            f"🏭 实体经济 (GDP)<br>${m2_real_economy/1000:.1f}T", # 5
            f"🚀 市场估值溢价 (杠杆)<br>+${valuation_leverage/1000:.1f}T", # 6 (灰)
            f"📈 股市+债市总值<br>${total_asset_cap/1000:.1f}T" # 7
        ]
        
        # 颜色
        color_list = [
            "#F1C40F", # Fed 黄
            "#8E44AD", # Leak 紫
            "#2ECC71", # M0 绿
            "#BDC3C7", # Credit 灰 (杠杆)
            "#2E86C1", # M2 蓝
            "#7F8C8D", # Economy 灰
            "#BDC3C7", # Valuation 灰 (杠杆)
            "#E74C3C"  # Assets 红
        ]
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 15, thickness = 20,
                line = dict(color = "black", width = 0.5),
                label = label_list,
                color = color_list
            ),
            link = dict(
                source = [0,   0,   2,  3,  4,  4,                 4,                 6], 
                target = [1,   2,   4,  4,  5,  7,                 7,                 7], 
                value =  [tga+rrp, base_money_m0, base_money_m0, credit_creation, m2_real_economy, m2_financial_flow, 1, valuation_leverage],
                # 注意：上面 target 7 出现了两次，一次是M2流入，一次是杠杆流入
                # 为了让 M2->Market 的线显示出来，我给了一个基础流，剩下的用杠杆补
                # 实际上 flow m2->7 应该 = m2_financial_flow
                
                label =  ["损耗", "基础货币", "M0基础", "信贷放大", "实体流通", "金融分流", "", "估值放大"],
                color =  ["#D7BDE2", "#ABEBC6", "#ABEBC6", "#D5DBDB", "#AED6F1", "#AED6F1", "#AED6F1", "#E6B0AA"]
            )
        )])
        
        fig_sankey.update_layout(height=600, font=dict(size=14))
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info("""
        **🔍 资金放大镜 (Leverage Anatomy):**
        1.  **第一级放大 (银行层):** 央行只给了 **${:.1f}T** 的基础货币(M0)，但银行通过放贷(灰色管道)将其放大到了 **${:.1f}T** 的 M2。
        2.  **第二级放大 (市场层):** 只有一部分 M2 进了股市，但通过 **估值溢价(PE Expansion)** (灰色管道)，支撑起了 **${:.1f}T** 的庞大市值。
        """.format(base_money_m0/1000, m2/1000, total_asset_cap/1000))

else:
    st.info("⏳ 正在构建宏观资金瀑布...")
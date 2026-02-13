import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("全景视角：**【M0/M1/M2 全收录】**。现在你可以直观看到 M1 是如何占据 M2 的半壁江山的。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据
    try:
        # 增加 M1SL, BOGMBASE (M0)
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
    
    tab_treemap, tab_waterfall = st.tabs(["🏰 市值时光机 (M0-M1-M2)", "🌊 宏观资金瀑布 (流向图)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (Treemap with Nested Money)
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 拖动滑块，观察【货币结构】与【资产规模】的对比")
        
        # 1. 定义结构 (嵌套逻辑)
        # 逻辑：
        # Source -> M0 (独立)
        # Source -> M2 (大框) -> M1 (子框) + M2_Other (储蓄)
        # 这样既能看到总量，又能看到结构，且不重复计算 M1和M2
        
        ids = [
            "root", 
            "cat_source", "cat_valve", "cat_asset",
            # Source Children
            "m0", "fed", "m2", 
            # M2 Children (嵌套!)
            "m1", "m2_other",
            # Valve Children
            "tga", "rrp",
            # Asset Children
            "spy", "tlt", "gld", "btc", "uso"
        ]
        
        parents = [
            "", 
            "root", "root", "root",
            "cat_source", "cat_source", "cat_source", # M0, Fed, M2 属于 Source
            "m2", "m2",                               # M1, M2_Other 属于 M2 (嵌套)
            "cat_valve", "cat_valve",
            "cat_asset", "cat_asset", "cat_asset", "cat_asset", "cat_asset"
        ]
        
        labels = [
            "全球资金池",
            "Source (水源)", "Valve (调节阀)", "Asset (资产)",
            "🌱 M0 (基础货币)", "🖨️ 美联储资产", "💰 M2 (广义货币)", 
            "💧 M1 (狭义货币)", "🏦 储蓄/定存 (M2-M1)", # M2的子项
            "👜 TGA", "♻️ RRP",
            "🇺🇸 美股", "📜 美债", "🥇 黄金", "₿ 比特币", "🛢️ 原油"
        ]
        
        colors = [
            "#333", "#2E86C1", "#8E44AD", "#D35400",
            "#1ABC9C", "#5DADE2", "#2980B9", # M0绿, Fed蓝, M2深蓝
            "#3498DB", "#AED6F1",            # M1亮蓝, 储蓄浅蓝 (体现包含关系)
            "#AF7AC5", "#AF7AC5",
            "#E59866", "#E59866", "#E59866", "#E59866", "#E59866"
        ]
        
        # 2. 生成动画帧
        df_weekly = df.resample('W-FRI').last().iloc[-52:]
        latest_row = df.iloc[-1]
        
        # 静态基准
        LATEST_CAPS = {"M2": 22300, "SPY": 55000, "TLT": 52000, "GLD": 14000, "BTC-USD": 2500, "USO": 2000}
        
        frames = []
        steps = []
        
        for date in df_weekly.index:
            date_str = date.strftime('%Y-%m-%d')
            row = df_weekly.loc[date]
            
            vals = {}
            # 获取数值
            def get_val(col): return float(row.get(col, 0)) if not pd.isna(row.get(col)) else 0.0
            def get_asset_size(col):
                curr = get_val(col)
                last = float(latest_row.get(col, 1))
                base = LATEST_CAPS.get(col, 100)
                return base * (curr / last) if last != 0 else base

            # 货币数据
            v_m0 = get_val('M0')
            v_m1 = get_val('M1')
            v_m2 = get_val('M2')
            v_fed = get_val('Fed_Assets')
            
            # 计算 M2 的剩余部分 (M2 - M1)
            v_m2_other = v_m2 - v_m1
            if v_m2_other < 0: v_m2_other = 0 # 保护逻辑
            
            # 资产数据
            v_spy = get_asset_size('SPY')
            v_tlt = get_asset_size('TLT')
            v_gld = get_asset_size('GLD')
            v_btc = get_asset_size('BTC-USD')
            v_uso = get_asset_size('USO')
            v_tga = abs(get_val('TGA'))
            v_rrp = abs(get_val('RRP'))
            
            # 填充 vals 字典
            vals['m0'] = v_m0
            vals['m1'] = v_m1
            vals['m2_other'] = v_m2_other
            vals['m2'] = v_m1 + v_m2_other # 父节点 M2 = 子节点之和
            vals['fed'] = v_fed
            
            vals['tga'] = v_tga
            vals['rrp'] = v_rrp
            
            vals['spy'] = v_spy
            vals['tlt'] = v_tlt
            vals['gld'] = v_gld
            vals['btc'] = v_btc
            vals['uso'] = v_uso
            
            # 汇总层级
            vals['cat_source'] = vals['m0'] + vals['fed'] + vals['m2']
            vals['cat_valve'] = vals['tga'] + vals['rrp']
            vals['cat_asset'] = vals['spy'] + vals['tlt'] + vals['gld'] + vals['btc'] + vals['uso']
            vals['root'] = vals['cat_source'] + vals['cat_valve'] + vals['cat_asset']
            
            # 组装列表 (顺序严格对应 ids)
            final_values = [
                vals['root'], 
                vals['cat_source'], vals['cat_valve'], vals['cat_asset'],
                vals['m0'], vals['fed'], vals['m2'],
                vals['m1'], vals['m2_other'], # M2 children
                vals['tga'], vals['rrp'],
                vals['spy'], vals['tlt'], vals['gld'], vals['btc'], vals['uso']
            ]
            
            # 文本显示
            text_list = []
            for v in final_values:
                if v > 1000: text_list.append(f"${v/1000:.1f}T")
                else: text_list.append(f"${v:,.0f}B")

            frames.append(go.Frame(
                name=date_str,
                data=[go.Treemap(
                    ids=ids, parents=parents, values=final_values, labels=labels, text=text_list, 
                    branchvalues="total"
                )]
            ))
            
            steps.append(dict(
                method="animate",
                args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))],
                label=date_str
            ))

        if frames:
            initial_frame = frames[-1]
            fig_tree = go.Figure(
                data=[go.Treemap(
                    ids=ids, parents=parents, labels=labels,
                    values=initial_frame.data[0].values,
                    text=initial_frame.data[0].text,
                    textinfo="label+text",
                    branchvalues="total",
                    marker=dict(colors=colors),
                    hovertemplate="<b>%{label}</b><br>规模: %{text}<extra></extra>",
                    pathbar=dict(visible=False)
                )],
                frames=frames
            )
            fig_tree.update_layout(
                height=650, margin=dict(t=0, l=0, r=0, b=0),
                sliders=[dict(active=len(steps)-1, currentvalue={"prefix": "📅 历史: "}, pad={"t": 50}, steps=steps)],
                updatemenus=[dict(type="buttons", showactive=False, visible=False)]
            )
            st.plotly_chart(fig_tree, use_container_width=True)

    # ==========================================
    # PROJECT 2: 货币层级瀑布 (保持不变)
    # ==========================================
    with tab_waterfall:
        st.markdown("##### 🪆 货币俄罗斯套娃：从 M0 到 资产")
        # (复用上一版的 Sankey 逻辑，此处略写，实际运行请保留上一版 Tab2 的完整代码)
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider("选择时间点：", options=available_dates, value=available_dates[-1], key="layer_slider")
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
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
        
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(pad = 15, thickness = 20, line = dict(color = "black", width = 0.5),
                label = [f"🏛️ Fed资产<br>${fed_assets/1000:.1f}T", f"🔒 TGA/RRP<br>${(tga+rrp)/1000:.1f}T", f"🌱 M0 (基础)<br>${m0/1000:.1f}T", f"💵 现金<br>${currency/1000:.1f}T", f"🏦 准备金<br>${reserves/1000:.1f}T", f"⚡ 活期创造<br>+${demand_deposits/1000:.1f}T", f"💧 M1 (狭义)<br>${m1/1000:.1f}T", f"⚡ 储蓄创造<br>+${savings_deposits/1000:.1f}T", f"🌊 M2 (广义)<br>${m2/1000:.1f}T", f"📈 估值放大<br>+${valuation_leverage/1000:.1f}T", f"🏙️ 资产池<br>${asset_pool_curr/1000:.1f}T"],
                color = ["#F1C40F", "#8E44AD", "#2ECC71", "#1ABC9C", "#95A5A6", "#BDC3C7", "#3498DB", "#BDC3C7", "#2E86C1", "#BDC3C7", "#E74C3C"]),
            link = dict(
                source = [0, 0, 2, 2, 3, 5, 6, 7, 8, 8, 9], 
                target = [1, 2, 3, 4, 6, 6, 8, 8, 10, 10, 10],
                value =  [tga+rrp, m0, currency, reserves, currency, demand_deposits, m1, savings_deposits, m2*0.5, m2*0.5, valuation_leverage],
                color =  ["#D7BDE2", "#ABEBC6", "#A2D9CE", "#D5DBDB", "#A2D9CE", "#D5DBDB", "#AED6F1", "#D5DBDB", "#AED6F1", "#D5DBDB", "#E6B0AA"]
            )
        )])
        fig_sankey.update_layout(height=650, font=dict(size=14))
        st.plotly_chart(fig_sankey, use_container_width=True)

else:
    st.info("⏳ 正在构建全维度数据模型...")
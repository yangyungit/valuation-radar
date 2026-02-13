import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("双重视角：**【市值】**看存量大小，**【液压】**看资金流向。请切换下方标签页。")

# --- 1. 统一数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观数据
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
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
        # 计算核心指标
        if 'WALCL' in df_all.columns: df_all['Fed_Assets'] = df_all['WALCL'] / 1000
        if 'WTREGEN' in df_all.columns: df_all['TGA'] = df_all['WTREGEN'] / 1000
        if 'RRPONTSYD' in df_all.columns: df_all['RRP'] = df_all['RRPONTSYD']
        if 'M2SL' in df_all.columns: df_all['M2'] = df_all['M2SL']
        
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # 创建两个独立的标签页
    tab_treemap, tab_sankey = st.tabs(["🏰 市值时光机 (存量)", "🌊 宏观液压图 (流量)"])
    
    # ==========================================
    # PROJECT 1: 市值时光机 (Treemap Animation)
    # ==========================================
    with tab_treemap:
        st.markdown("##### 📅 拖动滑块，观察资产池的物理膨胀与收缩")
        
        # 1. 定义结构 (V5 手动挡逻辑)
        ids = [
            "root", 
            "cat_source", "cat_valve", "cat_asset",
            "m2", "fed", "nl",
            "tga", "rrp",
            "spy", "tlt", "gld", "btc", "uso"
        ]
        parents = [
            "", 
            "root", "root", "root",
            "cat_source", "cat_source", "cat_source",
            "cat_valve", "cat_valve",
            "cat_asset", "cat_asset", "cat_asset", "cat_asset", "cat_asset"
        ]
        labels = [
            "全球资金池",
            "Source (水源)", "Valve (调节阀)", "Asset (资产)",
            "💰 M2", "🖨️ 美联储", "🏦 净流动性",
            "👜 TGA", "♻️ RRP",
            "🇺🇸 美股", "📜 美债", "🥇 黄金", "₿ 比特币", "🛢️ 原油"
        ]
        colors = [
            "#333", "#2E86C1", "#8E44AD", "#D35400",
            "#5DADE2", "#5DADE2", "#5DADE2",
            "#AF7AC5", "#AF7AC5",
            "#E59866", "#E59866", "#E59866", "#E59866", "#E59866"
        ]
        
        # 2. 生成动画帧
        df_weekly = df.resample('W-FRI').last().iloc[-52:]
        latest_row = df.iloc[-1]
        
        LATEST_CAPS = {"M2": 22300, "SPY": 55000, "TLT": 52000, "GLD": 14000, "BTC-USD": 2500, "USO": 2000}
        
        frames = []
        steps = []
        
        for date in df_weekly.index:
            date_str = date.strftime('%Y-%m-%d')
            row = df_weekly.loc[date]
            
            # 动态市值计算
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
            vals['nl'] = get_size('Net_Liquidity', True)
            vals['tga'] = get_size('TGA', True)
            vals['rrp'] = get_size('RRP', True)
            vals['spy'] = get_size('SPY', False)
            vals['tlt'] = get_size('TLT', False)
            vals['gld'] = get_size('GLD', False)
            vals['btc'] = get_size('BTC-USD', False)
            vals['uso'] = get_size('USO', False)
            
            # 手动汇总 (Accountant Fix)
            vals['cat_source'] = vals['m2'] + vals['fed'] + vals['nl']
            vals['cat_valve'] = vals['tga'] + vals['rrp']
            vals['cat_asset'] = vals['spy'] + vals['tlt'] + vals['gld'] + vals['btc'] + vals['uso']
            vals['root'] = vals['cat_source'] + vals['cat_valve'] + vals['cat_asset']
            
            final_values = [
                vals['root'], vals['cat_source'], vals['cat_valve'], vals['cat_asset'],
                vals['m2'], vals['fed'], vals['nl'], vals['tga'], vals['rrp'],
                vals['spy'], vals['tlt'], vals['gld'], vals['btc'], vals['uso']
            ]
            
            text_list = [f"${v/1000:.1f}T" if v > 1000 else f"${v:,.0f}B" for v in final_values]

            frames.append(go.Frame(
                name=date_str,
                data=[go.Treemap(ids=ids, parents=parents, values=final_values, labels=labels, text=text_list, branchvalues="total")]
            ))
            
            steps.append(dict(
                method="animate",
                args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))],
                label=date_str
            ))

        # 3. 渲染 Treemap
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
    # PROJECT 2: 宏观液压图 (Sankey Diagram)
    # ==========================================
    with tab_sankey:
        st.markdown("##### 🌊 资金管道工视图：钱去哪了？")
        
        # 独立的滑块控制 (服务端控制，保证逻辑清晰)
        available_dates = df_weekly.index.strftime('%Y-%m-%d').tolist()
        sankey_date_str = st.select_slider(
            "选择观测时间点：", 
            options=available_dates, 
            value=available_dates[-1],
            key="sankey_slider"
        )
        
        # 计算逻辑
        curr_date = pd.to_datetime(sankey_date_str)
        idx = df.index.get_indexer([curr_date], method='pad')[0]
        row = df.iloc[idx]
        
        fed = float(row.get('Fed_Assets', 0))
        tga = float(row.get('TGA', 0))
        rrp = float(row.get('RRP', 0))
        # 强制配平：Net Liq = Fed - TGA - RRP (忽略其他细项误差)
        net_liq = fed - tga - rrp
        if net_liq < 0: net_liq = 0 # 防止极端数据错误
        
        # 绘图
        fig_sankey = go.Figure(data=[go.Sankey(
            node = dict(
                pad = 20, thickness = 30,
                line = dict(color = "black", width = 0.5),
                label = [
                    f"🏛️ 美联储资产<br>${fed/1000:.1f}T", 
                    f"🔒 TGA (被锁死)<br>${tga:.0f}B", 
                    f"💤 RRP (被锁死)<br>${rrp:.0f}B", 
                    f"💧 净流动性 (市场燃料)<br>${net_liq/1000:.1f}T"
                ],
                color = ["#F1C40F", "#8E44AD", "#2E86C1", "#2ECC71"]
            ),
            link = dict(
                source = [0, 0, 0], # 从 Fed 出发
                target = [1, 2, 3], # 去向 TGA, RRP, NetLiq
                value =  [tga, rrp, net_liq],
                color =  ["#D7BDE2", "#AED6F1", "#ABEBC6"] # 浅色连接带
            )
        )])
        
        fig_sankey.update_layout(height=600, font=dict(size=16))
        st.plotly_chart(fig_sankey, use_container_width=True)
        
        st.info("""
        **💡 宏观交易员视角：**
        * 左边黄色的是 **总水源** (美联储印的钱)。
        * 中间紫色/蓝色的是 **"损耗"** (被财政部和逆回购工具截留的钱)。
        * 最下面绿色的才是 **"有效出水量"** (真正能把股市买上去的钱)。
        * **观察重点：** 当你拖动滑块，如果看到紫色(TGA)或蓝色(RRP)管道变细，通常意味着绿色(净流动性)管道变粗，利好股市。
        """)

else:
    st.info("⏳ 正在启动双引擎数据流...")
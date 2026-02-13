import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("🛡️ **数学级修复：** 采用【全链路自动求和】算法，确保父子节点数值严格匹配，根除白板与报错。")

# --- 1. 数据引擎 ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    # A. 宏观
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

    # B. 资产
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
        cols = ['Fed_Assets', 'TGA', 'RRP']
        if all(col in df_all.columns for col in cols):
            df_all['Net_Liquidity'] = df_all['Fed_Assets'] - df_all['TGA'] - df_all['RRP']
            
    return df_all

# --- 2. 页面逻辑 ---
df = get_all_data()

if not df.empty and 'Net_Liquidity' in df.columns:
    
    # === A. 定义严谨的树状结构 ===
    # 必须保证 IDs 和 Parents 一一对应
    
    # 1. 节点 ID 定义
    ids = [
        "root",                       # 0. 根
        "cat_source", "cat_valve", "cat_asset", # 1. 三大分类
        "m2", "fed", "nl",            # 2. Source 下的子节点
        "tga", "rrp",                 # 3. Valve 下的子节点
        "spy", "tlt", "gld", "btc"    # 4. Asset 下的子节点
    ]
    
    # 2. 父节点定义 (族谱)
    parents = [
        "",                           # root 没爸爸
        "root", "root", "root",       # 分类归 root 管
        "cat_source", "cat_source", "cat_source",
        "cat_valve", "cat_valve",
        "cat_asset", "cat_asset", "cat_asset", "cat_asset"
    ]
    
    # 3. 标签定义
    labels = [
        "全球资金池",
        "Source (水源)", "Valve (调节阀)", "Asset (资产)",
        "💰 M2", "🖨️ 美联储", "🏦 净流动性",
        "👜 TGA", "♻️ RRP",
        "🇺🇸 美股", "📜 美债", "🥇 黄金", "₿ 比特币"
    ]

    # 4. 颜色定义 (手动指定，防止闪烁)
    # 对应上面的 ids 顺序
    colors = [
        "#333333",                    # root (黑)
        "#2E86C1", "#8E44AD", "#D35400", # 蓝、紫、橙
        "#5DADE2", "#5DADE2", "#5DADE2", # Source 浅蓝
        "#AF7AC5", "#AF7AC5",            # Valve 浅紫
        "#E59866", "#E59866", "#E59866", "#E59866" # Asset 浅橙
    ]

    # === B. 构建每一帧的数据 (The Accountant Logic) ===
    df_weekly = df.resample('W-FRI').last().iloc[-52:]
    latest_row = df.iloc[-1]
    
    # 基础市值锚点
    LATEST_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500
    }
    
    frames = []
    steps = []
    
    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        row = df_weekly.loc[date]
        
        # --- 1. 计算叶子节点数值 (Leaf Values) ---
        vals = {}
        
        # Helper: 获取市值 (Dynamic Size)
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
        
        # --- 2. 计算父节点数值 (Aggregations) ---
        # 关键修复：父节点的值必须等于子节点之和！
        vals['cat_source'] = vals['m2'] + vals['fed'] + vals['nl']
        vals['cat_valve'] = vals['tga'] + vals['rrp']
        vals['cat_asset'] = vals['spy'] + vals['tlt'] + vals['gld'] + vals['btc']
        vals['root'] = vals['cat_source'] + vals['cat_valve'] + vals['cat_asset']
        
        # --- 3. 组装最终 Values 列表 ---
        # 顺序必须严格对应 ids
        final_values = [
            vals['root'],
            vals['cat_source'], vals['cat_valve'], vals['cat_asset'],
            vals['m2'], vals['fed'], vals['nl'],
            vals['tga'], vals['rrp'],
            vals['spy'], vals['tlt'], vals['gld'], vals['btc']
        ]
        
        # 构建 Display Text
        text_list = []
        for v in final_values:
            disp = f"${v:,.0f}B"
            if v > 1000: disp = f"${v/1000:.1f}T"
            text_list.append(disp)

        # 创建帧
        frames.append(go.Frame(
            name=date_str,
            data=[go.Treemap(
                ids=ids,
                parents=parents,
                values=final_values,
                labels=labels,
                text=text_list,
                textinfo="label+text",
                branchvalues="total", # <--- 现在敢用 total 了，因为账平了
                marker=dict(colors=colors), # 颜色锁定
                hovertemplate="<b>%{label}</b><br>规模: %{text}<extra></extra>"
            )]
        ))
        
        steps.append(dict(
            method="animate",
            args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))],
            label=date_str
        ))

    # === C. 初始化图表 ===
    # 用第一帧做底
    initial_frame = frames[-1] # 用最新一帧做初始显示
    
    fig = go.Figure(
        data=[go.Treemap(
            ids=ids,
            parents=parents,
            values=initial_frame.data[0].values,
            labels=labels,
            text=initial_frame.data[0].text,
            textinfo="label+text",
            branchvalues="total",
            marker=dict(colors=colors),
            hovertemplate="<b>%{label}</b><br>规模: %{text}<extra></extra>",
            pathbar=dict(visible=False)
        )],
        frames=frames
    )

    fig.update_layout(
        height=700,
        margin=dict(t=0, l=0, r=0, b=0),
        sliders=[dict(
            active=len(steps) - 1,
            currentvalue={"prefix": "📅 历史: ", "font": {"size": 20}},
            pad={"t": 50},
            steps=steps
        )],
        updatemenus=[dict(type="buttons", showactive=False, visible=False)]
    )

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ 时光机内核 (V5 手动挡) 已加载。数据严丝合缝，请拖动体验。")

else:
    st.info("⏳ 数据引擎启动中...")
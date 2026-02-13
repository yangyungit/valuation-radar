import streamlit as st
import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
import plotly.graph_objects as go # <--- 切换核心库
from datetime import datetime, timedelta

st.set_page_config(page_title="全球流动性时光机", layout="wide")

st.title("💸 全球流动性时光机 (Liquidity Time Machine)")
st.caption("🛠️ **工程级修复：** 切换至 Graph Objects 底层引擎，强制锁定树状结构，根除 TypeError。")

# --- 1. 数据引擎 (保持不变) ---
@st.cache_data(ttl=3600*4)
def get_all_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730) 
    
    try:
        macro_codes = ['WALCL', 'WTREGEN', 'RRPONTSYD', 'M2SL']
        df_macro = web.DataReader(macro_codes, 'fred', start_date, end_date)
        df_macro = df_macro.resample('D').ffill()
    except:
        df_macro = pd.DataFrame()

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
    
    # === A. 定义静态树状结构 (Static Hierarchy) ===
    # 这是手动挡的核心：ID 永远不变，只有 Values 在变
    # 结构：Root -> [Source, Valve, Asset] -> [Leaves...]
    
    # 节点 ID 映射
    ids = [
        "root", 
        "cat_src", "cat_vlv", "cat_ast",
        "m2", "fed", "nl", "tga", "rrp", "spy", "tlt", "gld", "btc"
    ]
    
    # 节点显示名称
    labels = [
        "全球资金池",
        "Source (水源)", "Valve (调节阀)", "Asset (资产)",
        "💰 M2 货币", "🖨️ 美联储资产", "🏦 净流动性",
        "👜 财政部 TGA", "♻️ 逆回购 RRP",
        "🇺🇸 美股", "📜 美债", "🥇 黄金", "₿ 比特币"
    ]
    
    # 父节点 ID (定义层级关系)
    parents = [
        "", 
        "root", "root", "root",
        "cat_src", "cat_src", "cat_src",
        "cat_vlv", "cat_vlv",
        "cat_ast", "cat_ast", "cat_ast", "cat_ast"
    ]
    
    # 映射列名到叶子节点
    leaf_map = {
        "m2": "M2", "fed": "Fed_Assets", "nl": "Net_Liquidity",
        "tga": "TGA", "rrp": "RRP",
        "spy": "SPY", "tlt": "TLT", "gld": "GLD", "btc": "BTC-USD"
    }
    
    # 基础市值 (用于动态伸缩)
    LATEST_CAPS = {
        "M2": 22300, "SPY": 55000, "TLT": 52000, 
        "GLD": 14000, "BTC-USD": 2500
    }

    # === B. 构建动画帧 (Frames) ===
    df_weekly = df.resample('W-FRI').last().iloc[-52:]
    latest_row = df.iloc[-1]
    
    frames = []
    steps = [] # 滑块步骤
    
    for date in df_weekly.index:
        date_str = date.strftime('%Y-%m-%d')
        row = df_weekly.loc[date]
        
        # 找前值
        prev_date = date - timedelta(days=30)
        idx_prev = df.index.get_indexer([prev_date], method='pad')[0]
        row_prev = df.iloc[idx_prev]
        
        # 构建每一帧的 Values 和 Colors
        # 注意：顺序必须严格对应上面的 `ids` 列表！
        frame_values = [0, 0, 0, 0] # 前4个是父节点，设为0让Plotly自动求和
        frame_colors = [0, 0, 0, 0] # 父节点颜色中性
        frame_text = ["", "", "", ""]
        
        # 遍历叶子节点
        for node_id in ids[4:]:
            col = leaf_map.get(node_id)
            if not col: 
                frame_values.append(0.1)
                frame_colors.append(0)
                frame_text.append("")
                continue
                
            # 取值
            val_curr = float(row.get(col, 0))
            val_prev = float(row_prev.get(col, 0))
            val_latest = float(latest_row.get(col, 1))
            
            # 计算涨跌
            pct = 0
            if val_prev != 0: pct = (val_curr - val_prev) / val_prev * 100
            
            # 计算 Size
            size = 1.0
            if col in ['M2', 'Fed_Assets', 'Net_Liquidity', 'TGA', 'RRP']:
                size = abs(val_curr)
            else:
                base = LATEST_CAPS.get(col, 100)
                if val_latest != 0: size = base * (val_curr / val_latest)
                else: size = base
                
            # 文本
            disp = f"${val_curr:,.0f}B"
            if size > 1000: disp = f"${size/1000:.1f}T"
            if col in ['M2', 'Fed_Assets', 'Net_Liquidity'] and val_curr > 1000: 
                disp = f"${val_curr/1000:.1f}T"
            
            hover_txt = f"{labels[ids.index(node_id)]}<br>{disp}<br>30d: {pct:.2f}%"

            frame_values.append(max(size, 0.1))
            frame_colors.append(pct)
            frame_text.append(hover_txt)
            
        # 创建 Frame 对象
        frames.append(go.Frame(
            name=date_str,
            data=[go.Treemap(
                ids=ids,
                values=frame_values,
                marker=dict(colors=frame_colors),
                customdata=frame_text, # 把文本传进去
                hovertemplate="%{customdata}<extra></extra>"
            )]
        ))
        
        steps.append(dict(
            method="animate",
            args=[[date_str], dict(mode="immediate", frame=dict(duration=300, redraw=True), transition=dict(duration=300))],
            label=date_str
        ))

    # === C. 初始化图表 ===
    # 使用最后一帧的数据作为初始状态
    initial_frame = frames[-1]
    
    fig = go.Figure(
        data=[go.Treemap(
            ids=ids,
            labels=labels,
            parents=parents,
            values=initial_frame.data[0].values,
            marker=dict(
                colors=initial_frame.data[0].marker.colors,
                colorscale=['#FF4B4B', '#1E1E1E', '#09AB3B'],
                cmid=0,
                showscale=True,
                colorbar=dict(title="30天涨跌%")
            ),
            branchvalues="total", # 关键：让子节点填满父节点
            texttemplate="<b>%{label}</b><br>%{value:.2s}", # 简略显示
            hovertemplate="%{customdata}<extra></extra>",
            customdata=initial_frame.data[0].customdata,
            pathbar=dict(visible=False) # 隐藏顶部面包屑
        )],
        frames=frames
    )

    # === D. 配置滑块控件 ===
    fig.update_layout(
        height=700,
        margin=dict(t=10, l=10, r=10, b=10),
        sliders=[dict(
            active=len(steps) - 1,
            currentvalue={"prefix": "📅 历史回放: "},
            pad={"t": 50},
            steps=steps
        )],
        updatemenus=[dict(type="buttons", showactive=False, visible=False)] # 隐藏播放按钮
    )

    st.plotly_chart(fig, use_container_width=True)
    st.success("✅ 时光机内核已重构。底层架构稳定，请拖动滑块。")

else:
    st.info("⏳ 正在初始化...")
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 资产池架构 (分层设计) ---
st.set_page_config(page_title="宏观雷达 (显微镜版)", layout="wide")

# 层级 1: 全球宏观 (只看指数/ETF/大类)
MACRO_ASSETS = {
    "标普500": "SPY", "纳指100": "QQQ", "罗素小盘": "IWM",
    "中概互联": "KWEB", "中国大盘": "FXI", "日本股市": "EWJ",
    "印度股市": "INDA", "越南股市": "VNM", "欧洲股市": "VGK",
    "黄金": "GLD", "白银": "SLV", "铜矿": "COPX",
    "原油": "USO", "天然气": "UNG", "美元指数": "UUP", 
    "半导体": "SMH", "科技": "XLK", "金融": "XLF",
    "能源": "XLE", "医疗": "XLV", "工业": "XLI",
    "比特币": "BTC-USD", "以太坊": "ETH-USD", "20年美债": "TLT"
}

# 层级 2: 细分赛道 (龙头拆解)
SECTOR_DRILLDOWN = {
    "🤖 拆解：半导体 & AI": {
        "英伟达 (算力王)": "NVDA", "台积电 (代工王)": "TSM",
        "博通 (网络)": "AVGO", "AMD (老二)": "AMD",
        "英特尔 (老兵)": "INTC", "美光 (存储)": "MU",
        "ARM (架构)": "ARM", "超微电脑 (服务器)": "SMCI",
        "ASML (光刻机)": "ASML", "半导体指数(基准)": "SMH"
    },
    "🐉 拆解：中国核心资产": {
        "腾讯 (港股)": "0700.HK", "阿里 (电商)": "BABA",
        "拼多多 (卷王)": "PDD", "美团 (本地)": "3690.HK",
        "京东 (物流)": "JD", "百度 (AI)": "BIDU",
        "网易 (游戏)": "NTES", "携程 (旅游)": "TCOM",
        "贝壳 (房产)": "BEKE", "中概互联(基准)": "KWEB"
    },
    "bf 拆解：加密货币": {
        "比特币 (大饼)": "BTC-USD", "以太坊 (二饼)": "ETH-USD",
        "Solana (新贵)": "SOL-USD", "BNB (平台)": "BNB-USD",
        "XRP (瑞波)": "XRP-USD", "Dogecoin (狗)": "DOGE-USD",
        "Cardano": "ADA-USD", "Avalanche": "AVAX-USD",
        "Chainlink": "LINK-USD", "纳指(基准)": "QQQ"
    },
    "🛢️ 拆解：大宗与资源": {
        "黄金 (避险)": "GLD", "白银 (工业)": "SLV",
        "铜矿 (周期)": "COPX", "原油 (能源)": "USO",
        "天然气 (波动)": "UNG", "铀矿 (核能)": "URA",
        "锂矿 (电池)": "LIT", "农业 (粮食)": "DBA",
        "稀土 (战略)": "REMX", "美元(基准)": "UUP"
    }
}

# --- 2. 侧边栏：显微镜控制台 ---
with st.sidebar:
    st.header("🔬 显微镜控制台")
    view_mode = st.radio(
        "选择观测层级",
        ["🌍 全球宏观 (上帝视角)"] + list(SECTOR_DRILLDOWN.keys()),
        index=0
    )
    
    # 动态决定用哪个资产池
    if view_mode == "🌍 全球宏观 (上帝视角)":
        CURRENT_ASSETS = MACRO_ASSETS
        st.info("当前模式：对比全球大类资产的轮动。")
    else:
        CURRENT_ASSETS = SECTOR_DRILLDOWN[view_mode]
        st.warning(f"当前模式：正在深入 {view_mode} 内部，对比龙头强弱。")

# --- 3. 核心引擎 (通用版) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers_dict):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*11)
    
    display_years = 10
    rolling_window = 252 
    
    # 动态显示状态
    status_text = st.empty()
    status_text.text(f"📥 正在拉取 {len(tickers_dict)} 个标的数据...")
    
    try:
        # 提取代码列表
        symbol_list = list(tickers_dict.values())
        data = yf.download(symbol_list, start=start_date, end=end_date, progress=False, auto_adjust=True)
        
        # 兼容性处理：如果只下载一个标的，yf返回的格式不同
        if len(symbol_list) == 1:
            raw_close = data[['Close']] # 保持DataFrame格式
            raw_volume = data[['Volume']]
            # 重命名列以匹配多标的格式
            raw_close.columns = symbol_list
            raw_volume.columns = symbol_list
        else:
            raw_close = data['Close']
            raw_volume = data['Volume']
            
    except Exception as e:
        return pd.DataFrame() 
    
    status_text.text("⚡ 正在计算相对强弱与情绪...")
    
    processed_dfs = []
    
    for name, ticker in tickers_dict.items():
        try:
            if ticker not in raw_close.columns: continue
            
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            
            # 允许稍短一点的数据进入（为了兼容新上市的龙头）
            if len(series_price) < rolling_window + 20: continue

            price_weekly = series_price.resample('W-FRI').last()
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index
            
            for date in display_dates:
                # Rolling Window
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.8: continue # 稍微放宽要求
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                v_mean = window_vol.mean()
                v_std = window_vol.std()
                
                if p_std == 0: continue

                # Z-Score
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                # Momentum (4 Weeks)
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0
                
                # Vol Z-Score
                vol_val = vol_weekly.loc[date]
                vol_z = (vol_val - v_mean) / v_std if v_std > 0 else 0
                
                # 气泡大小
                size_metric = max(5, min(10 + (vol_z * 8), 60))
                
                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'), 
                    "Name": name,
                    "Z-Score": round(z_score, 2),
                    "Momentum": round(momentum, 2),
                    "Vol_Z": round(vol_z, 2),
                    "Price": round(price_val, 2),
                    "Size": size_metric 
                })
        except: continue

    status_text.empty()
    full_df = pd.DataFrame(processed_dfs)
    if not full_df.empty:
        full_df = full_df.sort_values(by="Date")
    return full_df

# --- 4. 主界面渲染 ---
st.title(f"🔭 宏观雷达: {view_mode}")

# 这一步是关键：根据用户的选择，重新运行数据引擎
df_anim = get_market_data(CURRENT_ASSETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    
    range_x = [-4.5, 4.5]
    range_y = [-50, 60] 

    fig = px.scatter(
        df_anim, 
        x="Z-Score", y="Momentum", 
        animation_frame="Date", animation_group="Name", 
        text="Name", hover_name="Name",
        hover_data=["Price", "Vol_Z"],
        color="Momentum", size="Size", size_max=60, 
        range_x=range_x, range_y=range_y, 
        color_continuous_scale="RdYlGn", range_color=[-20, 40],
        title=""
    )

    fig.update_traces(cliponaxis=False, textposition='top center', marker=dict(line=dict(width=1, color='black')))
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 拥挤/主升", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 爆发/抢筹", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 冷宫/吸筹", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 崩盘/主跌", showarrow=False, font=dict(color="orange"))

    # 动画控件
    settings_normal = dict(frame=dict(duration=200, redraw=True), fromcurrent=True)
    settings_fast = dict(frame=dict(duration=50, redraw=True), fromcurrent=True)

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.15,
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[all_dates[::-1], settings_fast]),
            dict(label="▶️ 播放", method="animate", args=[None, settings_normal]),
            dict(label="🐢 慢放", method="animate", args=[None, dict(frame=dict(duration=800, redraw=True), fromcurrent=True)]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    fig.layout.sliders[0].currentvalue.prefix = "" 
    fig.layout.sliders[0].currentvalue.font.size = 20
    fig.layout.sliders[0].pad = {"t": 50} 
    
    fig.update_layout(
        height=750, template="plotly_dark",
        margin=dict(l=40, r=40, t=20, b=100),
        xaxis=dict(visible=True, showticklabels=True, title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->"),
        yaxis=dict(title="<-- 资金流出  |  资金流入 -->")
    )

    st.plotly_chart(fig, use_container_width=True)

    # 局限性说明
    with st.expander("⚠️ 局限性与方法论说明 (Limitations & Methodology)", expanded=False):
        st.markdown("""
        * **数据源：** 使用 Yahoo Finance，部分中概股或加密货币数据可能存在延迟。
        * **显微镜模式：** 当进入细分板块时，"基准"依然是该资产自身的历史均值，而非板块指数。这有助于发现板块内部的 Alpha（谁比谁更强）。
        """)

    # 数据表格
    st.markdown(f"### 📊 {view_mode} - 最新快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    
    st.dataframe(
        df_latest[['Name', 'Z-Score', 'Momentum', 'Vol_Z', 'Price']]
        .sort_values(by="Z-Score", ascending=False)
        .style
        .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40) 
        .background_gradient(subset=['Vol_Z'], cmap='Blues', vmin=0, vmax=3),
        use_container_width=True
    )

else:
    st.info("💡 请在左侧选择观测层级，数据正在装填中...")

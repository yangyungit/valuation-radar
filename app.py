import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观雷达 (合成指数版)", layout="wide")

# --- 2. 定义资产池与合成组合 ---
# 纯净版资产池 (剔除以太坊，新增人民币汇率)
ASSETS = {
    # --- 全球核心指数 ---
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "中概互联": "KWEB",
    "中国大盘": "FXI",
    "日本股市": "EWJ",
    "印度股市": "INDA",
    "欧洲股市": "VGK",
    "越南股市": "VNM",

    # --- 细分消费板块 ---
    "可选消费(XLY)": "XLY",
    "必选消费(XLP)": "XLP",
    "沃尔玛 (WMT)": "WMT",
    "好市多 (COST)": "COST",

    # --- 核心行业 ---
    "半导体": "SMH",
    "科技巨头": "XLK",
    "机器人": "BOTZ",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "房地产": "XLRE",
    "公用事业": "XLU",
    "军工": "ITA",
    "农业": "DBA",

    # --- 加密货币 ---
    "比特币": "BTC-USD",
    # (以太坊已移除)

    # --- 大宗商品 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "铀矿": "URA",

    # --- 利率与外汇 ---
    "美元指数": "UUP",
    "美元/人民币": "CNY=X",  # 新增：美元兑人民币汇率
    "日元": "FXY",
    "20年美债": "TLT",
    "高收益债": "HYG"
}

# 合成组合 (Basket): 后台下载成分股 -> 合成等权指数
CUSTOM_BASKETS = {
    "科技七姐妹": ["NVDA", "AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA"],
    "必选消费": ["WMT", "COST", "KO", "PG", "PEP"], # 沃尔玛, 好市多, 可乐, 宝洁, 百事
    "垃圾债": ["HYG", "JNK"] # 用两个ETF合成更稳
}

# --- 3. 核心引擎 (支持合成指数) ---
@st.cache_data(ttl=3600*12) 
def get_market_data(single_dict, basket_dict):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2.5) # 2.5年数据保证计算精度
    
    display_years = 1 
    rolling_window = 252 

    status_text = st.empty()
    status_text.text(f"📥 正在构建合成指数与宏观数据...")

    # 1. 收集所有需要下载的 Ticker (去重)
    all_tickers = list(single_dict.values())
    for tickers in basket_dict.values():
        all_tickers.extend(tickers)
    all_tickers = list(set(all_tickers))

    try:
        # 批量下载
        data = yf.download(all_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except:
        return pd.DataFrame()

    status_text.text("⚡ 正在合成 '七姐妹' 与 '消费精英' 指数...")

    # --- 数据处理与合成逻辑 ---
    processed_dfs = []
    
    # A. 处理单一资产
    check_list = list(SINGLE_ASSETS.items())
    # B. 处理合成资产 (这是关键一步)
    #    我们在内存中创建一个"虚拟"的价格序列
    for name, components in CUSTOM_BASKETS.items():
        # 获取成分股的日收益率
        valid_components = [t for t in components if t in raw_close.columns]
        if not valid_components: continue
        
        # 计算等权重收益率 (Equal Weighted Return)
        # 每天的涨跌幅 = 所有成分股涨跌幅的平均值
        basket_returns = raw_close[valid_components].pct_change().mean(axis=1)
        
        # 重新构建净值曲线 (假设初始值为100)
        # (1 + r1) * (1 + r2) ...
        synthetic_price = (1 + basket_returns).cumprod() * 100
        
        # 暂时把合成的价格塞进 raw_close (为了复用下面的逻辑，虽然有点hack但很高效)
        # 注意：这里我们不需要Volume，因为合成指数的Volume很难定义，我们暂设为0或平均
        raw_close[name] = synthetic_price
        raw_volume[name] = raw_volume[valid_components].mean(axis=1) # 简单的平均量
        
        # 把合成的名字加入待处理列表
        check_list.append((name, name))

    # --- 统一计算 Z-Score ---
    for name, ticker in check_list:
        try:
            # 如果是合成的，ticker就是name；如果是原始的，ticker就是代码
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            
            if len(series_price) < rolling_window + 20: continue

            price_weekly = series_price.resample('W-FRI').last()
            
            # 只有这里需要注意：合成指数的Volume没有太大意义，我们主要看价格位置
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index
            
            for date in display_dates:
                # Rolling Window
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.9: continue
                
                p_mean = window_price.mean()
                p_std = window_price.std()
                
                if p_std == 0: continue

                # Z-Score
                price_val = price_weekly.loc[date]
                z_score = (price_val - p_mean) / p_std
                
                # Momentum
                lookback_date = date - timedelta(weeks=4)
                try:
                    idx = series_price.index.searchsorted(lookback_date)
                    if idx < len(series_price) and idx >= 0:
                        price_prev = series_price.iloc[idx]
                        momentum = ((price_val - price_prev) / price_prev) * 100 if price_prev > 0 else 0
                    else: momentum = 0
                except: momentum = 0
                
                # Vol Z-Score
                if ticker in CUSTOM_BASKETS:
                    vol_z = 0 # 合成指数暂不显示量能异动，避免数据失真
                else:
                    v_mean = window_vol.mean()
                    v_std = window_vol.std()
                    vol_val = vol_weekly.loc[date]
                    vol_z = (vol_val - v_mean) / v_std if v_std > 0 else 0
                
                # 获取真实代码用于展示 (如果是合成的，展示成分股数量)
                display_ticker = ticker if ticker not in CUSTOM_BASKETS else f"Basket({len(CUSTOM_BASKETS[ticker])})"

                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'), 
                    "Name": name,
                    "Ticker": display_ticker, 
                    "Z-Score": round(z_score, 2),
                    "Momentum": round(momentum, 2),
                    "Vol_Z": round(vol_z, 2),
                    "Price": round(price_val, 2)
                })
        except: continue

    status_text.empty()
    full_df = pd.DataFrame(processed_dfs)
    if not full_df.empty:
        full_df = full_df.sort_values(by="Date")
    return full_df

# --- 4. 页面渲染 ---
st.title(f"🔭 宏观雷达 (精英合成版)")

df_anim = get_market_data(SINGLE_ASSETS, CUSTOM_BASKETS)

if not df_anim.empty:
    
    all_dates = sorted(df_anim['Date'].unique())
    range_x = [-4.0, 4.0]
    range_y = [-40, 50] 

    # 气泡图
    fig = px.scatter(
        df_anim, 
        x="Z-Score", y="Momentum", 
        animation_frame="Date", animation_group="Name", 
        text="Name", hover_name="Name",
        hover_data=["Ticker", "Price", "Vol_Z"], 
        color="Momentum", 
        range_x=range_x, range_y=range_y, 
        color_continuous_scale="RdYlGn", range_color=[-20, 40],
        title=""
    )

    fig.update_traces(
        cliponaxis=False, 
        textposition='top center', 
        marker=dict(size=14, line=dict(width=1, color='black'))
    )
    
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="gray")

    fig.add_annotation(x=0.95, y=0.95, xref="paper", yref="paper", text="🔥 强势/拥挤", showarrow=False, font=dict(color="red"))
    fig.add_annotation(x=0.05, y=0.95, xref="paper", yref="paper", text="💎 反转/启动", showarrow=False, font=dict(color="#00FF00"))
    fig.add_annotation(x=0.05, y=0.05, xref="paper", yref="paper", text="🧊 弱势/冷宫", showarrow=False, font=dict(color="gray"))
    fig.add_annotation(x=0.95, y=0.05, xref="paper", yref="paper", text="⚠️ 补跌/崩盘", showarrow=False, font=dict(color="orange"))

    settings_play = dict(frame=dict(duration=400, redraw=True), fromcurrent=True, transition=dict(duration=100))
    settings_rewind = dict(frame=dict(duration=100, redraw=True), fromcurrent=True, transition=dict(duration=0))

    fig.layout.updatemenus = [dict(
        type="buttons", showactive=False, direction="left", x=0.0, y=-0.15,
        buttons=[
            dict(label="⏪ 倒放", method="animate", args=[all_dates[::-1], settings_rewind]),
            dict(label="▶️ 正放", method="animate", args=[None, settings_play]),
            dict(label="⏸️ 暂停", method="animate", args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False))])
        ]
    )]

    fig.layout.sliders[0].active = len(all_dates) - 1
    fig.layout.sliders[0].currentvalue.prefix = "" 
    fig.layout.sliders[0].currentvalue.font.size = 20
    fig.layout.sliders[0].pad = {"t": 50} 
    
    fig.update_layout(
        height=750, template="plotly_dark",
        margin=dict(l=40, r=40, t=20, b=100),
        xaxis=dict(visible=True, showticklabels=True, title="<-- 便宜 (低 Z-Score)  |  昂贵 (高 Z-Score) -->"),
        yaxis=dict(title="<-- 资金流出  |  资金流入 -->")
    )

    st.plotly_chart(fig, width='stretch')

    with st.expander("⚠️ 合成指数说明 (Methodology)", expanded=False):
        st.markdown("""
        * **科技七姐妹:** 等权重合成 (NVDA, AAPL, MSFT, GOOG, AMZN, META, TSLA)。代表美股最强进攻力量。
        * **必选消费:** 等权重合成 (WMT, COST, KO, PG, PEP)。剔除了板块中的垃圾股，只看最强防御龙头。
        * **原理:** 我们在后台下载了这些个股的原始数据，实时计算它们的等权净值曲线，再将其放入宏观雷达进行对比。
        """)

    st.markdown("### 📊 最新数据快照")
    latest_date = df_anim['Date'].iloc[-1]
    df_latest = df_anim[df_anim['Date'] == latest_date]
    
    display_cols = ['Name', 'Ticker', 'Z-Score', 'Momentum', 'Vol_Z', 'Price']
    
    st.dataframe(
        df_latest[display_cols]
        .sort_values(by="Z-Score", ascending=False)
        .style
        .background_gradient(subset=['Momentum'], cmap='RdYlGn', vmin=-20, vmax=40) 
        .background_gradient(subset=['Vol_Z'], cmap='Blues', vmin=0, vmax=3),
        width='stretch'
    )

else:
    st.info("正在合成精英指数并获取数据...")
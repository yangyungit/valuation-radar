import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 配置与资产池 ---
st.set_page_config(page_title="宏观时光机 (Market Time Machine)", layout="wide")

ASSETS = {
    # --- 全球核心指数 ---
    "标普500": "SPY",
    "纳指100": "QQQ",
    "罗素小盘": "IWM",
    "中概互联": "KWEB",
    "中国大盘(FXI)": "FXI",
    "日本股市": "EWJ",
    "印度股市": "INDA",
    "欧洲股市": "VGK",
    "越南股市": "VNM",

    # --- 核心大宗与货币 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "美元指数": "UUP",
    "日元": "FXY",

    # --- 关键行业板块 ---
    "半导体": "SMH",
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "医疗": "XLV",
    "工业": "XLI",
    "房地产": "XLRE",
    "消费": "XLY",
    
    # --- 债券 ---
    "20年美债": "TLT",
    "高收益债": "HYG",

    # --- 另类与主题 ---
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",
    "人工智能": "BOTZ",
    "网络安全": "CIBR",
    "生物科技": "XBI",
    "军工": "ITA",
    "铀矿(核能)": "URA"
}

# --- 2. 数据处理核心逻辑 (时光机版) ---
@st.cache_data(ttl=3600)
def get_market_animation_data(tickers):
    animation_frames = []
    
    end_date = datetime.now()
    # 我们取过去 400 天的数据，为了计算一整年的动画
    start_date = end_date - timedelta(days=400) 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)
    count = 0

    # 预先下载所有数据以提高速度 (Batch Download)
    # yfinance支持一次下载多个ticker
    ticker_list = list(tickers.values())
    try:
        status_text.text("正在批量下载全市场历史数据...")
        raw_data = yf.download(ticker_list, start=start_date, end=end_date, progress=False)['Close']
    except Exception as e:
        return pd.DataFrame() # 失败返回空

    progress_bar.progress(0.3)
    status_text.text("正在构建时间序列模型...")

    # 对每一列（每一个资产）进行处理
    processed_dfs = []
    
    for name, ticker in tickers.items():
        try:
            if ticker not in raw_data.columns:
                continue
            
            series = raw_data[ticker].dropna()
            if len(series) < 260: continue

            # --- 核心技巧：重采样为"周" (Weekly) ---
            # 这样动画只有 52 帧，非常流畅，且过滤了单日噪音
            series_weekly = series.resample('W-FRI').last() 
            
            # 计算基准 (用过去一年的整体分布作为静态地图背景)
            # 这样坐标轴不会乱动，球在动
            base_mean = series.tail(252).mean()
            base_std = series.tail(252).std()

            # 遍历每一周，生成这一周的数据切片
            # 我们只生成最近 52 周（1年）的动画
            recent_weeks = series_weekly.tail(52)
            
            for date, price in recent_weeks.items():
                # 1. 计算当时的 Z-Score (相对于全年基准)
                # 注意：这里用的是固定基准，为了展示"绝对位置"的移动
                z_score = (price - base_mean) / base_std
                
                # 2. 计算当时的动量 (相对于那一天之前的 12 周/约3个月)
                # 我们需要回溯到原始数据去找 3个月前的价格
                lookback_date = date - timedelta(weeks=12)
                # 在原始数据中找最接近 lookback_date 的价格
                try:
                    # searchsorted 找最近的索引
                    idx = series.index.searchsorted(lookback_date)
                    if idx < len(series) and idx >= 0:
                        price_prev = series.iloc[idx]
                        momentum = ((price - price_prev) / price_prev) * 100
                    else:
                        momentum = 0
                except:
                    momentum = 0
                
                processed_dfs.append({
                    "Date": date.strftime('%Y-%m-%d'), # 转成字符串给滑块用
                    "Name": name,
                    "Ticker": ticker,
                    "Z-Score": round(z_score, 2),
                    "Momentum": round(momentum, 2),
                    "Price": round(price, 2),
                    "Size": 15 # 固定大小
                })
                
        except Exception as e:
            continue

    progress_bar.empty()
    status_text.empty()
    
    # 转换成大表格
    full_df = pd.DataFrame(processed_dfs)
    
    # 确保时间排序正确
    full_df = full_df.sort_values(by="Date")
    
    return full_df

# --- 3. 页面渲染 ---
tz = pytz.timezone('US/Eastern')
update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M EST')

st.title("🎢 宏观时光机 (Market Time Machine)")
st.caption(f"数据更新: {update_time} | 包含过去 52 周的动态演变 | 点击下方 ▶️ 播放")

df_anim = get_market_animation_data(ASSETS)

if not df_anim.empty:
    
    # --- 使用 Plotly Express 制作动画 ---
    # 这是一个非常强大的高层接口
    
    fig = px.scatter(
        df_anim, 
        x="Z-Score", 
        y="Momentum", 
        animation_frame="Date", # 核心：这就是时间轴
        animation_group="Name", # 核心：告诉它谁是谁，保证平滑过渡
        text="Name",
        hover_name="Name",
        hover_data=["Price", "Ticker"],
        color="Momentum", # 颜色随动量变化
        range_x=[-4.5, 4.5], # 锁定 X 轴范围，防止画面乱跳
        range_y=[-50, 60],   # 锁定 Y 轴范围
        color_continuous_scale="RdYlGn",
        range_color=[-20, 40], # 锁定颜色范围，防止闪烁
        title="点击播放键 ▶️ 回看过去一年资产轮动路径"
    )

    # 美化布局
    fig.update_traces(
        textposition='top center', 
        marker=dict(size=14, line=dict(width=1, color='black'))
    )
    
    # 画十字线
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="gray")
    fig.add_vline(x=0, line_width=1,

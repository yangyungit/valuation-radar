import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观雷达 (全领域覆盖版)", layout="wide")

# 纯净版资产池 (修正名称，补全板块)
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

    # --- 科技与制造 ---
    "半导体": "SMH",
    "科技行业": "XLK",
    "机器人": "BOTZ",     # 修正：去掉了AI，还原为机器人
    
    # --- 传统周期与防御 ---
    "金融": "XLF",
    "能源": "XLE",
    "工业": "XLI",
    "医疗": "XLV",
    "房地产": "XLRE",
    "消费": "XLY",
    "公用事业": "XLU",
    "军工": "ITA",         # 新增：军工板块
    "农业": "DBA",         # 新增：农业板块

    # --- 加密货币 ---
    "比特币": "BTC-USD",
    "以太坊": "ETH-USD",

    # --- 大宗商品 ---
    "黄金": "GLD",
    "白银": "SLV",
    "铜矿": "COPX",
    "原油": "USO",
    "天然气": "UNG",
    "铀矿": "URA",

    # --- 利率与外汇 ---
    "美元指数": "UUP",
    "日元": "FXY",
    "20年美债": "TLT",
    "高收益债": "HYG"
}

# --- 2. 核心数据引擎 ---
@st.cache_data(ttl=3600*12) 
def get_market_data(tickers):
    end_date = datetime.now()
    # 下载11年数据
    start_date = end_date - timedelta(days=365*11)
    
    display_years = 10
    rolling_window = 252 
    
    status_text = st.empty()
    status_text.text(f"📥 正在扫描全球全领域资产 (10年历史)...")
    
    try:
        data = yf.download(list(tickers.values()), start=start_date, end=end_date, progress=False, auto_adjust=True)
        raw_close = data['Close']
        raw_volume = data['Volume']
    except:
        return pd.DataFrame() 
    
    status_text.text("⚡ 正在清洗量价因子...")
    
    processed_dfs = []
    
    for name, ticker in tickers.items():
        try:
            if ticker not in raw_close.columns: continue
            
            series_price = raw_close[ticker].dropna()
            series_vol = raw_volume[ticker].dropna()
            
            # 部分ETF(如BOTZ)历史较短，只要够算Z-Score就允许进入
            if len(series_price) < rolling_window + 60: continue

            price_weekly = series_price.resample('W-FRI').last()
            vol_weekly = series_vol.resample('W-FRI').mean()
            
            target_start_date = end_date - timedelta(days=365 * display_years)
            display_dates = price_weekly[price_weekly.index >= target_start_date].index
            
            for date in display_dates:
                # Rolling 1 Year Window
                window_price = series_price.loc[:date].tail(rolling_window)
                window_vol = series_vol.loc[:date].tail(rolling_window)
                
                if len(window_price) < rolling_window * 0.9: continue
                
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
                vol_z = (vol_

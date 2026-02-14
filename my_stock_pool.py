# my_stock_pool.py
# 你的专属自选股池配置
# 格式: { "分组名": { "代码": "中文显示名" } }

MY_POOL = {
    "A (防守/稳健)": {
        "GLD": "黄金ETF",
        "WMT": "沃尔玛",
        "TJX": "TJX百货",
        "RSG": "共和废品",
        "LLY": "礼来制药",
        "COST": "好市多",
        "KO": "可口可乐",
        "V": "Visa",
        "BRK-B": "伯克希尔",
        "ISRG": "直觉外科",
        "LMT": "洛克希德",
        "WM": "废物管理",
        "JNJ": "强生",
        "LIN": "林德气体"
    },
    
    "B (核心/基石)": {
        "GOOGL": "谷歌",
        "MSFT": "微软",
        "AMZN": "亚马逊",
        "AAPL": "苹果",
        "PWR": "广达服务",
        "CACI": "CACI国际",
        "MNST": "怪兽饮料",
        "XOM": "埃克森美孚",
        "CVX": "雪佛龙",
        # 重复标的保留（代码会自动去重，不影响）：
        "COST": "好市多",
        "LLY": "礼来制药",
        "WM": "废物管理"
    },
    
    "C (时代之王)": {
        "TSLA": "特斯拉",
        "NVDA": "英伟达",
        "PLTR": "Palantir",
        "VRT": "维谛技术",
        "NOC": "诺斯罗普",
        "XAR": "航空国防ETF",
        "XLP": "必选消费ETF",
        "MS": "摩根士丹利",
        "GS": "高盛",
        "ANET": "Arista网络",
        "ETN": "伊顿电力",
        "BTC-USD": "比特币",
        "ETH-USD": "以太坊",  # 新增
        "GOLD": "巴里克黄金",
        # 重复标的保留：
        "LMT": "洛克希德"
    },
    
    "D (观察/潜力)": {
        # --- 贵金属/矿业 ---
        "FCX": "自由港铜金",
        "AG": "First Majestic",
        "HL": "赫克拉矿业",
        "BHP": "必和必拓",
        "VALE": "淡水河谷",
        "RIO": "力拓",
        
        # --- AI/科技 ---
        "MU": "美光科技",
        "SPIR": "Spire Global",
        "APPS": "Digital Turbine",
        "WDC": "西部数据",
        "NET": "Cloudflare",
        
        # --- 军工/太空 ---
        "ITA": "航空国防ETF",
        "KTOS": "Kratos防务",
        "BKR": "贝克休斯",
        "BAH": "博思艾伦",
        
        # --- 能源/铀矿 ---
        "TDW": "泰德威特",
        "TRGP": "Targa资源",
        "UEC": "铀能源公司",
        "CCJ": "Cameco铀矿",
        "URA": "铀矿ETF",
        
        # --- 消费/其他 ---
        "BTI": "英美烟草",
        "MO": "奥驰亚",
        "FIGS": "Figs医疗服饰"
    }
}
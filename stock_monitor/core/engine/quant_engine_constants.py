"""
量化引擎常量定义模块
将魔法数字集中管理，便于维护和调整
"""

# ====== 缓存相关 ======
CACHE_TTL_SECONDS = 60  # K 线缓存生存时间 (秒)
MAX_CACHE_SIZE = 500  # K 线缓存最大条目数
MAX_AVG_VOL_CACHE_AGE = 86400  # 5 日均量缓存最大年龄 (秒)

# ====== 数据量阈值 ======
MIN_DATA_POINTS_FOR_BB = 100  # 布林带收敛判断最少需要 100 个数据点
MIN_DATA_POINTS_FOR_MACD = 60  # MACD 底背离检测最少需要 60 个数据点 (window*2)
MIN_DATA_POINTS_FOR_RSI = 50  # RSI 计算最少数据点

# ====== 大单统计相关 ======
BIG_ORDER_THRESHOLD_AMOUNT = 500000  # 大单金额阈值 (元) - 基准值，适用于中盘股
BIG_ORDER_THRESHOLD_SMALL_CAP = 200000  # 小盘股大单阈值 (<100 亿市值)
BIG_ORDER_THRESHOLD_MID_CAP = 500000  # 中盘股大单阈值 (100-1000 亿市值)
BIG_ORDER_THRESHOLD_LARGE_CAP = 1000000  # 大盘股大单阈值 (>1000 亿市值)

# 市值分档界限 (元)
MARKET_CAP_SMALL_LIMIT = 10e9  # 小盘股上限 (100 亿)
MARKET_CAP_MID_LIMIT = 100e9  # 中盘股上限 (1000 亿)

MAX_TRANSACTION_FETCH = 1000000  # 交易记录获取上限 (安全熔断)
TRANSACTION_BATCH_SIZE = 2000  # 批量获取交易记录的批次大小
MIN_ORDER_VOLUME_HANDS = 100  # 最小统计手数

# ====== 时间阈值 ======
MARKET_OPEN_TIME = "09:15"  # 集合竞价开始时间
MARKET_TRADE_START_TIME = "09:25"  # 正式交易统计开始时间
EARLIEST_COMPENSATION_TIME = "09:35"  # 盘后补偿最早回溯时间
MARKET_CLOSE_HOUR = 15  # 收盘小时数

# ====== 技术指标参数 ======
MACD_WINDOW = 30  # MACD 底背离检测窗口
MACD_FAST_PERIOD = 12  # MACD 快线周期
MACD_SLOW_PERIOD = 26  # MACD 慢线周期
MACD_SIGNAL_PERIOD = 9  # MACD 信号线周期

BBAND_LOOKBACK = 100  # 布林带收敛回看周期
BBAND_STD_DEV = 2.0  # 布林带标准差倍数

RSI_PERIOD = 14  # RSI 计算周期
RSRS_THRESHOLD = 0.7  # RSRS Z-Score 强势阈值
RSRS_WEAK_THRESHOLD = -0.7  # RSRS Z-Score 弱势阈值

# ====== 周期映射 ======
FreqMap = {"15m": 1, "30m": 2, "60m": 3, "daily": 9}

TF_CHINESE_MAP = {
    "15m": "15 分钟",
    "30m": "30 分钟",
    "60m": "60 分钟",
    "daily": "日线",
}

# ====== 信号强度阈值 ======
SIGNAL_INTENSITY_HIGH = 0.8  # 高强度信号阈值
SIGNAL_INTENSITY_MEDIUM = 0.5  # 中等强度信号阈值
SIGNAL_COOLDOWN_MINUTES = 30  # 信号冷却期 (分钟)

# ====== 基本面筛选阈值 ======
MIN_MARKET_CAP = 1e9  # 最小市值 (元)
MAX_PE_RATIO = 100  # 最大市盈率
MAX_PB_RATIO = 10  # 最大市净率
MIN_ROE = 0.05  # 最小 ROE
MIN_OPERATING_PROFIT_GROWTH = -0.3  # 最小营业利润增长率

"""
配置键常量，避免硬编码字符串
"""


class ConfigKeys:
    """配置键常量定义"""

    # 用户自选股
    USER_STOCKS = "user_stocks"

    # 刷新间隔
    REFRESH_INTERVAL = "refresh_interval"

    # 量化相关
    QUANT_ENABLED = "quant_enabled"
    QUANT_SCAN_INTERVAL = "quant_scan_interval"  # 量化扫描间隔（秒）
    DAILY_REPORT_TIMES = "daily_report_times"  # 每日复盘触发时刻列表 ["HH:MM", ...]

    # 显示相关
    FONT_FAMILY = "font_family"
    FONT_SIZE = "font_size"
    TRANSPARENCY = "transparency"

    # 消息推送
    WECOM_WEBHOOK = "wecom_webhook"
    PUSH_MODE = "push_mode"
    WECOM_CORPID = "wecom_corpid"
    WECOM_CORPSECRET = "wecom_corpsecret"
    WECOM_AGENTID = "wecom_agentid"

    # 窗口位置
    WINDOW_POS = "window_pos"

    # 自动导出相关
    AUTO_EXPORT_EXCEL = "auto_export_excel"
    AUTO_CLOSE_EXPORT = "auto_close_export"  # 收盘时自动抓取全网数据

    # 任务栏行情条
    TASKBAR_QUOTE_ENABLED = "taskbar_quote_enabled"  # 是否启用任务栏行情条
    TASKBAR_CAROUSEL_INTERVAL = "taskbar_carousel_interval"  # 自动轮播间隔(秒)
    TASKBAR_PER_PAGE = "taskbar_per_page"  # 每页显示股票数
    TASKBAR_SHOW_PRICE = "taskbar_show_price"  # 是否显示价格
    TASKBAR_SHOW_CHANGE = "taskbar_show_change"  # 是否显示涨跌幅
    TASKBAR_SHOW_DARK_FLOW = "taskbar_show_dark_flow"  # 是否显示暗盘净流入

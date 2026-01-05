"""
UI常量模块
集中管理所有UI相关的魔法数字
"""


class UIConstants:
    """UI常量类 - 集中管理所有UI相关的常量"""

    # ==================== 窗口尺寸 ====================
    class Window:
        """窗口尺寸常量"""

        # 主窗口
        MAIN_WIDTH = 320
        MAIN_HEIGHT = 160

        # 设置对话框
        SETTINGS_WIDTH = 900
        SETTINGS_HEIGHT = 700

        # 更新对话框
        UPDATE_DIALOG_WIDTH = 500
        UPDATE_DIALOG_HEIGHT = 250

        # 更新详情对话框
        UPDATE_DETAIL_MIN_WIDTH = 600
        UPDATE_DETAIL_MIN_HEIGHT = 400
        UPDATE_DETAIL_MAX_WIDTH = 800
        UPDATE_DETAIL_MAX_HEIGHT = 700
        UPDATE_DETAIL_DEFAULT_WIDTH = 600
        UPDATE_DETAIL_DEFAULT_HEIGHT = 500

        # 测试窗口
        TEST_WINDOW_WIDTH = 300
        TEST_WINDOW_HEIGHT = 200

    # ==================== 颜色常量 ====================
    class Colors:
        """颜色常量"""

        # 主题色
        PRIMARY = "#0078d4"  # 主色调(蓝色)
        PRIMARY_HOVER = "#108de6"  # 主色调悬停
        PRIMARY_PRESSED = "#005a9e"  # 主色调按下

        # 背景色
        BG_DARK = "#1e1e1e"  # 深色背景
        BG_MEDIUM = "#2d2d2d"  # 中等背景
        BG_LIGHT = "#3d3d3d"  # 浅色背景
        BG_LIGHTER = "#4d4d4d"  # 更浅背景

        # 边框色
        BORDER_DARK = "#333333"  # 深色边框
        BORDER_MEDIUM = "#555555"  # 中等边框
        BORDER_LIGHT = "#888888"  # 浅色边框

        # 文本色
        TEXT_PRIMARY = "white"  # 主文本
        TEXT_DISABLED = "#888888"  # 禁用文本

        # 状态色 - 涨跌渐变
        STOCK_UP_LIMIT = "#FF0000"     # 涨停-最亮红
        STOCK_UP_BRIGHT = "#FF4500"    # 大涨-亮红(涨幅>=5%)
        STOCK_UP = "#e74c3f"           # 上涨-标准红
        STOCK_NEUTRAL = "#e6eaf3"      # 平盘-灰白
        STOCK_DOWN = "#27ae60"         # 下跌-标准绿
        STOCK_DOWN_DEEP = "#1e8449"    # 大跌-深绿(跌幅<=-5%)
        STOCK_DOWN_LIMIT = "#145a32"   # 跌停-最深绿

        # 状态色 - 背景
        BG_UP = "#ffecec"  # 上涨背景
        BG_DOWN = "#e8f5e9"  # 下跌背景

        # 按钮色 - 成功
        SUCCESS = "#28a745"  # 成功按钮
        SUCCESS_HOVER = "#218838"  # 成功按钮悬停
        SUCCESS_PRESSED = "#1e7e34"  # 成功按钮按下

        # 按钮色 - 危险
        DANGER = "#dc3545"  # 危险按钮
        DANGER_HOVER = "#c82333"  # 危险按钮悬停
        DANGER_PRESSED = "#bd2130"  # 危险按钮按下

        # 按钮色 - 禁用
        DISABLED_BG = "#555555"  # 禁用背景
        DISABLED_TEXT = "#888888"  # 禁用文本

        # 渐变色
        GRADIENT_START = "#2d2d2d"  # 渐变起始
        GRADIENT_END = "#1e1e1e"  # 渐变结束
        GRADIENT_PRIMARY_START = "#0078d4"  # 主色渐变起始
        GRADIENT_PRIMARY_END = "#00a8ff"  # 主色渐变结束

    # ==================== 字体常量 ====================
    class Fonts:
        """字体常量"""

        DEFAULT_FAMILY = "Microsoft YaHei"  # 默认字体
        DEFAULT_SIZE = 14  # 默认字号
        SMALL_SIZE = 12  # 小字号
        LARGE_SIZE = 16  # 大字号

    # ==================== 间距常量 ====================
    class Spacing:
        """间距常量"""

        SMALL = 5  # 小间距
        MEDIUM = 10  # 中等间距
        LARGE = 15  # 大间距
        EXTRA_LARGE = 20  # 超大间距

    # ==================== 透明度常量 ====================
    class Alpha:
        """透明度常量"""

        MIN = 128  # 最小透明度(50%)
        MAX = 255  # 最大透明度(100%)
        DEFAULT = 230  # 默认透明度(90%)

    # ==================== 刷新间隔常量 ====================
    class RefreshInterval:
        """刷新间隔常量(秒)"""

        FAST = 2  # 快速刷新
        NORMAL = 5  # 正常刷新
        SLOW = 10  # 慢速刷新
        VERY_SLOW = 30  # 很慢刷新
        ULTRA_SLOW = 60  # 超慢刷新

    # ==================== 其他UI常量 ====================
    class Misc:
        """其他UI常量"""

        BORDER_RADIUS = 4  # 圆角半径
        BORDER_WIDTH = 1  # 边框宽度
        SCROLLBAR_WIDTH = 150  # 滚动条最小高度
        SCROLLBAR_MAX_HEIGHT = 350  # 滚动条最大高度


# 便捷访问
WINDOW = UIConstants.Window
COLORS = UIConstants.Colors
FONTS = UIConstants.Fonts
SPACING = UIConstants.Spacing
ALPHA = UIConstants.Alpha
REFRESH = UIConstants.RefreshInterval
MISC = UIConstants.Misc

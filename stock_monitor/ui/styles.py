def get_table_style(font_family, font_size):
    """
    Generate CSS for the main stock table.

    Args:
        font_family (str): Font family name.
        font_size (int): Font size in pixels.

    Returns:
        str: CSS stylesheet string.
    """
    return f"""
        QTableView {{
            background: transparent;
            border: none;
            outline: none;
            gridline-color: #aaa;
            selection-background-color: transparent;
            selection-color: #fff;
            font-family: "{font_family}";
            font-size: {font_size}px;
            font-weight: bold;
            color: #fff;
        }}
        QTableView::item {{
            border: none;
            padding: 0px;
            background: transparent;
        }}
        QTableView::item:selected {{
            background: transparent;
            color: #fff;
        }}
        QHeaderView::section {{
            background: transparent;
            border: none;
            color: transparent;
        }}
        QScrollBar {{
            background: transparent;
            width: 0px;
            height: 0px;
        }}
        QScrollBar::handle {{
            background: transparent;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            background: transparent;
            border: none;
        }}
    """


def get_loading_label_style(font_size):
    """
    Generate CSS for the loading label.

    Args:
        font_size (int): Font size in pixels.

    Returns:
        str: CSS stylesheet string.
    """
    return f"""
        QLabel {{
            color: #fff;
            font-size: {max(1, font_size)}px;
            background: rgba(30, 30, 30, 0.8);
            border-radius: 10px;
            padding: 10px;
        }}
    """


def get_main_window_style(font_family, font_size):
    """
    Generate CSS for the main window container.

    Args:
        font_family (str): Font family name.
        font_size (int): Font size in pixels.

    Returns:
        str: CSS stylesheet string.
    """
    return f'font-family: "{font_family}"; font-size: {font_size}px;'


def get_button_style(
    bg_color="#0078d4",
    hover_color="#108de6",
    pressed_color="#005a9e",
    disabled_bg="#555555",
    disabled_color="#888888",
    text_color="white",
    border_radius="4px",
    padding="6px 12px",
    font_size="14px",
    min_width="60px",
    min_height="20px",
):
    """
    生成通用按钮样式

    Args:
        bg_color: 背景颜色
        hover_color: 悬停时颜色
        pressed_color: 按下时颜色
        disabled_bg: 禁用时背景色
        disabled_color: 禁用时文字颜色
        text_color: 文字颜色
        border_radius: 圆角半径
        padding: 内边距
        font_size: 字体大小
        min_width: 最小宽度
        min_height: 最小高度

    Returns:
        str: CSS样式字符串
    """
    return f"""
        QPushButton {{
            background-color: {bg_color};
            color: {text_color};
            border: none;
            border-radius: {border_radius};
            padding: {padding};
            font-size: {font_size};
            min-width: {min_width};
            min-height: {min_height};
        }}
        QPushButton:hover {{
            background-color: {hover_color};
        }}
        QPushButton:pressed {{
            background-color: {pressed_color};
        }}
        QPushButton:disabled {{
            background-color: {disabled_bg};
            color: {disabled_color};
        }}
    """


def get_primary_button_style():
    """获取主要按钮样式（蓝色）"""
    return get_button_style()


def get_success_button_style():
    """获取成功按钮样式（绿色）"""
    return get_button_style(
        bg_color="#28a745", hover_color="#218838", pressed_color="#1e7e34"
    )


def get_danger_button_style():
    """获取危险按钮样式（红色）"""
    return get_button_style(
        bg_color="#dc3545", hover_color="#c82333", pressed_color="#bd2130"
    )

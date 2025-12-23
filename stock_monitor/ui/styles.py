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
        QTableWidget {{
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
        QTableWidget::item {{
            border: none;
            padding: 0px;
            background: transparent;
        }}
        QTableWidget::item:selected {{
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

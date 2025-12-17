#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
右键菜单模块
负责创建和管理应用程序的右键菜单
"""

from PyQt6 import QtWidgets, QtGui


class AppContextMenu(QtWidgets.QMenu):
    """
    应用程序右键菜单类
    独立管理右键菜单的样式和行为，确保菜单样式不会被其他界面影响
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_style()
        # 保存默认样式，防止被外部修改
        self._default_style = self.styleSheet()
        
    def setup_style(self):
        """设置菜单样式"""
        self.setStyleSheet('''
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: 'Microsoft YaHei';
                font-size: 11px;
                padding: 2px 0;
                min-width: 0px;
            }
            QMenu::item {
                padding: 2px 6px;  /* 进一步减小菜单项左右内边距 */
                border-radius: 4px;
                min-width: 30px;  /* 进一步减小最小宽度 */
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background: #555555;
                margin: 2px 0;
            }
        ''')
        
    def update_font_family(self, font_family):
        """
        更新菜单字体族，但保持尺寸样式
        
        Args:
            font_family (str): 新的字体族
        """
        self.setStyleSheet(f'''
            QMenu {{
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                font-family: '{font_family}';
                font-size: 11px;
                padding: 2px 0;
                min-width: 0px;
            }}
            QMenu::item {{
                padding: 2px 6px;
                border-radius: 4px;
                min-width: 30px;
            }}
            QMenu::item:selected {{
                background-color: #0078d4;
            }}
            QMenu::separator {{
                height: 1px;
                background: #555555;
                margin: 2px 0;
            }}
        ''')

    def restore_default_style(self):
        """恢复默认样式"""
        self.setStyleSheet(self._default_style)


# 示例用法和测试代码
if __name__ == '__main__':
    import sys
    
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建测试窗口
    window = QtWidgets.QWidget()
    window.resize(300, 200)
    window.show()
    
    # 创建右键菜单
    menu = AppContextMenu(window)
    action_settings = menu.addAction('设置')
    menu.addSeparator()
    action_quit = menu.addAction('退出')
    
    # 连接信号
    action_settings.triggered.connect(lambda: print("设置"))
    action_quit.triggered.connect(app.quit)
    
    # 显示菜单
    menu.popup(QtGui.QCursor.pos())
    
    sys.exit(app.exec())
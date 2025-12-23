"""
股票数据模型模块
提供基于QAbstractTableModel的高效数据模型，用于QTableView显示
"""

from PyQt6 import QtCore, QtGui
from typing import List, Tuple, Any

class StockTableModel(QtCore.QAbstractTableModel):
    """
    股票数据模型
    
    数据结构:
    List[Tuple[name, price, change, color, seal_vol, seal_type]]
    """
    
    # 定义列索引
    COL_NAME = 0
    COL_PRICE = 1
    COL_CHANGE = 2
    COL_SEAL = 3
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Tuple] = []
        self._header_labels = ["名称", "价格", "涨跌幅", "封单"]
        self._font_size = 13
        self._show_seal_column = False
        
    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._data)
    
    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 4 if self._show_seal_column else 3
        
    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._data):
            return None
            
        row_data = self._data[index.row()]
        # row_data structure: (name, price, change, color, seal_vol, seal_type)
        col = index.column()
        
        name, price, change, color_hex, seal_vol, seal_type = row_data
        
        # 文本显示
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if col == self.COL_NAME:
                # 处理港股名称显示
                if name.startswith('hk') and ':' in name:
                    display_name = name.split(':')[1].strip()
                elif name.startswith('hk') and '-' in name:
                    display_name = name.split('-')[0].strip()
                else:
                    display_name = name
                return f" {display_name}"
                
            elif col == self.COL_PRICE:
                return price
                
            elif col == self.COL_CHANGE:
                if not change.endswith('%'):
                    return change + '%'
                return f"{change} "
                
            elif col == self.COL_SEAL:
                return f"{seal_vol} " if seal_vol and seal_type else ""
        
        # 文本颜色
        elif role == QtCore.Qt.ItemDataRole.ForegroundRole:
            # 封单列特殊处理
            if col == self.COL_SEAL:
                if seal_type == 'up':
                    return QtGui.QColor(color_hex)
                elif seal_type == 'down':
                    return QtGui.QColor('#27ae60')
                else:
                    return QtGui.QColor('#888')
            
            # 其他列使用传进来的color
            return QtGui.QColor(color_hex)
            
        # 背景颜色 (涨跌停高亮)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            if seal_type == 'up':
                return QtGui.QColor('#ffecec')
            elif seal_type == 'down':
                return QtGui.QColor('#e8f5e9')
            # 默认透明背景
            return None
            
        # 对齐方式
        elif role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if col == self.COL_NAME:
                return QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            else:
                return QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                
        # 不再通过FontRole设置字体，让CSS样式表接管
        # 这样可以避免QFont与CSS的优先级冲突
        # elif role == QtCore.Qt.ItemDataRole.FontRole:
        #     font = QtGui.QFont("微软雅黑", self._font_size)
        #     font.setBold(True)
        #     return font
            
        return None
        
    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == QtCore.Qt.Orientation.Horizontal and role == QtCore.Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._header_labels):
                return self._header_labels[section]
        return None
        
    def update_data(self, new_data: List[Tuple]):
        """更新数据"""
        # 检查是否需要显示封单列
        has_seal = any(item[5] for item in new_data) # item[5] is seal_type
        
        # 布局变更检测
        layout_changed = (has_seal != self._show_seal_column)
        
        self.beginResetModel()
        self._data = new_data
        self._show_seal_column = has_seal
        self.endResetModel()
        
        return layout_changed
        
    def set_font_size(self, size: int):
        self._font_size = size
        # 字体改变需要重绘
        self.force_refresh()
        
    def force_refresh(self):
        """强制刷新所有视图"""
        if self._data:
            self.dataChanged.emit(
                self.index(0, 0), 
                self.index(len(self._data)-1, self.columnCount()-1),
                [QtCore.Qt.ItemDataRole.FontRole]
            )

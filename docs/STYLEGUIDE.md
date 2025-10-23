# 代码风格指南

本项目遵循Python社区的最佳实践和PEP 8规范。

## 目录

- [代码格式](#代码格式)
- [命名规范](#命名规范)
- [文档字符串](#文档字符串)
- [类型注解](#类型注解)
- [注释](#注释)
- [导入](#导入)
- [异常处理](#异常处理)

## 代码格式

### 缩进
- 使用4个空格进行缩进
- 不使用制表符

### 行长度
- 每行最多79个字符
- 注释和文档字符串每行最多72个字符

### 空行
- 顶级函数和类定义前后用两行空行分隔
- 类内的方法定义前后用一行空行分隔
- 函数内的逻辑代码块可用空行分隔，但要适度

### 导入
```python
# 正确
import os
import sys

from PyQt5 import QtWidgets, QtGui, QtCore

# 错误
from PyQt5.QtWidgets import *
```

## 命名规范

### 模块和包
- 全小写，单词间用下划线分隔
- 简短但有意义
```python
# 正确
config_manager.py
ui_components.py

# 错误
ConfigManager.py
ui-components.py
```

### 类
- 使用大写字母开头的驼峰命名法(CamelCase)
```python
class StockTable:
class SettingsDialog:
```

### 函数和变量
- 全小写，单词间用下划线分隔
```python
def load_config():
def get_stock_emoji():
refresh_interval = 5
user_stocks = []
```

### 常量
- 全大写，单词间用下划线分隔
```python
APP_VERSION = 'v1.0.0'
CONFIG_PATH = 'config.json'
```

### 私有成员
- 使用单下划线前缀
```python
def _format_stock_code():
class _InternalClass:
```

## 文档字符串

### 模块文档字符串
每个模块文件的开头应包含文档字符串，描述模块的功能：
```python
"""
配置管理模块

提供配置文件的加载、保存和管理功能。
"""
```

### 类文档字符串
每个类应包含文档字符串，描述类的用途和主要功能：
```python
class StockTable(QtWidgets.QTableWidget):
    """
    股票表格组件
    
    用于显示股票行情数据的表格组件，支持自定义样式和数据更新。
    """
```

### 函数文档字符串
每个公共函数应包含文档字符串，描述功能、参数和返回值：
```python
def load_config():
    """
    加载配置文件
    
    从配置文件中加载用户设置，如果文件不存在则创建默认配置。
    
    Returns:
        dict: 包含配置信息的字典
    """
```

## 类型注解

### 函数参数和返回值
为函数参数和返回值添加类型注解：
```python
from typing import List, Dict, Optional

def format_stock_code(code: str) -> Optional[str]:
    """格式化股票代码"""
    pass

def load_stock_data() -> List[Dict[str, str]]:
    """加载股票数据"""
    pass
```

### 变量
为复杂变量添加类型注解：
```python
user_stocks: List[str] = []
config: Dict[str, Any] = {}
```

## 注释

### 单行注释
- 使用`#`后跟一个空格
- 注释应与被注释的代码对齐
```python
# 计算涨跌幅百分比
percent = ((now - close) / close * 100) if close else 0
```

### 多行注释
- 使用多个单行注释
- 或使用三引号字符串
```python
"""
处理股票数据
1. 获取股票名称
2. 计算价格变化
3. 设置显示颜色
"""
```

### 注释内容
- 解释"为什么"而不是"是什么"
- 保持注释与代码同步更新
- 删除无用的注释

## 导入

### 导入顺序
1. 标准库导入
2. 第三方库导入
3. 本地应用/库导入

### 分组
每组导入之间用空行分隔：
```python
import json
import os
import sys

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal, pyqtSlot

from .config.manager import load_config
from .utils.helpers import resource_path
```

### 避免循环导入
- 重构代码避免循环依赖
- 使用延迟导入（在函数内部导入）
- 考虑将共享代码移到单独的模块

## 异常处理

### 捕获具体异常
```python
# 正确
try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    # 处理文件不存在
    pass
except json.JSONDecodeError:
    # 处理JSON解析错误
    pass

# 错误
try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
except Exception:
    pass
```

### 异常信息
- 提供有用的错误信息
- 不要忽略异常（除非有充分理由）
- 记录异常日志（如适用）

```python
try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
except json.JSONDecodeError as e:
    print(f"配置文件格式错误: {e}")
    # 可以选择创建默认配置或提示用户
```

### 自定义异常
在适当的情况下创建自定义异常类：
```python
class ConfigError(Exception):
    """配置相关异常"""
    pass
```

## 其他建议

### 函数设计
- 保持函数简短，单一职责
- 函数参数不宜过多（建议不超过5个）
- 避免副作用

### 类设计
- 遵循单一职责原则
- 合理使用继承和组合
- 保持公共接口简洁

### 性能考虑
- 避免不必要的重复计算
- 合理使用缓存
- 注意内存使用

通过遵循这些规范，我们可以保持代码的一致性和可读性，使项目更易于维护和协作开发。
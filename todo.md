# 项目待办事项列表

## 已完成
1. 模块化重构
目前设置界面的所有功能都在一个类中实现，可以考虑将其拆分为更小的组件：
股票搜索模块 - 已经部分实现为 StockSearchWidget，但可以进一步优化
自选股列表模块 - StockListWidget 可以进一步独立
设置选项模块 - 刷新频率、开机启动等设置可以整合为一个独立的设置面板

2. UI布局优化
当前界面虽然功能完整，但可以进一步优化用户体验：
响应式布局 - 当前使用固定尺寸，可以考虑使用更灵活的布局管理器
搜索体验优化 - 可以增加搜索历史、热门搜索等功能
自选股列表增强 - 可以增加分组、排序选项等功能

3. 性能优化
数据加载优化 - 当前每次打开设置都会重新加载股票数据，可以考虑缓存机制
搜索性能 - 对于大量股票数据的搜索可以使用更高效的算法或索引

4. 功能增强建议
批量操作 - 增加全选、反选、批量删除等功能
导入导出自选股 - 支持从文件导入或导出自选股列表
~~搜索结果优化 - 增加智能排序，将匹配度高的结果排在前面~~

5. 代码结构优化
~~减少重复代码 - accept 和 sync_to_main 方法中有很多重复代码，可以提取公共方法~~
~~配置管理 - 可以将配置的读取和保存进一步封装~~

## 可以优化的地方和功能

### 代码优化
~~1. 重复代码检查 - 检查项目中是否存在重复的代码逻辑~~
~~2. 未使用导入清理 - 移除未使用的导入语句~~
~~3. 代码规范性 - 统一代码风格和注释规范~~

### 功能增强
1. 全选/反选功能 - 在自选股列表中增加全选和反选功能
2. 批量删除 - 支持同时删除多个选中的自选股
3. 自选股导出 - 支持将自选股列表导出到文件
4. 自选股导入 - 支持从文件导入自选股列表
5. 热门股票推荐 - 在搜索界面增加热门股票推荐功能

### UI/UX优化
1. 响应式布局 - 使用更灵活的布局管理器替代固定尺寸
2. 搜索体验优化 - 增加搜索历史记录、热门搜索建议
3. 界面美化 - 进一步优化界面视觉效果，保持透明磨砂玻璃风格

## 已识别的重复代码问题

### 1. get_name_by_code 函数重复实现
- [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 中实现了 `get_name_by_code` 方法
- [stock_monitor/ui/stock_search.py](file:///d%3A/code/stock/stock_monitor/ui/stock_search.py) 中实现了 `get_name_by_code` 方法
- [stock_monitor/data/quotation.py](file:///d%3A/code/stock/stock_monitor/data/quotation.py) 中实现了 `get_name_by_code` 函数
~~- [stock_monitor/ui/components.py](file:///d%3A/code/stock/stock_monitor/ui/components.py) 中实现了 `get_name_by_code` 方法~~

### 2. 股票数据加载和拼音处理功能重复
- [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 中实现了 `load_stock_data` 和 `enrich_pinyin` 方法
- [stock_monitor/ui/stock_search.py](file:///d%3A/code/stock/stock_monitor/ui/stock_search.py) 中实现了 `load_stock_data` 和 `enrich_pinyin` 方法
- [stock_monitor/data/stocks.py](file:///d%3A/code/stock/stock_monitor/data/stocks.py) 中有统一的实现

### 3. 未使用的导入语句
- [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 中导入了未使用的模块
- [stock_monitor/main.py](file:///d%3A/code/stock/stock_monitor/main.py) 中导入了未使用的模块

## 建议的优化方案

### 1. 消除重复代码
~~- 移除 [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 和 [stock_monitor/ui/stock_search.py](file:///d%3A/code/stock/stock_monitor/ui/stock_search.py) 中的 `get_name_by_code` 方法，统一使用 [stock_monitor/data/quotation.py](file:///d%3A/code/stock/stock_monitor/data/quotation.py) 中的实现~~
~~- 移除 [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 和 [stock_monitor/ui/stock_search.py](file:///d%3A/code/stock/stock_monitor/ui/stock_search.py) 中的 `load_stock_data` 和 `enrich_pinyin` 方法，统一使用 [stock_monitor/data/stocks.py](file:///d%3A/code/stock/stock_monitor/data/stocks.py) 中的实现~~
~~- 移除 [stock_monitor/ui/components.py](file:///d%3A/code/stock/stock_monitor/ui/components.py) 中未使用的 `get_name_by_code` 方法~~

### 2. 清理未使用导入
~~- 清理 [stock_monitor/ui/settings_dialog.py](file:///d%3A/code/stock/stock_monitor/ui/settings_dialog.py) 中未使用的导入语句~~
~~- 清理 [stock_monitor/main.py](file:///d%3A/code/stock/stock_monitor/main.py) 中未使用的导入语句~~
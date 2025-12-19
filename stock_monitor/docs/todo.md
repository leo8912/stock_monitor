# 代码重构任务清单

## 1. 主程序模块 (main.py)

### 1.1 拆分setup_ui方法 (高优先级) ✅ 已完成
- **任务描述**: 将MainWindow.setup_ui()方法拆分为多个小方法，分别处理窗口属性设置、UI组件初始化和事件处理初始化
- **源文件**: `stock_monitor/main.py`
- **代码位置**: `MainWindow.setup_ui()` 方法（第70-192行）
- **推荐理由**: 解决函数过长问题，符合单一职责原则，提高代码可读性和可维护性

### 1.2 消除重复代码 (高优先级) ✅ 已完成
- **任务描述**: 创建`get_config_manager`工具函数，消除多处重复的ConfigManager导入和初始化代码
- **源文件**: `stock_monitor/main.py`
- **代码位置**: 第112行、第141行、第387行等多处ConfigManager重复导入
- **推荐理由**: 符合DRY原则，便于维护

### 1.3 提取魔法数字为常量 (中优先级) ✅ 已完成
- **任务描述**: 将paintEvent方法中的魔法数字200和55定义为模块级常量
- **源文件**: `stock_monitor/main.py`
- **代码位置**: 第746行 `alpha = int(200 + (55 * transparency / 100))`
- **推荐理由**: 提高代码可读性，便于理解和修改

## 2. 配置管理模块 (config/manager.py)

### 2.1 拆分_load_config方法 (高优先级) ✅ 已完成
- **任务描述**: 将_load_config方法中的不同错误处理逻辑提取为独立方法
- **源文件**: `stock_monitor/config/manager.py`
- **代码位置**: `_load_config()` 方法（第64-83行）
- **推荐理由**: 明确职责划分，提高代码可读性，便于维护特定错误处理逻辑

### 2.2 添加类型提示 (中优先级) ✅ 已完成
- **任务描述**: 为_create_default_config方法添加返回值类型提示
- **源文件**: `stock_monitor/config/manager.py`
- **代码位置**: `_create_default_config()` 方法
- **推荐理由**: 符合PEP 484规范，提高代码可读性和IDE支持

## 3. UI组件模块 (ui/components/stock_table.py)

### 3.1 添加类型提示 (中优先级) ✅ 已完成
- **任务描述**: 为_create_table_item等方法添加参数和返回值类型提示
- **源文件**: `stock_monitor/ui/components/stock_table.py`
- **代码位置**: `_create_table_item()`等方法
- **推荐理由**: 符合PEP 484规范，提高代码可读性和IDE支持

### 3.2 添加文档字符串 (中优先级) ✅ 已完成
- **任务描述**: 为私有方法如_set_text_alignment等添加完整的文档字符串
- **源文件**: `stock_monitor/ui/components/stock_table.py`
- **代码位置**: `_set_text_alignment()`等私有方法
- **推荐理由**: 提高代码可读性，便于理解和维护

## 4. 核心业务模块 (core/stock_manager.py)

### 4.1 拆分get_stock_list_data方法 (高优先级) ✅ 已完成
- **任务描述**: 将get_stock_list_data方法中的数据处理逻辑和封单计算逻辑提取为独立方法
- **源文件**: `stock_monitor/core/stock_manager.py`
- **代码位置**: `get_stock_list_data()`方法（第43-154行）
- **推荐理由**: 解决函数复杂度过高问题，符合单一职责原则，提高可测试性

## 5. 设置对话框模块 (ui/dialogs/settings_dialog.py)

### 5.1 拆分NewSettingsDialog类 (高优先级) ✅ 已完成
- **任务描述**: 将NewSettingsDialog类中搜索、自选股管理、配置管理等功能拆分为独立的小类
- **源文件**: `stock_monitor/ui/dialogs/settings_dialog.py`
- **代码位置**: `NewSettingsDialog`类（超过1200行）
- **推荐理由**: 解决类过大问题，符合单一职责原则，提高可维护性

## 6. 高优先级优化项

### 6.1 引入缓存机制 (高优先级) ✅ 已完成
- **任务描述**: 在StockManager中引入LRU缓存机制，缓存股票数据处理结果
- **源文件**: `stock_monitor/core/stock_manager.py`
- **推荐理由**: 减少重复的数据处理计算，提高数据刷新效率，降低CPU和内存消耗

### 6.2 优化UI渲染性能 (高优先级) ✅ 已完成
- **任务描述**: 在StockTable中引入差异更新机制，只更新发生变化的数据行
- **源文件**: `stock_monitor/ui/components/stock_table.py`
- **推荐理由**: 减少UI重绘次数，提高渲染性能，降低CPU使用率，提升用户体验

## 7. 中优先级优化项

### 7.1 引入依赖注入优化 (中优先级)
- **任务描述**: 使用依赖注入容器管理核心组件（如ConfigManager、StockManager等）
- **源文件**: 多个文件涉及
- **推荐理由**: 降低模块间的耦合度，提高可测试性，便于替换实现

### 7.2 优化错误处理机制 (中优先级)
- **任务描述**: 引入统一的错误处理装饰器或上下文管理器
- **源文件**: 多个文件涉及
- **推荐理由**: 统一错误处理方式，减少重复的try/except代码块，便于集中管理和维护

## 实施顺序建议

1. **第一阶段（高优先级任务）**:
   - 拆分主程序模块的setup_ui方法 ✅ 已完成
   - 消除配置管理模块的重复代码 ✅ 已完成
   - 拆分核心业务模块的get_stock_list_data方法 ✅ 已完成
   - 拆分设置对话框模块的NewSettingsDialog类 ✅ 已完成

2. **第二阶段（中优先级任务）**:
   - 添加各模块的类型提示 ✅ 已完成
   - 添加UI组件模块的文档字符串 ✅ 已完成
   - 提取主程序模块的魔法数字为常量 ✅ 已完成
   - 拆分配置管理模块的_load_config方法 ✅ 已完成

3. **第三阶段（优化项）**:
   - 引入缓存机制 ✅ 已完成
   - 优化UI渲染性能 ✅ 已完成
   - 引入依赖注入优化
   - 优化错误处理机制

所有任务均应确保不修改业务逻辑和功能行为，仅提升代码质量。
# 设置界面标签页（Tab）优化方案

## 🎯 优化目标

### 当前问题
1. **内容过多太拥挤** - 所有配置项垂直堆叠，窗口高度不足
2. **自选股区域展示不足** - 左右分栏布局导致搜索和列表都受限
3. **视觉层次不清晰** - 多个分组并列，缺乏明确的信息架构

### 优化方向
- ✅ 改用标签页（QTabWidget）组织配置项
- ✅ 自选股区域改为上下布局，最大化列表展示空间
- ✅ 每个标签页专注一类设置，提升认知效率

---

## 📐 标签页架构设计

### 标签页结构
```
┌─────────────────────────────────────────────────────┐
│ A 股行情监控设置                              [×]   │
├─────────────────────────────────────────────────────┤
│ [📋 自选股管理] [🎨 显示设置] [📊 量化预警] [⚙️ 系统] │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌────────────────────────────────────────────┐    │
│  │                                            │    │
│  │          当前标签页的内容区域               │    │
│  │                                            │    │
│  │  • 更大的列表展示空间                      │    │
│  │  • 更清晰的分组层次                        │    │
│  │  • 更舒适的操作体验                        │    │
│  │                                            │    │
│  └────────────────────────────────────────────┘    │
│                                                      │
├─────────────────────────────────────────────────────┤
│  ⚙️ 开机启动 ☑  刷新频率 [5 秒 ▼]  📦 v1.0.0       │
│                                    [确定] [取消]    │
└─────────────────────────────────────────────────────┘
```

### 标签页分配

#### Tab 1: 📋 自选股管理
- **核心功能**: 股票搜索、添加、删除、排序
- **布局优化**:
  - 顶部：搜索框 + 搜索结果（可折叠）
  - 中部：自选股列表（占据 70% 空间）
  - 底部：操作按钮（删除、上移、下移）

#### Tab 2: 🎨 显示设置
- **字体设置**: 字体大小滑块 + 字体选择下拉框
- **透明度**: 背景透明度滑块
- **预览**: 实时预览效果
- **重置**: 恢复默认值按钮

#### Tab 3: 📊 量化预警
- **开关**: 开启智能扫描复选框
- **通知渠道**: Webhook / 企业应用切换
- **Webhook 配置**: 地址输入框 + 测试推送
- **企业应用配置**: CorpID、Secret、AgentID + 测试应用
- **手动复盘**: 立即执行全量复盘按钮

#### Tab 4: ⚙️ 系统设置（移出主标签页）
- **基础设置**: 开机启动、刷新频率
- **版本信息**: 版本号 + 检查更新
- **位置**: 作为底部工具栏，不属于任何标签页

---

## 🔧 技术实施方案

### 1. 引入 QTabWidget
```python
from PyQt6.QtWidgets import QTabWidget

# 创建标签页容器
self.tabs = QTabWidget()
self.tabs.setObjectName("SettingsTabs")

# 创建各个标签页
self.tab_watchlist = QWidget()
self.tab_display = QWidget()
self.tab_quant = QWidget()

# 添加到标签页
self.tabs.addTab(self.tab_watchlist, "📋 自选股管理")
self.tabs.addTab(self.tab_display, "🎨 显示设置")
self.tabs.addTab(self.tab_quant, "📊 量化预警")

# 设置标签页样式
self.tabs.setStyleSheet("""
    QTabWidget::pane {
        border: 1px solid #555;
        border-radius: 4px;
        background-color: #2d2d2d;
    }
    QTabBar::tab {
        background-color: #3d3d3d;
        color: #ffffff;
        padding: 8px 16px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }
    QTabBar::tab:selected {
        background-color: #0078d4;
    }
    QTabBar::tab:hover {
        background-color: #4d4d4d;
    }
""")
```

### 2. 重构 `_setup_watchlist_ui` - 上下布局
```python
def _setup_watchlist_ui(self, tab_widget):
    """设置自选股管理 UI - 上下布局"""
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(15, 15, 15, 15)
    main_layout.setSpacing(12)

    # === 顶部：搜索区域 ===
    search_group = QGroupBox("🔍 搜索股票")
    search_layout = QVBoxLayout()
    search_layout.setSpacing(8)

    # 搜索输入框（大尺寸）
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText("输入股票代码或名称，按回车快速添加...")
    self.search_input.setFixedHeight(40)  # 增加高度

    # 搜索结果列表（可折叠）
    self.search_results = QListWidget()
    self.search_results.setMaximumHeight(150)  # 限制最大高度
    self.search_results.setObjectName("SettingsSearchResults")

    # 添加按钮
    self.add_button = QPushButton("➕ 添加到自选股")
    self.add_button.setObjectName("PrimaryButton")
    self.add_button.setFixedHeight(36)
    self.add_button.setEnabled(False)

    search_layout.addWidget(self.search_input)
    search_layout.addWidget(self.search_results)
    search_layout.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignCenter)
    search_group.setLayout(search_layout)

    # === 中部：自选股列表（占据主要空间） ===
    list_group = QGroupBox("📋 自选股列表")
    list_layout = QVBoxLayout()
    list_layout.setSpacing(8)

    self.watch_list = DraggableListWidget()
    self.watch_list.setObjectName("SettingsWatchList")
    # ... 拖拽配置 ...

    list_layout.addWidget(self.watch_list)
    list_group.setLayout(list_layout)

    # === 底部：操作按钮 ===
    button_group = QGroupBox("🛠️ 操作")
    button_layout = QHBoxLayout()
    button_layout.setSpacing(12)

    self.remove_button = QPushButton("🗑 删除")
    self.remove_button.setObjectName("removeButton")
    self.remove_button.setFixedHeight(36)
    self.remove_button.setEnabled(False)

    self.move_up_button = QPushButton("↑ 上移")
    self.move_up_button.setObjectName("move_up_button")
    self.move_up_button.setFixedHeight(36)
    self.move_up_button.setEnabled(False)

    self.move_down_button = QPushButton("↓ 下移")
    self.move_down_button.setObjectName("move_down_button")
    self.move_down_button.setFixedHeight(36)
    self.move_down_button.setEnabled(False)

    button_layout.addWidget(self.remove_button)
    button_layout.addWidget(self.move_up_button)
    button_layout.addWidget(self.move_down_button)
    button_group.setLayout(button_layout)

    # 添加到主布局
    main_layout.addWidget(search_group)
    main_layout.addWidget(list_group, stretch=1)  # 列表占据剩余空间
    main_layout.addWidget(button_group)

    tab_widget.setLayout(main_layout)
```

### 3. 重构主布局 - 引入标签页
```python
def __init__(self, main_window=None):
    # ... 现有初始化代码 ...

    # 创建主布局
    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(20, 20, 20, 20)
    main_layout.setSpacing(15)
    self.setLayout(main_layout)

    # === 创建标签页 ===
    self._setup_tabs(main_layout)

    # === 底部：系统设置和按钮 ===
    self._setup_bottom_bar(main_layout)

    # ... 后续初始化代码 ...

def _setup_tabs(self, main_layout):
    """创建标签页"""
    from PyQt6.QtWidgets import QTabWidget, QWidget

    self.tabs = QTabWidget()
    self.tabs.setObjectName("SettingsTabs")

    # 创建各个标签页
    self.tab_watchlist = QWidget()
    self.tab_display = QWidget()
    self.tab_quant = QWidget()

    # 构建各标签页内容
    self._setup_watchlist_ui(self.tab_watchlist)
    self._setup_display_settings_ui(self.tab_display)
    self._setup_quant_settings_ui(self.tab_quant)

    # 添加到标签页
    self.tabs.addTab(self.tab_watchlist, "📋 自选股管理")
    self.tabs.addTab(self.tab_display, "🎨 显示设置")
    self.tabs.addTab(self.tab_quant, "📊 量化预警")

    main_layout.addWidget(self.tabs)

def _setup_bottom_bar(self, main_layout):
    """设置底部工具栏（系统设置 + 按钮）"""
    # 系统设置行
    system_layout = QHBoxLayout()
    # ... 开机启动、刷新频率、版本号 ...

    # 底部按钮
    button_layout = QHBoxLayout()
    # ... 确定、取消按钮 ...

    # 合并到底部
    bottom_layout = QHBoxLayout()
    bottom_layout.addLayout(system_layout, 1)
    bottom_layout.addLayout(button_layout)
    main_layout.addLayout(bottom_layout)
```

---

## 🎨 样式表增强

### 标签页样式（暗色主题）
```css
/* 标签页容器 */
QTabWidget#SettingsTabs {
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: 4px;
}

/* 标签栏 */
QTabBar {
    background-color: transparent;
}

/* 标签页按钮 */
QTabBar::tab {
    background-color: #3d3d3d;
    color: #ffffff;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 120px;
}

/* 选中状态 */
QTabBar::tab:selected {
    background-color: #0078d4;
    font-weight: bold;
}

/* 悬停状态 */
QTabBar::tab:hover {
    background-color: #4d4d4d;
}

/* 禁用状态 */
QTabBar::tab:disabled {
    background-color: #2d2d2d;
    color: #666;
}
```

---

## 📊 空间对比

### 优化前（垂直堆叠）
```
窗口高度需求：~900px
- 自选股管理：280px
- 显示设置：120px
- 量化预警：280px
- 系统设置：80px
- 底部按钮：60px
- 间距：80px
```

### 优化后（标签页）
```
窗口高度需求：~650px (-28%)
- 标签页内容：480px（自选股列表占 70% = 336px）
- 底部工具栏：80px
- 间距：90px
```

**效果提升**:
- ✅ 窗口高度减少 28%
- ✅ 自选股列表高度增加 43% (236px → 336px)
- ✅ 视觉层次更清晰
- ✅ 操作更专注

---

## ✅ 验收标准

### 功能完整性
- [ ] 所有原有功能正常工作
- [ ] 信号槽连接正确
- [ ] 配置加载/保存正常

### UI 体验
- [ ] 标签页切换流畅
- [ ] 自选股列表占据主要空间
- [ ] 搜索框高度适中（40px）
- [ ] 按钮高度统一（36px）
- [ ] 底部工具栏固定可见

### 响应式布局
- [ ] 窗口缩放时布局自适应
- [ ] 最小尺寸限制合理
- [ ] 无内容溢出或遮挡

---

## 🚀 实施步骤

### Phase 1: 基础架构（P0）
1. 引入 QTabWidget
2. 创建 3 个标签页容器
3. 移动现有内容到对应标签页
4. 调整主布局结构

### Phase 2: 自选股优化（P0）
1. 改为上下布局
2. 增加搜索框高度
3. 扩大列表展示空间
4. 优化按钮布局

### Phase 3: 样式美化（P1）
1. 标签页暗色主题
2. 统一按钮高度
3. 优化间距和内边距
4. 添加 hover/selected 状态

### Phase 4: 细节打磨（P2）
1. 搜索框回车快速添加
2. 列表支持 Ctrl+A 全选
3. 添加键盘快捷键
4. 工具提示优化

---

## 📝 注意事项

### 兼容性
- 保持 ViewModel 接口不变
- 配置存储格式不变
- 信号名称和参数不变

### 用户体验
- 首次打开默认选中"自选股管理"标签
- 记住上次关闭时的标签页索引（可选）
- 标签页切换无闪烁

### 性能
- 懒加载各标签页内容
- 避免重复创建/销毁
- 信号断开/重连正确处理

---

**预计实施时间**: 2-3 小时
**风险等级**: 低（纯 UI 重构，不影响业务逻辑）
**用户价值**: 高（显著提升可用性和美观度）

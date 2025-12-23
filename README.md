# A股行情监控系统

本软件是一个用于实时监控A股行情的桌面应用程序，采用Python和PyQt5开发，具有简洁美观的界面和丰富的功能。

![A股行情监控系统界面示意图](image.png)

## 项目概述

A股行情监控系统是一款专为A股投资者设计的实时行情监控工具，帮助用户快速掌握自选股的最新动态。该软件具备以下特色功能：

- 实时显示自选股最新价格和涨跌幅
- 高亮显示涨跌停股票及其封单情况
- 市场整体涨跌状态可视化展示
- 灵活的自选股管理（支持代码/名称/拼音搜索）
- 窗口拖拽移动和位置记忆
- 右键菜单快捷操作
- 可调节的数据刷新频率（2-60秒）
- 自动版本更新功能
- 日志自动清理机制
- 绿色软件特性（解压即用）

## 项目结构

```
stock_monitor/
├── config/                 # 配置管理模块
│   ├── __init__.py
│   └── manager.py         # 配置加载和保存功能
├── core/                  # 核心业务逻辑模块
│   ├── __init__.py
│   ├── market_manager.py  # 市场管理器
│   ├── stock_manager.py   # 股票管理器
│   └── stock_service.py   # 股票服务
├── data/                  # 数据处理模块
│   ├── market/
│   │   ├── __init__.py
│   │   ├── quotation.py   # 行情数据处理
│   │   └── updater.py     # 市场数据更新
│   ├── stock/
│   │   ├── __init__.py
│   │   └── stocks.py      # 股票数据处理
│   └── __init__.py
├── network/               # 网络请求模块
│   ├── __init__.py
│   └── manager.py         # 网络请求封装
├── resources/             # 资源文件目录
│   ├── icon.ico           # 应用图标
│   └── stocks.db          # SQLite数据库文件，包含股票基础数据
├── ui/                    # 用户界面模块
│   ├── components/
│   │   ├── __init__.py
│   │   └── stock_table.py # 股票表格组件
│   ├── dialogs/
│   │   ├── __init__.py
│   │   └── settings_dialog.py # 设置对话框
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── market_status.py   # 市场状态条组件
│   │   └── stock_search.py    # 股票搜索组件
│   └── __init__.py
├── utils/                 # 工具模块
│   ├── __init__.py
│   ├── cache.py           # 数据缓存
│   ├── error_handler.py   # 错误处理
│   ├── helpers.py         # 辅助函数
│   ├── log_cleaner.py     # 日志清理工具
│   ├── logger.py          # 日志记录
│   └── stock_cache.py     # 股票缓存
├── __init__.py
└── main.py                # 主程序入口

其他文件:
├── API.md                 # API文档
├── build.py               # 构建脚本
├── build_config.py        # 构建配置
├── requirements.txt       # 生产环境依赖列表
├── requirements-dev.txt   # 开发环境依赖列表（包含测试依赖）
├── CHANGELOG.md           # 更新日志
└── README.md              # 项目说明文档
```

## 核心功能详解

### 1. 实时行情监控
- 实时显示自选股的最新价格和涨跌幅
- 支持多种股票类型（A股、指数等）
- 颜色标识涨跌状态，涨幅超过5%使用更亮的橙红色突出显示

### 2. 涨跌停封单显示
- 自动识别并高亮显示涨停/跌停股票的封单手数
- 封单数以"k"为单位显示，简洁明了

### 3. 市场状态可视化
- 底部状态条可视化展示整个市场的涨跌情况
- 红色表示上涨，绿色表示下跌，灰色表示平盘

### 4. 自选股管理
- 支持添加、删除自选股
- 支持通过股票代码、名称、拼音、首字母等多种方式搜索股票
- 支持ST股票的特殊处理和模糊搜索

### 5. 灵活的界面操作
- 支持窗口拖拽移动
- 右键菜单提供设置和退出选项
- 窗口位置自动记忆

### 6. 智能刷新机制
- 支持多种刷新频率设置（2秒、5秒、10秒、30秒、60秒）
- 开市期间按设定频率刷新，休市期间降低刷新频率

### 7. 自动更新功能
- 采用独立更新程序(updater.exe)实现无缝更新
- 支持自动检测并下载新版本
- 通过GitHub API检测更新,支持备用加速下载源(https://ghfast.top/)
- 更新过程中显示进度界面,用户体验流畅
- 自动备份当前版本,支持更新失败回滚
- 更新完成后自动启动新版本

### 8. 开机自启动
- 支持设置开机自动启动

### 9. 日志自动清理
- 自动清理7天前的日志文件，防止日志文件过大
- 每24小时检查一次并清理过期日志

## 使用说明

1. 运行 `python main.py` 启动（需安装依赖，见 requirements.txt）
2. Windows 可用打包版，下载 release 页的 `stock_monitor.zip` 解压即用
3. 右键点击窗口可打开设置界面，管理自选股、刷新频率、开机启动等

## 测试运行

### 开发环境运行

```bash
# 1. 克隆项目
git clone <项目地址>
cd stock_monitor

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行程序
python -m stock_monitor.main
# 或者
cd stock_monitor && python main.py
```

### 测试日志清理功能

```bash
# 测试清理过期日志功能
python -c "from stock_monitor.utils.log_cleaner import clean_old_logs; print('清理过期日志...'); deleted = clean_old_logs(); print(f'已删除 {deleted} 个过期日志文件')"
```

## 依赖环境

### 生产环境依赖
- Python 3.7+
- PyQt5
- easyquotation
- pypinyin
- packaging
- pywin32

### 开发环境依赖
除了生产环境依赖外，还包括：
- pytest（用于测试）

## 构建与发布

- 采用 GitHub Actions 自动打包，主分支变动即触发
- 打包产物为 `stock_monitor.zip`，含所有依赖，解压即用
- Release 日志自动从 CHANGELOG.md 提取，最新在前

## 更新机制

### 独立更新程序

本软件采用独立更新程序(`updater.exe`)实现自动更新,彻底解决了Windows平台文件锁定问题。

**更新流程**:
1. 主程序检测到新版本并下载更新包
2. 主程序启动`updater.exe`并传递更新包路径
3. 主程序立即退出,释放所有文件锁
4. `updater.exe`等待主程序完全退出
5. `updater.exe`解压更新包并备份当前版本
6. `updater.exe`替换所有文件
7. `updater.exe`启动新版本主程序
8. `updater.exe`自动删除自身

**优势**:
- ✅ 完全避免文件锁定问题
- ✅ 用户体验流畅,无卡顿
- ✅ 支持更新失败自动回滚
- ✅ 自动清理临时文件
- ✅ 显示友好的进度界面
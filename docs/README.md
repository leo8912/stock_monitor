# A股行情监控软件开发文档

## 目录

- [项目概述](#项目概述)
- [开发环境搭建](#开发环境搭建)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [测试](#测试)
- [构建和发布](#构建和发布)
- [贡献指南](#贡献指南)

## 项目概述

本软件是一个基于Python和PyQt5的A股行情监控工具，具有以下特点：
- 实时显示自选股行情数据
- 支持拼音搜索和ST股票特殊处理
- 具有自动更新功能
- 使用GitHub Actions进行自动构建和发布

## 开发环境搭建

### 系统要求

- Windows 7/8/10/11 (推荐Windows 10及以上)
- Python 3.7+

### 安装步骤

1. 克隆项目代码：
```bash
git clone <项目地址>
cd stock_monitor
```

2. 创建虚拟环境（推荐）：
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 运行程序：
```bash
python stock_monitor/main.py
```

## 项目结构

```
stock_monitor/
├── main.py                 # 程序入口
├── build.py                # 构建脚本
├── build_config.py         # 构建配置
├── test_build.py           # 构建测试
├── test_runner.py          # 测试运行器
├── requirements.txt        # 依赖列表
├── README.md               # 项目说明
├── CHANGELOG.md            # 更新日志
├── GITHUB_ACTIONS.md       # GitHub Actions说明
├── config.json             # 用户配置（运行时生成）
├── docs/                   # 文档目录
│   └── README.md           # 开发文档
├── stock_monitor/          # 主程序目录
│   ├── __init__.py
│   ├── config/             # 配置管理
│   ├── ui/                 # 用户界面
│   ├── data/               # 数据处理
│   ├── utils/              # 工具函数
│   └── resources/          # 资源文件
├── tests/                  # 测试目录
└── dist/                   # 构建输出目录
```

## 开发指南

### 代码规范

- 遵循PEP 8代码规范
- 使用类型注解
- 函数和类需要添加文档字符串
- 重要逻辑需要添加注释

### 模块说明

#### config 模块
处理配置文件的加载和保存。

#### ui 模块
处理用户界面相关组件。

#### data 模块
处理股票数据和行情数据。

#### utils 模块
提供通用工具函数。

### 添加新功能

1. 根据功能类型选择合适的模块
2. 编写代码并添加必要注释
3. 添加相应的单元测试
4. 更新文档

## 测试

### 运行测试

```bash
# 运行所有测试
python test_runner.py

# 运行特定模块测试
python -m pytest tests/test_stocks.py -v
```

### 测试结构

- `tests/test_stocks.py` - 股票数据处理测试
- `tests/test_quotation.py` - 行情数据处理测试
- `tests/test_config.py` - 配置管理测试
- `tests/test_utils.py` - 工具函数测试
- `tests/test_ui_components.py` - UI组件测试

## 构建和发布

### 构建可执行文件

```bash
python build.py
```

构建后的可执行文件位于 `dist/stock_monitor.exe`

### GitHub Actions 自动构建

项目配置了GitHub Actions，当main.py文件发生变化时会自动构建并发布。

## 贡献指南

欢迎提交Issue和Pull Request来改进项目！

### 提交Issue

- 请使用清晰的标题描述问题
- 详细描述问题出现的场景和复现步骤
- 提供系统环境信息（操作系统、Python版本等）

### 提交Pull Request

1. Fork项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

### 代码审查

所有Pull Request都需要经过代码审查才能合并。

### 开发流程

1. 确保代码符合项目规范
2. 添加必要的单元测试
3. 确保所有测试通过
4. 更新相关文档
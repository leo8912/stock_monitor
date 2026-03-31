# PyInstaller 打包问题修复说明

## 问题描述

GitHub Actions 自动编译的程序运行时出现模块找不到的错误：
1. `ModuleNotFoundError: No module named 'akshare'`
2. `ModuleNotFoundError: No module named 'mootdx'`

## 根本原因

akshare 和 mootdx 都是依赖关系非常复杂的库，包含大量动态导入和隐式依赖。PyInstaller 的静态分析无法完全捕获所有依赖项。

- **akshare**: 用于获取股票财务数据、行情数据等
- **mootdx**: 用于获取通达信行情数据

## 解决方案

### 1. 增强的 spec 文件配置

**文件**: `stock_monitor.spec`

主要改进：
- ✅ 显式列出 akshare 的所有常用子模块
- ✅ 使用 `collect_submodules('akshare')` 收集所有子模块
- ✅ 使用 `collect_data_files('akshare', include_py_files=True)` 收集数据文件
- ✅ 添加 pandas、lxml、bs4、html5lib 等相关依赖
- ✅ 添加自定义 hooks 路径支持

### 2. 自定义 PyInstaller Hooks

**文件**: 
- `stock_monitor/hooks/hook-akshare.py`
- `stock_monitor/hooks/hook-mootdx.py`

功能：
- 专门为 akshare 和 mootdx 创建独立的 hook 文件
- 显式声明所有可能的动态导入
- 收集所有数据文件和子模块

### 3. GitHub Actions 工作流优化

**文件**: `.github/workflows/pack-release.yml`

改进：
- ✅ 强制重新安装 akshare 确保路径可访问
- ✅ 强制重新安装 mootdx 确保路径可访问
- ✅ 添加 akshare 和 mootdx 安装验证步骤
- ✅ 添加构建日志输出便于调试

### 4. 代码层面优化（备选）

**文件**: `stock_monitor/core/financial_filter.py`

改动：
- 将 akshare 导入改为延迟导入（在需要时才导入）
- 这样即使打包时有遗漏，也能在使用时才发现而非启动就崩溃

## 测试方法

### 本地测试打包

```powershell
# 清理之前的构建
Remove-Item -Recurse -Force build,dist

# 执行打包
pyinstaller -y stock_monitor.spec

# 测试运行
.\dist\stock_monitor\stock_monitor.exe
```

### 查看打包日志

打包时会输出详细信息：
- 收集的隐藏导入数量
- 收集的数据文件数量
- 使用的 hooks 路径

## 关键依赖列表

以下模块已显式包含：

### akshare 核心模块
- akshare.stock.*
- akshare.index
- akshare.fund
- akshare.common
- akshare.utils

### mootdx 核心模块
- mootdx.quotes
- mootdx.business
- mootdx.utils
- mootdx.client
- mootdx.factory

### 解析库
- lxml
- beautifulsoup4 (bs4)
- html5lib

### 数据处理
- pandas (含所有子模块)
- numpy
- openpyxl
- xlrd

### 网络相关
- requests
- urllib3
- charset_normalizer
- chardet

### 其他
- jsonpath
- simplejson
- demjson3
- tqdm
- tabulate

## 如果仍然失败

1. **查看详细日志**：打包时使用 `--log-level=DEBUG`
2. **手动测试**：在 GitHub Actions 环境 SSH 调试
3. **简化方案**：考虑将 akshare 功能改为可选功能，不使用时不加载

## 相关文件

- `stock_monitor.spec` - PyInstaller 配置文件
- `stock_monitor/hooks/hook-akshare.py` - akshare 专用 hook
- `stock_monitor/hooks/hook-mootdx.py` - mootdx 专用 hook
- `.github/workflows/pack-release.yml` - CI/CD 工作流
- `requirements.txt` - Python 依赖列表
- `PACKAGING_FIX.md` - 本修复说明文档

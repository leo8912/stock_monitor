# 实施计划 - BAT 脚本更新方案 (方案一)

## 目标
用轻量级、健壮的 Windows BAT 脚本方案替换复杂的独立 `updater.exe` 机制。这将消除进程锁定问题，降低构建复杂性，并移除 `psutil` 依赖。

## 拟定变更

### 1. 重构 `stock_monitor/core/updater.py`
我们将重写 `AppUpdater` 类中的 `install_update` 方法，直接在主程序中执行以下步骤：
1.  **解压**: 使用 Python 内置的 `zipfile` 模块将下载的 `stock_monitor.zip` 解压到临时目录 (`temp_update`).
2.  **生成脚本**: 在根目录生成一个 `update.bat` 文件。
    -   **循环等待**: 等待主程序进程 PID 消失。
    -   **复制覆盖**: 使用 `xcopy` 强制将 `temp_update` 中的文件覆盖到安装根目录。
    -   **清理**: 删除 `temp_update` 目录。
    -   **重启**: 启动 `stock_monitor.exe`。
    -   **自删除**: 删除 `.bat` 文件自身。
3.  **执行与退出**: 以后台分离模式启动 BAT 脚本，然后立即调用 `os._exit(0)`。

### 2. 清理依赖与构建配置
-   **`requirements.txt`**: 移除 `psutil` (之前是为独立 updater 添加的；主程序在缺失该库时有备用方案)。
-   **`.github/workflows/pack-release.yml`**:
    -   移除构建 `updater.exe` 的 PyInstaller 命令。
    -   移除复制 `updater.exe` 的步骤。
    -   从 `stock_monitor` 的构建参数中移除 `dist/updater.exe`。

### 3. 清理工作
-   **删除 `updater.py`**: (已通过命令完成)。
-   **版本升级**: 将版本更新为 **v2.6.0**，以标志架构的重大简化。

## 验证计划

### 手动验证
需要用户配合：
1.  构建新版本 (GitHub Actions)。
2.  手动安装 v2.6.0。
3.  等待 v2.6.1 (或模拟更新) 以验证 BAT 脚本是否正常触发。
    -   *模拟方法*: 我可以提供一段代码，创建一个伪造的 zip 包并调用 `install_update` 来测试。

### 自动化测试
-   由于涉及进程终止和外部脚本执行，全自动测试较难实现。
-   我们将依赖 Windows `choice` / `ping` / `timeout` 命令的稳定性。

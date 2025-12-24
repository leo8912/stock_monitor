# 任务清单

- [x] **重构更新核心逻辑** <!-- id: 0 -->
    - [x] 重写 `stock_monitor/core/updater.py` <!-- id: 1 -->
    - [x] 实现 ZIP 解压逻辑 <!-- id: 2 -->
    - [x] 实现 BAT 脚本生成逻辑 (包含 PID 等待、文件覆盖、重启) <!-- id: 3 -->
    - [x] 实现脚本启动与主程序强制退出 <!-- id: 4 -->
- [x] **清理项目依赖与配置** <!-- id: 5 -->
    - [x] 从 `requirements.txt` 移除 `psutil` <!-- id: 6 -->
    - [x] 从 `.github/workflows/pack-release.yml` 移除 updater 构建步骤 <!-- id: 7 -->
- [x] **版本发布准备** <!-- id: 8 -->
    - [x] 更新版本号至 v2.6.0 (`pyproject.toml`, `version.py`) <!-- id: 9 -->
    - [x] 更新 `CHANGELOG.md` 记录架构变更 <!-- id: 10 -->

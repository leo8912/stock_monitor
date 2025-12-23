# 项目优化待办事项

## 1. 文档修正
- [ ] **README.md**:
  - 修正依赖描述：项目依赖为 `PyQt6` 而非 `PyQt5`。
  - 检查并修正断链的文档引用（如 `API.md`）。
- [ ] **CHANGELOG.md**: 保持更新，确保 Release 脚本能正确提取日志。

## 2. 依赖管理
- [ ] **锁定版本**: 生成 `requirements.lock` 或在 `requirements.txt` 中精确指定版本（特别是 PyQt 和 Pandas）。
- [ ] **清理依赖**: 检查并移除不必要的依赖（如 `openpyxl`，如果未被使用）。

## 3. 代码质量与规范
- [ ] **Linting & Formatting**:
  - 引入 `black` (格式化) 和 `ruff` (Linter)。
  - 添加 `.pre-commit-config.yaml`。
- [ ] **类型提示**: 核心逻辑代码增加 Python Type Hints。

## 4. 打包与更新优化
- [ ] **Updater 安全性**: 下载更新包后增加 Hash 校验 (SHA256)。
- [ ] **构建优化**: GitHub Actions 增加 pip 缓存。

## 5. 测试增强
- [ ] **覆盖率**: 引入 `pytest-cov` 并生成报告。
- [ ] **GUI 测试**: 增加基础的 GUI 冒烟测试。

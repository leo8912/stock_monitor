# Learned Rules

## [LEARN] Compatibility: Python 3.9 不支持 `X | Y` 类型注解语法

**Date**: 2026-06-18
**Category**: Compatibility
**Mistake**: 在 `quant_worker.py` 和 `wave_analyzer.py` 中使用了 `str | None`、`dict[str, Any] | None` 等类型注解语法，导致 PyInstaller 打包版（Python 3.9）运行时闪退，报错 `unsupported operand type(s) for |: 'types.GenericAlias' and 'NoneType'`
**Correction**:
- 本项目打包环境为 Python 3.9，`X | Y` 联合类型语法需要 Python 3.10+
- 解决方案：在文件顶部添加 `from __future__ import annotations` 使注解延迟求值
- 或使用 `Optional[X]` / `Union[X, Y]` 替代
- 检查方法：`python -m py_compile <file>` 验证语法兼容性

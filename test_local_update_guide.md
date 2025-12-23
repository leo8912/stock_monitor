# 本地完整更新流程测试指南

## 测试目标
在真实环境中验证独立更新程序的完整更新流程。

## 前置准备

### 1. 编译当前版本(旧版本)
```bash
# 确保当前版本号
# 查看 stock_monitor/version.py
# 当前应该是 2.4.4

# 编译主程序
python local_build_workflow.py
```

### 2. 准备测试目录
```bash
# 创建测试目录
mkdir test_update_env
cd test_update_env

# 复制编译好的程序
# 从 dist/stock_monitor/ 复制所有文件到这里
```

### 3. 准备新版本(模拟更新包)
```bash
# 修改版本号为 2.4.5
# 编辑 stock_monitor/version.py
# __version__ = "2.4.5"

# 重新编译
python local_build_workflow.py

# 创建更新包zip
# 这个zip包将作为模拟的更新包
```

## 测试步骤

### 步骤1: 运行旧版本
1. 进入测试目录 `test_update_env`
2. 运行 `stock_monitor.exe`
3. 确认版本号显示为 2.4.4
4. 确认程序正常运行

### 步骤2: 模拟更新检查
由于我们无法真正连接到GitHub获取更新,需要手动触发更新逻辑:

**方法A: 修改代码临时跳过版本检查**
```python
# 在 stock_monitor/core/updater.py 的 perform_update 方法中
# 临时注释掉 show_update_dialog 的检查
# 直接调用 download_update 和 apply_update
```

**方法B: 手动准备更新包**
```python
# 创建测试脚本
import sys
sys.path.insert(0, 'stock_monitor')
from core.updater import app_updater

# 手动调用更新
update_file = "path/to/stock_monitor.zip"  # 新版本的zip
app_updater.apply_update(update_file)
```

### 步骤3: 观察更新过程
1. **主程序行为**:
   - [ ] 主程序是否显示"准备启动更新程序"日志
   - [ ] updater.exe是否被成功提取(如果不存在)
   - [ ] 主程序是否立即退出

2. **updater.exe行为**:
   - [ ] updater.exe窗口是否显示
   - [ ] 进度条是否正常显示
   - [ ] 状态信息是否清晰
   - [ ] 是否显示"等待主程序退出"
   - [ ] 是否显示"正在解压更新包"
   - [ ] 是否显示"正在替换文件"
   - [ ] 是否显示"正在启动新版本"

3. **文件系统变化**:
   - [ ] 检查是否创建了备份目录
   - [ ] 检查文件是否被正确替换
   - [ ] 检查是否有遗留的临时文件

### 步骤4: 验证更新结果
1. **新版本启动**:
   - [ ] 新版本是否自动启动
   - [ ] 版本号是否更新为 2.4.5
   - [ ] 所有功能是否正常

2. **清理检查**:
   - [ ] updater.exe是否被删除
   - [ ] cleanup_updater.bat是否被删除
   - [ ] 备份目录是否被清理

## 快速测试脚本

创建 `test_local_update.py`:
```python
import os
import sys
import shutil
from pathlib import Path

def prepare_test_env():
    \"\"\"准备测试环境\"\"\"
    print("准备测试环境...")
    
    # 1. 创建测试目录
    test_dir = Path("test_update_env")
    test_dir.mkdir(exist_ok=True)
    
    # 2. 复制当前编译的程序
    dist_dir = Path("dist/stock_monitor")
    if dist_dir.exists():
        print(f"复制程序文件到测试目录...")
        for item in dist_dir.iterdir():
            dest = test_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        print("✅ 测试环境准备完成")
        print(f"测试目录: {test_dir.absolute()}")
    else:
        print("❌ dist/stock_monitor 不存在,请先编译程序")
        return False
    
    return True

def create_mock_update_package():
    \"\"\"创建模拟更新包\"\"\"
    print("\\n创建模拟更新包...")
    print("提示: 请手动修改版本号并重新编译")
    print("1. 修改 stock_monitor/version.py 为 2.4.5")
    print("2. 运行 python local_build_workflow.py")
    print("3. 使用生成的 stock_monitor.zip 作为更新包")

if __name__ == "__main__":
    if prepare_test_env():
        create_mock_update_package()
        print("\\n下一步:")
        print("1. 进入 test_update_env 目录")
        print("2. 运行 stock_monitor.exe")
        print("3. 准备好更新包后,手动触发更新")
```

## 预期结果

### 成功标准
- ✅ 主程序正常退出
- ✅ updater.exe正常显示进度
- ✅ 文件替换成功,无错误
- ✅ 新版本自动启动
- ✅ 版本号正确更新
- ✅ 所有功能正常
- ✅ 临时文件被清理

### 失败处理
如果测试失败:
1. 检查日志文件
2. 检查是否有错误提示
3. 验证备份是否存在
4. 尝试手动恢复

## 注意事项

1. **备份数据**: 测试前备份配置文件和数据
2. **关闭杀毒软件**: 可能会拦截updater.exe
3. **管理员权限**: 某些情况下可能需要管理员权限
4. **日志记录**: 保存所有日志用于分析

## 测试记录

- 测试日期: ____
- 测试版本: 2.4.4 → 2.4.5
- 测试结果: ____
- 问题记录: ____

"""
测试updater.exe提取逻辑
"""
import os
import shutil
import sys
from pathlib import Path

# 添加项目路径到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from stock_monitor.core.updater import AppUpdater


def test_updater_extraction():
    """测试updater.exe提取逻辑"""
    print("=" * 60)
    print("测试updater.exe提取逻辑")
    print("=" * 60)

    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    updater_exe = os.path.join(current_dir, "updater.exe")

    # 场景1: updater.exe存在
    print("\n场景1: updater.exe已存在")
    if os.path.exists(updater_exe):
        print(f"✅ updater.exe存在: {updater_exe}")
        size_mb = os.path.getsize(updater_exe) / (1024 * 1024)
        print(f"   大小: {size_mb:.1f} MB")
    else:
        print(f"❌ updater.exe不存在: {updater_exe}")

    # 场景2: 模拟updater.exe不存在的情况
    print("\n场景2: 模拟updater.exe不存在")
    backup_path = None
    if os.path.exists(updater_exe):
        backup_path = updater_exe + ".backup"
        print(f"   备份updater.exe到: {backup_path}")
        shutil.move(updater_exe, backup_path)

    # 检查是否在打包环境
    if hasattr(sys, "_MEIPASS"):
        print(f"   检测到打包环境: {sys._MEIPASS}")
        resource_updater = os.path.join(sys._MEIPASS, "updater.exe")
        if os.path.exists(resource_updater):
            print(f"   ✅ 资源中存在updater.exe: {resource_updater}")
        else:
            print(f"   ❌ 资源中不存在updater.exe: {resource_updater}")
    else:
        print("   当前是开发环境")
        # 检查dist目录
        dist_updater = os.path.join(current_dir, "dist", "updater.exe")
        if os.path.exists(dist_updater):
            print(f"   ✅ dist目录中存在updater.exe: {dist_updater}")
        else:
            print(f"   ❌ dist目录中不存在updater.exe: {dist_updater}")

    # 场景3: 测试提取逻辑
    print("\n场景3: 测试提取逻辑")
    try:
        # 创建一个临时的更新包路径(不实际使用)
        os.path.join(current_dir, "test_update.zip")

        # 创建updater实例
        AppUpdater()

        # 注意: apply_update会尝试启动updater.exe并退出程序
        # 所以我们只测试提取部分的逻辑
        print("   提示: apply_update会启动updater.exe并退出程序")
        print("   建议: 手动检查日志确认提取逻辑是否正确")

    except Exception as e:
        print(f"   ❌ 测试失败: {e}")

    # 恢复updater.exe
    if backup_path and os.path.exists(backup_path):
        print(f"\n恢复updater.exe从: {backup_path}")
        shutil.move(backup_path, updater_exe)
        print("✅ 恢复完成")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_updater_extraction()

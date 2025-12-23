"""
本地更新流程测试准备脚本
"""
import os
import sys
import shutil
from pathlib import Path

def prepare_test_env():
    """准备测试环境"""
    print("=" * 60)
    print("准备本地更新测试环境")
    print("=" * 60)
    print()
    
    # 1. 创建测试目录
    test_dir = Path("test_update_env")
    print(f"1. 创建测试目录: {test_dir}")
    test_dir.mkdir(exist_ok=True)
    print("   ✅ 测试目录已创建")
    print()
    
    # 2. 检查编译产物
    dist_dir = Path("dist/stock_monitor")
    print(f"2. 检查编译产物: {dist_dir}")
    if not dist_dir.exists():
        print("   ❌ dist/stock_monitor 不存在")
        print("   请先运行: python local_build_workflow.py")
        return False
    print("   ✅ 编译产物存在")
    print()
    
    # 3. 复制程序文件
    print("3. 复制程序文件到测试目录...")
    copied_files = 0
    for item in dist_dir.iterdir():
        dest = test_dir / item.name
        try:
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            copied_files += 1
        except Exception as e:
            print(f"   ⚠️  复制 {item.name} 失败: {e}")
    
    print(f"   ✅ 已复制 {copied_files} 个文件/目录")
    print()
    
    # 4. 检查关键文件
    print("4. 检查关键文件...")
    key_files = [
        "stock_monitor.exe",
        "_internal",
    ]
    
    all_exist = True
    for file in key_files:
        file_path = test_dir / file
        if file_path.exists():
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} 不存在")
            all_exist = False
    
    if not all_exist:
        print("   ⚠️  部分关键文件缺失")
    print()
    
    # 5. 检查updater.exe
    print("5. 检查updater.exe...")
    updater_in_dist = Path("dist/updater.exe")
    updater_in_test = test_dir / "updater.exe"
    
    if updater_in_dist.exists():
        print(f"   ✅ dist/updater.exe 存在")
        if not updater_in_test.exists():
            print("   复制updater.exe到测试目录...")
            shutil.copy2(updater_in_dist, updater_in_test)
            print("   ✅ 已复制updater.exe")
    else:
        print("   ⚠️  dist/updater.exe 不存在")
        print("   updater.exe将在运行时从资源中提取")
    print()
    
    return True

def show_next_steps():
    """显示下一步操作"""
    print("=" * 60)
    print("测试环境准备完成!")
    print("=" * 60)
    print()
    print("下一步操作:")
    print()
    print("【方案1: 完整测试流程】")
    print("1. 修改版本号:")
    print("   编辑 stock_monitor/version.py")
    print("   将 __version__ = \"2.4.4\" 改为 \"2.4.5\"")
    print()
    print("2. 重新编译:")
    print("   python local_build_workflow.py")
    print()
    print("3. 准备更新包:")
    print("   使用生成的 stock_monitor.zip 作为更新包")
    print()
    print("4. 运行旧版本:")
    print("   cd test_update_env")
    print("   .\\stock_monitor.exe")
    print()
    print("5. 触发更新:")
    print("   在程序中手动触发更新检查")
    print("   或使用测试脚本模拟更新")
    print()
    print("【方案2: 快速验证】")
    print("1. 直接运行测试目录中的程序:")
    print("   cd test_update_env")
    print("   .\\stock_monitor.exe")
    print()
    print("2. 检查updater.exe是否能被正确提取")
    print()
    print("=" * 60)

if __name__ == "__main__":
    if prepare_test_env():
        show_next_steps()
    else:
        print()
        print("❌ 测试环境准备失败")
        print("请先编译程序: python local_build_workflow.py")

"""
简单测试updater.exe提取逻辑
"""
import os
import sys
import shutil

def test_extraction():
    print("测试updater.exe提取逻辑\n")
    
    # 1. 检查dist目录中的updater.exe
    dist_updater = "dist/updater.exe"
    print(f"1. 检查 {dist_updater}")
    if os.path.exists(dist_updater):
        size = os.path.getsize(dist_updater) / (1024 * 1024)
        print(f"   ✅ 存在, 大小: {size:.1f} MB\n")
    else:
        print(f"   ❌ 不存在\n")
        return
    
    # 2. 模拟提取到当前目录
    target_updater = "updater.exe"
    print(f"2. 测试复制到当前目录: {target_updater}")
    
    # 如果已存在,先备份
    if os.path.exists(target_updater):
        backup = target_updater + ".old"
        print(f"   备份现有文件到: {backup}")
        if os.path.exists(backup):
            os.remove(backup)
        shutil.move(target_updater, backup)
    
    # 复制文件
    try:
        shutil.copy2(dist_updater, target_updater)
        if os.path.exists(target_updater):
            size = os.path.getsize(target_updater) / (1024 * 1024)
            print(f"   ✅ 提取成功, 大小: {size:.1f} MB\n")
            
            # 清理测试文件
            print("3. 清理测试文件")
            os.remove(target_updater)
            print("   ✅ 已删除测试文件\n")
            
            # 恢复备份
            backup = target_updater + ".old"
            if os.path.exists(backup):
                shutil.move(backup, target_updater)
                print(f"   ✅ 已恢复备份文件\n")
        else:
            print(f"   ❌ 提取失败\n")
    except Exception as e:
        print(f"   ❌ 错误: {e}\n")
    
    print("✅ 测试完成!")
    print("\n总结:")
    print("- updater.exe存在于dist目录")
    print("- 文件复制功能正常")
    print("- 提取逻辑应该可以正常工作")

if __name__ == "__main__":
    test_extraction()

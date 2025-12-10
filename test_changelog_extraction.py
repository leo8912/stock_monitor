#!/usr/bin/env python3
"""
本地测试更新日志提取功能的脚本
用于在不触发GitHub Actions的情况下验证CHANGELOG.md解析逻辑
"""

import re
import sys
from pathlib import Path

def extract_changelog(version):
    """
    从CHANGELOG.md中提取指定版本的更新日志
    
    Args:
        version (str): 版本号，例如"2.0.7"
        
    Returns:
        str: 提取的更新日志内容
    """
    # 确保在项目根目录下运行
    project_root = Path(__file__).parent
    changelog_path = project_root / "CHANGELOG.md"
    
    if not changelog_path.exists():
        print(f"错误: 找不到CHANGELOG.md文件 ({changelog_path})")
        return None
        
    # 读取CHANGELOG.md文件
    try:
        with open(changelog_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"读取CHANGELOG.md时出错: {e}")
        return None
    
    print(f"处理版本号: {version}")
    
    # 处理版本号（去掉开头的'v'字符）
    if version.startswith('v'):
        version = version[1:]
    
    print(f"处理后的版本号: {version}")
    
    # 构造正则表达式匹配特定版本的日志
    # 匹配 ## [v2.0.4] - 2025-12-10 或 ## [v2.0.4] 这样的格式
    pattern = r"## \[" + re.escape("v" + version) + r"\](.*?)(?=## \[v|\Z)"
    print(f"使用的正则表达式: {pattern}")
    
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        changelog = match.group(1).strip()
        print("成功提取日志:")
        return changelog
    else:
        print("未找到匹配的日志")
        return "暂无详细更新日志"

def main():
    """主函数"""
    print("=== 更新日志提取本地测试工具 ===\n")
    
    # 获取版本号参数
    if len(sys.argv) > 1:
        version = sys.argv[1]
    else:
        # 默认使用当前版本
        version_py_path = Path(__file__).parent / "stock_monitor" / "version.py"
        try:
            with open(version_py_path, 'r', encoding='utf-8') as f:
                version_content = f.read()
                match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", version_content)
                if match:
                    version = match.group(1)
                else:
                    print("无法从version.py中提取版本号，请提供版本号参数")
                    return
        except Exception as e:
            print(f"读取version.py时出错: {e}")
            return
    
    print(f"测试版本: {version}\n")
    
    # 提取更新日志
    changelog = extract_changelog(version)
    
    if changelog is not None:
        print("-" * 50)
        print(changelog)
        print("-" * 50)
        print("\n测试完成!")

if __name__ == "__main__":
    main()
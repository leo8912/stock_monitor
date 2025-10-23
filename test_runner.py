#!/usr/bin/env python3
"""
测试运行器 - 运行所有单元测试
"""

import unittest
import sys
import os

def run_all_tests():
    """运行所有测试"""
    # 添加测试目录到路径
    test_dir = os.path.join(os.path.dirname(__file__), 'tests')
    sys.path.insert(0, test_dir)
    
    # 发现并运行所有测试
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()

if __name__ == '__main__':
    print("=== 运行所有单元测试 ===")
    success = run_all_tests()
    if success:
        print("\n🎉 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败！")
        sys.exit(1)
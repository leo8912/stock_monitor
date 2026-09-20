#!/usr/bin/env python3
"""
测试更新功能的简单脚本
"""

import pytest

from stock_monitor.core.updater import AppUpdater

# 此测试会访问 GitHub 的真实发布接口；默认单元测试必须保持离线、确定且不
# 启动网络线程。需要验证线上更新链路时显式执行 ``pytest -m integration``。
pytestmark = pytest.mark.integration


def test_update_check():
    """测试检查更新功能"""
    print("开始测试更新功能...")

    # 创建更新器实例
    updater = AppUpdater()

    # 检查更新
    print("检查是否有新版本...")
    result = updater.check_for_updates()

    if result is True:
        print("发现新版本!")
        print(f"最新版本信息: {updater.latest_release_info}")
    elif result is False:
        print("当前已是最新版本")
    else:
        print("检查更新失败，可能是网络问题")

    return result


if __name__ == "__main__":
    test_update_check()

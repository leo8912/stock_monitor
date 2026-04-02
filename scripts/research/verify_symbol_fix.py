import os
import sys

# 确保能导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_monitor.core.container import container
from stock_monitor.core.stock_data_fetcher import StockDataFetcher


def verify_fix():
    fetcher = container.get(StockDataFetcher)
    registry = fetcher.name_registry

    # 强制进行一次全量同步
    print("正在增量同步名称字典...")
    registry.sync_mootdx_names()

    # 检查两个冲突代码
    sh_index = registry.get_name("sh000001")
    sz_bank = registry.get_name("sz000001")

    print("\n结果验证:")
    print(f"sh000001 -> {sh_index}")
    print(f"sz000001 -> {sz_bank}")

    if sh_index == "上证指数" and sz_bank == "平安银行":
        print("\n✅ 修复成功：名称冲突已解决。")
    else:
        print("\n❌ 修复失败：名称仍存在冲突。")


if __name__ == "__main__":
    verify_fix()

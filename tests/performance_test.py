#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能基准测试脚本
用于测试股票数据处理和缓存机制的性能
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from stock_monitor.core.stock_manager import StockManager


def benchmark_stock_processing(
    stock_manager: StockManager, stock_codes: List[str], iterations: int = 100
) -> Dict[str, Any]:
    """
    测试股票数据处理性能

    Args:
        stock_manager: 股票管理器实例
        stock_codes: 股票代码列表
        iterations: 测试迭代次数

    Returns:
        Dict[str, Any]: 性能测试结果
    """
    print(f"开始股票数据处理性能测试，迭代次数: {iterations}")

    # 准备测试数据
    test_data = {}
    for code in stock_codes:
        test_data[code] = {
            "name": f"测试股票{code}",
            "now": 10.0,
            "close": 9.5,
            "high": 10.5,
            "low": 9.0,
            "bid1": 10.0,
            "ask1": 10.1,
            "bid1_vol": 1000000,
            "ask1_vol": 500000,
        }

    # 测试股票数据获取性能
    start_time = time.time()
    for _ in range(iterations):
        stock_manager.get_stock_list_data(stock_codes)
    end_time = time.time()

    processing_time = end_time - start_time
    avg_time_per_iteration = processing_time / iterations

    result = {
        "total_time": processing_time,
        "iterations": iterations,
        "avg_time_per_iteration": avg_time_per_iteration,
        "stocks_processed_per_second": len(stock_codes) * iterations / processing_time,
    }

    print("股票数据处理性能测试完成:")
    print(f"  总耗时: {processing_time:.4f}秒")
    print(f"  平均每次迭代耗时: {avg_time_per_iteration:.6f}秒")
    print(f"  每秒处理股票数: {result['stocks_processed_per_second']:.2f}")

    return result


def benchmark_cache_performance(
    stock_manager: StockManager, stock_codes: List[str], iterations: int = 1000
) -> Dict[str, Any]:
    """
    测试缓存性能

    Args:
        stock_manager: 股票管理器实例
        stock_codes: 股票代码列表
        iterations: 测试迭代次数

    Returns:
        Dict[str, Any]: 缓存性能测试结果
    """
    print(f"\n开始缓存性能测试，迭代次数: {iterations}")

    # 准备测试数据
    test_data = {}
    for code in stock_codes:
        test_data[code] = json.dumps(
            {"name": f"测试股票{code}", "now": 10.0, "close": 9.5}, sort_keys=True
        )

    # 测试缓存命中性能
    start_time = time.time()
    for _ in range(iterations):
        for code in stock_codes:
            stock_manager._process_single_stock_data_cached(code, test_data[code])
    end_time = time.time()

    cache_hit_time = end_time - start_time
    avg_cache_hit_time = cache_hit_time / (iterations * len(stock_codes))

    # 测试缓存未命中性能（通过修改数据使缓存失效）
    start_time = time.time()
    for i in range(iterations):
        for code in stock_codes:
            modified_data = json.dumps(
                {
                    "name": f"测试股票{code}",
                    "now": 10.0 + i * 0.01,  # 稍微修改数据确保缓存未命中
                    "close": 9.5,
                },
                sort_keys=True,
            )
            stock_manager._process_single_stock_data_cached(code, modified_data)
    end_time = time.time()

    cache_miss_time = end_time - start_time
    avg_cache_miss_time = cache_miss_time / (iterations * len(stock_codes))

    result = {
        "cache_hit_total_time": cache_hit_time,
        "cache_miss_total_time": cache_miss_time,
        "avg_cache_hit_time": avg_cache_hit_time,
        "avg_cache_miss_time": avg_cache_miss_time,
        "cache_hit_rate": cache_hit_time / (cache_hit_time + cache_miss_time),
        "performance_ratio": avg_cache_miss_time / avg_cache_hit_time
        if avg_cache_hit_time > 0
        else float("inf"),
    }

    print("缓存性能测试完成:")
    print(f"  缓存命中总耗时: {cache_hit_time:.4f}秒")
    print(f"  缓存未命中总耗时: {cache_miss_time:.4f}秒")
    print(f"  平均缓存命中时间: {avg_cache_hit_time:.8f}秒")
    print(f"  平均缓存未命中时间: {avg_cache_miss_time:.8f}秒")
    print(f"  缓存命中率: {result['cache_hit_rate']:.2%}")
    print(f"  性能提升倍数: {result['performance_ratio']:.2f}x")

    return result


def main():
    """主函数"""
    print("=== 股票监控系统性能基准测试 ===\n")

    # 创建股票管理器实例
    stock_manager = StockManager()

    # 定义测试用的股票代码
    test_stocks = ["sh000001", "sz000001", "sh600000", "sz000002", "sh600036"]

    # 执行股票数据处理性能测试
    processing_result = benchmark_stock_processing(stock_manager, test_stocks, 100)

    # 执行缓存性能测试
    cache_result = benchmark_cache_performance(stock_manager, test_stocks, 1000)

    # 输出汇总报告
    print("\n=== 性能测试汇总报告 ===")
    print("股票数据处理性能:")
    print(f"  每秒处理股票数: {processing_result['stocks_processed_per_second']:.2f}")
    print(f"  平均每次迭代耗时: {processing_result['avg_time_per_iteration']:.6f}秒")

    print("\n缓存性能:")
    print(f"  缓存命中平均时间: {cache_result['avg_cache_hit_time']:.8f}秒")
    print(f"  缓存未命中平均时间: {cache_result['avg_cache_miss_time']:.8f}秒")
    print(f"  性能提升倍数: {cache_result['performance_ratio']:.2f}x")
    print(f"  缓存命中率: {cache_result['cache_hit_rate']:.2%}")

    # 保存测试结果到文件
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stock_processing": processing_result,
        "cache_performance": cache_result,
    }

    with open("performance_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n测试结果已保存到 performance_test_results.json")


if __name__ == "__main__":
    main()

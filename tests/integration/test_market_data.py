"""
测试市场数据获取方案
比较不同方案的可行性和数据质量
"""

import time

import easyquotation


def test_market_snapshot():
    """测试方案：market_snapshot"""
    print("=" * 60)
    print("测试方案：market_snapshot(prefix=True)")
    print("=" * 60)

    try:
        quotation = easyquotation.use("sina")
        snapshot = quotation.market_snapshot(prefix=True)

        if snapshot:
            print("✓ 成功获取数据")
            print(f"✓ 返回股票数量: {len(snapshot)}")

            # 统计涨跌
            up = 0
            down = 0
            flat = 0

            for _code, info in snapshot.items():
                if not isinstance(info, dict):
                    continue

                name = info.get("name", "")
                # 跳过指数
                if "指数" in name or "Ａ股" in name:
                    continue

                try:
                    close = float(info.get("close", 0))
                    now = float(info.get("now", 0))

                    if close == 0:
                        flat += 1
                    elif now > close:
                        up += 1
                    elif now < close:
                        down += 1
                    else:
                        flat += 1
                except:
                    continue

            total = up + down + flat
            print("✓ 统计结果:")
            print(f"  - 上涨: {up} ({up/total*100:.1f}%)")
            print(f"  - 下跌: {down} ({down/total*100:.1f}%)")
            print(f"  - 平盘: {flat} ({flat/total*100:.1f}%)")
            print(f"  - 总计: {total}")

            # 显示前5只股票
            print("\n✓ 示例数据（前5只）:")
            count = 0
            for code, info in snapshot.items():
                if count >= 5:
                    break
                if isinstance(info, dict):
                    name = info.get("name", "")
                    if "指数" not in name:
                        print(f"  {code}: {name}")
                        count += 1

            return True, total
        else:
            print("✗ 未获取到数据")
            return False, 0

    except Exception as e:
        print(f"✗ 错误: {e}")
        return False, 0


def test_market_indices():
    """测试方案：市场指数（涨跌家数）"""
    print("\n" + "=" * 60)
    print("测试方案：市场指数（sh880003, sz880003）")
    print("=" * 60)

    try:
        quotation = easyquotation.use("sina")

        # 测试多个可能的指数代码
        test_codes = [
            "sh880003",  # 上证涨跌家数
            "sz880003",  # 深证涨跌家数
            "sh000001",  # 上证指数
            "sz399001",  # 深证成指
        ]

        for code in test_codes:
            print(f"\n测试代码: {code}")
            try:
                data = quotation.stocks(code, prefix=True)
                if data and code in data:
                    info = data[code]
                    print("  ✓ 成功获取")
                    print(f"  名称: {info.get('name', 'N/A')}")
                    print(f"  现价: {info.get('now', 'N/A')}")
                    print(f"  涨跌: {info.get('changepercent', 'N/A')}%")

                    # 检查是否有涨跌家数字段
                    print(f"  所有字段: {list(info.keys())}")
                else:
                    print("  ✗ 未获取到数据")
            except Exception as e:
                print(f"  ✗ 错误: {e}")

        return False, 0  # 需要根据实际结果判断

    except Exception as e:
        print(f"✗ 错误: {e}")
        return False, 0


def test_all_method():
    """测试方案：quotation.all"""
    print("\n" + "=" * 60)
    print("测试方案：quotation.all")
    print("=" * 60)

    try:
        quotation = easyquotation.use("sina")
        all_data = quotation.all

        if all_data:
            print("✓ 成功获取数据")
            print(f"✓ 返回股票数量: {len(all_data)}")

            # 统计涨跌
            up = 0
            down = 0
            flat = 0

            for _code, info in all_data.items():
                if not isinstance(info, dict):
                    continue

                name = info.get("name", "")
                # 跳过指数
                if "指数" in name or "Ａ股" in name:
                    continue

                try:
                    close = float(info.get("close", 0))
                    now = float(info.get("now", 0))

                    if close == 0:
                        flat += 1
                    elif now > close:
                        up += 1
                    elif now < close:
                        down += 1
                    else:
                        flat += 1
                except:
                    continue

            total = up + down + flat
            print("✓ 统计结果:")
            print(f"  - 上涨: {up} ({up/total*100:.1f}%)")
            print(f"  - 下跌: {down} ({down/total*100:.1f}%)")
            print(f"  - 平盘: {flat} ({flat/total*100:.1f}%)")
            print(f"  - 总计: {total}")

            return True, total
        else:
            print("✗ 未获取到数据")
            return False, 0

    except Exception as e:
        print(f"✗ 错误: {e}")
        return False, 0


if __name__ == "__main__":
    print("开始测试市场数据获取方案...\n")

    # 测试方案1: market_snapshot
    success1, count1 = test_market_snapshot()
    time.sleep(2)

    # 测试方案2: 市场指数
    success2, count2 = test_market_indices()
    time.sleep(2)

    # 测试方案3: quotation.all
    success3, count3 = test_all_method()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"market_snapshot: {'✓ 可用' if success1 else '✗ 不可用'} (股票数: {count1})")
    print(f"市场指数方案: {'✓ 可用' if success2 else '✗ 不可用'}")
    print(f"quotation.all: {'✓ 可用' if success3 else '✗ 不可用'} (股票数: {count3})")

    print("\n推荐方案:")
    if count1 > count3:
        print("→ market_snapshot (数据更完整)")
    elif count3 > count1:
        print("→ quotation.all (数据更完整)")
    else:
        print("→ 两者数据量相同，建议使用 market_snapshot")

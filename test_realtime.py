"""
测试 market_snapshot 的实时性
对比 market_snapshot 和 stocks 单独查询的数据时效性
"""

import easyquotation
import time
from datetime import datetime

def test_realtime_comparison():
    """对比实时性"""
    print("=" * 80)
    print("测试 market_snapshot 的实时性")
    print("=" * 80)
    
    quotation = easyquotation.use('sina')
    
    # 选择一只活跃股票进行测试
    test_code = 'sh600000'  # 浦发银行
    
    print(f"\n测试股票: {test_code}")
    print("\n连续5次查询，对比两种方法的数据时效性：\n")
    
    for i in range(5):
        print(f"第 {i+1} 次查询 ({datetime.now().strftime('%H:%M:%S.%f')[:-3]})")
        print("-" * 80)
        
        # 方法1: market_snapshot
        start1 = time.time()
        snapshot = quotation.market_snapshot(prefix=True)
        time1 = time.time() - start1
        
        if test_code in snapshot:
            data1 = snapshot[test_code]
            print(f"market_snapshot:")
            print(f"  现价: {data1.get('now')}")
            print(f"  时间: {data1.get('date')} {data1.get('time')}")
            print(f"  耗时: {time1*1000:.0f}ms")
        
        # 方法2: 单独查询
        start2 = time.time()
        individual = quotation.stocks(test_code, prefix=True)
        time2 = time.time() - start2
        
        if test_code in individual:
            data2 = individual[test_code]
            print(f"\nstocks(单独查询):")
            print(f"  现价: {data2.get('now')}")
            print(f"  时间: {data2.get('date')} {data2.get('time')}")
            print(f"  耗时: {time2*1000:.0f}ms")
        
        # 对比
        if test_code in snapshot and test_code in individual:
            price_diff = abs(float(data1.get('now', 0)) - float(data2.get('now', 0)))
            time_same = (data1.get('time') == data2.get('time'))
            
            print(f"\n对比:")
            print(f"  价格差异: {price_diff}")
            print(f"  时间戳相同: {time_same}")
            print(f"  速度对比: market_snapshot {'更快' if time1 < time2 else '更慢'}")
        
        print()
        
        if i < 4:
            time.sleep(2)  # 等待2秒再查询
    
    print("=" * 80)
    print("结论:")
    print("如果两种方法的时间戳始终相同，说明 market_snapshot 是实时的")
    print("如果价格有差异或时间戳不同，说明 market_snapshot 有延迟")
    print("=" * 80)

if __name__ == '__main__':
    test_realtime_comparison()

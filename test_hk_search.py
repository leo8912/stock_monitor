import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stock_monitor.data.stocks import load_stock_data, enrich_pinyin

# 加载股票数据
stock_data = load_stock_data()
print(f"总股票数: {len(stock_data)}")

# 过滤出港股
hk_stocks = [s for s in stock_data if s['code'].startswith('hk')]
print(f"港股数: {len(hk_stocks)}")

# 丰富拼音信息
enriched_data = enrich_pinyin(stock_data)
print("拼音信息处理完成")

# 测试搜索功能
def test_search(text):
    results = []
    for s in enriched_data:
        if (text in s['code'].lower() or 
            text in s['name'].lower() or 
            text in s.get('pinyin', '') or 
            text in s.get('abbr', '')):
            results.append(s)
        elif s['code'].startswith('hk') and text in s['code'][2:]:
            results.append(s)
    
    print(f"搜索 '{text}' 找到 {len(results)} 个结果")
    for i, s in enumerate(results[:5]):
        print(f"  {s['code']}: {s['name']}")
    return results

# 测试几种情况
print("\n=== 测试搜索功能 ===")
test_search("hk00001")  # 精确港股代码
test_search("00001")    # 不带hk前缀的港股代码
test_search("长和")      # 港股名称
test_search("cheung")   # 港股拼音
from stock_monitor.data.updater import fetch_hk_stocks

# 获取港股数据
stocks = fetch_hk_stocks()
print(f"获取到 {len(stocks)} 只港股")

# 显示前10只港股，检查繁简转换是否正常工作
print("前10只港股:")
for i, stock in enumerate(stocks[:10]):
    print(f"  {stock['code']}: {stock['name']}")
    
    # 特别检查一些应该有繁简转换的股票名称
    if i == 0 and "长和" in stock['name']:
        print("  ✅ 繁简转换正常工作")
        break
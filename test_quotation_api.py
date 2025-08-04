import easyquotation

quotation = easyquotation.use('sina')  # 也可用 'tencent'

codes = ['sh000001', 'sz000001']  # 上证指数和平安银行

print('【批量获取】')
data = quotation.real(codes)
for code in codes:
    # 尝试不同的键来获取数据
    result = data.get(code) or data.get(code[2:])  # code[2:]是去掉sh/sz前缀的部分
    print(f'{code}: {result}')

print('\n【分别获取】')
for code in codes:
    single = quotation.real([code])
    print(f'{code}: {single}')

print('\n【原始返回数据结构】')
print("Keys in data:", list(data.keys()) if data else "None")
print(data)

# 测试其他可能的代码
print('\n【测试其他代码】')
other_codes = ['sh600460', 'sz002594']
other_data = quotation.real(other_codes)
for code in other_codes:
    result = other_data.get(code) or other_data.get(code[2:])
    print(f'{code}: {result}')
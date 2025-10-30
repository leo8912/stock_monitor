import pandas as pd

# 读取Excel文件，尝试不同的工作表和参数
excel_file = "test.xlsx"

# 读取所有工作表的名称
xls = pd.ExcelFile(excel_file)
print("工作表名称:", xls.sheet_names)

# 尝试读取每个工作表
for sheet_name in xls.sheet_names:
    print(f"\n工作表 '{sheet_name}' 的前10行:")
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        print(f"总行数: {len(df)}")
        print(f"总列数: {len(df.columns)}")
        print("列名:", list(df.columns))
        print("前10行数据:")
        print(df.head(10))
    except Exception as e:
        print(f"读取工作表 '{sheet_name}' 时出错: {e}")
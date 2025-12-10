import re

# 读取CHANGELOG.md文件
with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 要查找的版本
version = 'v2.0.1'

# 构造正则表达式来匹配指定版本的日志
# 首先尝试匹配带有日期的版本标题
pattern_with_date = r'## $$v' + re.escape(version) + r'$$ - .*?\n\n.*?(?=\n## $$v|\Z)'
match = re.search(pattern_with_date, content, re.DOTALL)

if not match:
    # 如果没有匹配到，尝试匹配不带日期的版本标题
    pattern_without_date = r'## $$v' + re.escape(version) + r'$$\n\n.*?(?=\n## $$v|\Z)'
    match = re.search(pattern_without_date, content, re.DOTALL)

if match:
    changelog = match.group(0).strip()
else:
    changelog = '暂无更新日志'

print("提取到的更新日志:")
print("=" * 50)
print(changelog)
print("=" * 50)
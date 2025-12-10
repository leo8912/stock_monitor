import re

# 读取CHANGELOG.md文件
with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 显示文件开头部分内容
print("文件开头内容:")
print(repr(content[:100]))

# 要查找的版本
version = 'v2.0.1'
print(f"\n查找版本: {version}")

# 测试简单的模式匹配
simple_pattern = '## $$v2.0.1$$'
simple_match = re.search(simple_pattern, content)
print(f"\n简单模式匹配结果: {simple_match}")

# 测试更复杂的模式
complex_pattern = '## $$v2.0.1$$ - 2025-12-10'
complex_match = re.search(complex_pattern, content)
print(f"复杂模式匹配结果: {complex_match}")

# 测试实际文件中的模式
actual_pattern = '## $$v2.0.1$$'
actual_match = re.search(actual_pattern, content)
print(f"实际模式匹配结果: {actual_match}")

# 显示匹配到的内容前后字符
if complex_match:
    start = max(0, complex_match.start() - 20)
    end = min(len(content), complex_match.end() + 20)
    print(f"匹配内容前后片段: {repr(content[start:end])}")
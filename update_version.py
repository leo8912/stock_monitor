import re
import os
import json
from datetime import datetime

def update_version_files(new_version):
    """更新所有需要版本号的文件，严格按照当前文档格式同步更新"""
    # 提取版本号数字部分（去掉v前缀）
    version_number = new_version[1:] if new_version.startswith('v') else new_version
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 更新main.py中的版本号
    with open('main.py', 'r+', encoding='utf-8') as f:
        content = f.read()
        # 更新版本号
        content = re.sub(r"APP_VERSION = 'v\d+\.\d+\.\d+'", 
                         f"APP_VERSION = '{new_version}'", content)
        # 更新更新日志中的版本记录
        content = re.sub(r'# v\d+\.\d+\.\d+ - \d{4}-\d{2}-\d{2}
# -', 
                         f'# {new_version} - {today}\n# -', content)
        f.seek(0)
        f.write(content)
        f.truncate()

    # 更新README.md中的版本号
    with open('README.md', 'r+', encoding='utf-8') as f:
        content = f.read()
        # 更新当前版本号（格式：**vX.X.X**）
        content = re.sub(r'\*\*v\d+\.\d+\.\d+\*\*', 
                        f'**{new_version}**', content)
        # 更新版本历史中的最新版本（格式：* **最新版本**: [vX.X.X]）
        content = re.sub(r'\* \*\*最新版本\*\*: \[v\d+\.\d+\.\d+\]', 
                        f'* **最新版本**: [{new_version}]', content)
        f.seek(0)
        f.write(content)
        f.truncate()

    # 更新CHANGELOG.md中的版本号
    with open('CHANGELOG.md', 'r+', encoding='utf-8') as f:
        content = f.read()
        # 检查是否已经有当前版本的条目
        version_header = f'## {new_version} ({today})'
        if version_header not in content:
            # 创建新版本日志
            changelog_entry = f"""
## {new_version} ({today})

### 🛠 更新内容
- 版本自动升级

---
"""
            # 插入到顶部
            content = changelog_entry + content
            f.seek(0)
            f.write(content)
            f.truncate()

if __name__ == '__main__':
    # 从环境变量获取新版本号
    new_version = os.getenv('NEW_VERSION', 'v1.0.7')
    update_version_files(new_version)
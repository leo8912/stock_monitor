"""
在settings_dialog.py和update_dialogs.py中添加constants导入的脚本
"""
import re

# 处理settings_dialog.py
with open('d:/code/stock/stock_monitor/ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 在NewSettingsDialog类前添加导入
if 'from stock_monitor.ui.constants import' not in content:
    content = content.replace(
        'class NewSettingsDialog(QDialog):',
        '# 导入UI常量\nfrom stock_monitor.ui.constants import WINDOW, COLORS, SPACING\n\n\nclass NewSettingsDialog(QDialog):'
    )
    
    with open('d:/code/stock/stock_monitor/ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ settings_dialog.py 导入已添加")

# 处理update_dialogs.py
with open('d:/code/stock/stock_monitor/ui/dialogs/update_dialogs.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 在ModernProgressDialog类前添加导入
if 'from stock_monitor.ui.constants import' not in content:
    content = content.replace(
        'class ModernProgressDialog(QDialog):',
        '# 导入UI常量\nfrom stock_monitor.ui.constants import WINDOW, COLORS\n\n\nclass ModernProgressDialog(QDialog):'
    )
    
    with open('d:/code/stock/stock_monitor/ui/dialogs/update_dialogs.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ update_dialogs.py 导入已添加")

print("\n完成!")

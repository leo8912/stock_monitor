# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('pyproject.toml', '.'),
    ('stock_monitor/resources/icon.ico', 'stock_monitor/resources'),
    ('stock_monitor/resources/stocks_base.db', 'stock_monitor/resources'),
    ('stock_monitor/resources/styles', 'stock_monitor/resources/styles'),
]

# Get paths for third-party files (using env vars from GitHub Action)
# In local development, you might need to set these manually or adjust paths.
import os
eq_path = os.environ.get('EQPATH')
if eq_path:
    datas.append((os.path.join(eq_path, 'stock_codes.conf'), 'easyquotation'))

zhconv_path = os.environ.get('ZHCONVPATH')
if zhconv_path:
    datas.append((os.path.join(zhconv_path, 'zhcdict.json'), 'zhconv'))

# --- Collect dependencies ---
pkgs_to_collect = ['akshare', 'pandas_ta', 'mootdx', 'pytz', 'certifi', 'pypinyin', 'lxml', 'beautifulsoup4', 'html5lib']
for pkg in pkgs_to_collect:
    tmp_ret = collect_all(pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

# Add specific hidden imports for akshare and its common sub-dependencies
hiddenimports += [
    'pandas',
    'requests',
    'urllib3',
    'charset_normalizer',
    'idna',
    'sqlalchemy',
]

block_cipher = None

a = Analysis(
    ['stock_monitor/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='stock_monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['stock_monitor/resources/icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='stock_monitor',
)

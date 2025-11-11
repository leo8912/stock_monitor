# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['stock_monitor\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('stock_monitor/resources/stock_basic.json', 'stock_monitor/resources'), ('stock_monitor/resources/icon.ico', 'stock_monitor/resources'), ('C:\\Users\\leo89\\AppData\\Local\\Programs\\Python\\Python313\\Lib\\site-packages\\easyquotation/stock_codes.conf', 'easyquotation')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='stock_monitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['stock_monitor\\resources\\icon.ico'],
)

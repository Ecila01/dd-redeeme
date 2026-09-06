# -*- mode: python ; coding: utf-8 -*-
# 兑了么 DD RedeeMe —— 便携版（onefile）打包配置
# 用法（项目根目录执行）：
#   .venv/Scripts/python -m PyInstaller --noconfirm --clean DDRedeeMe.spec
# 产物：dist/DD RedeeMe.exe（单文件便携版，assets 通过 sys._MEIPASS 读取）
# 入口是根目录 run.py（包上下文启动器），不能用 main.py（相对导入会崩）。

a = Analysis(
    ['run.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DD RedeeMe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

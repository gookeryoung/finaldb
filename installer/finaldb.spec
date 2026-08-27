# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：finaldb 单文件 GUI 可执行。

注意：
- 排除开发内部目录（tests/docs/.github 等，见 excludes）
- Widgets 界面无外部资源文件，无需 collect_data_files
- UPX 关闭：Win7 兼容目标下 UPX 压缩的 Qt DLL 易误报且收益有限
"""

import os

block_cipher = None

# 仓库根（spec 位于 installer/ 下）
_REPO = os.path.abspath(os.path.join(SPECPATH, ".."))
_ENTRY = os.path.join(_REPO, "src", "finaldb", "app.py")
_SRC = os.path.join(_REPO, "src")

datas = []
binaries = []

hiddenimports = [
    # dulwich porcelain 经由 dulwich 包名动态分发，显式声明保险
    "dulwich.porcelain",
]

# 排除的模块（减小体积 / 排除开发内部目录）
excludes = [
    "tkinter",
    "unittest",
    "pydoc",
    "tests",
    "pytest",
    "mypy",
    "ruff",
    "polars",
    "python_calamine",
]

a = Analysis(
    [_ENTRY],
    pathex=[_SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="finaldb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# 获取路径
spec_root = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_root)

block_cipher = None

# 查找 qfluentwidgets 包的位置
qfluentwidgets_path = None
for path in sys.path:
    potential_path = Path(path) / 'qfluentwidgets'
    if potential_path.exists():
        qfluentwidgets_path = str(potential_path)
        break

# 准备数据文件列表
datas_list = [
    (os.path.join(project_root, 'image', 'SIOM_logo.png'), 'image'),
    (os.path.join(project_root, 'image', 'DCS_Application_Logo.ico'), 'image'),
]

# 添加 qfluentwidgets 的资源文件
if qfluentwidgets_path:
    qfluentwidgets_resources = Path(qfluentwidgets_path)
    # 添加所有 qss, svg, png, json 等资源文件
    for pattern in ['**/*.qss', '**/*.svg', '**/*.png', '**/*.json', '**/*.ttf', '**/*.qm']:
        for file in qfluentwidgets_resources.glob(pattern):
            relative_path = file.relative_to(qfluentwidgets_resources.parent)
            datas_list.append((str(file), str(relative_path.parent)))

a = Analysis(
    ['seq_to_png_gui.py'],
    pathex=[spec_root],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'qfluentwidgets',
        'qfluentwidgets.common',
        'qfluentwidgets.components',
        'qfluentwidgets.window',
        'qframelesswindow',
        'darkdetect',
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'PIL._imaging',
        'numpy',
        'numpy.core',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SEQ_to_PNG_Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_root, 'image', 'DCS_icon_multi.ico'),
    version_file=None,
)

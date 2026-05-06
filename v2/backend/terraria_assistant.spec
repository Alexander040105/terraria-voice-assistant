# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_root = os.path.abspath(os.path.dirname(__file__))

pathex = [backend_root]

analysis = Analysis(
    [os.path.join(backend_root, "main.py")],
    pathex=pathex,
    binaries=[],
    datas=[
        (os.path.join(backend_root, "scraped_pages"), "scraped_pages"),
        (os.path.join(project_root, "chrome_langchain_db"), "chrome_langchain_db"),
    ],
    hiddenimports=["sentence_transformers"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="terraria_assistant",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

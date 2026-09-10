# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent

block_cipher = None

# Package data for modules that ship native DLLs or additional data.
datas = []
binaries = []
hiddenimports = []

for pkg in (
    "faster_whisper",
    "ctranslate2",
    "sqlite_vec",
    "piper",
    "onnxruntime",
    "llama_cpp",
):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Bundle the large model files and terraria.db so the package is self-contained.
MODELS_DIR = ROOT / "backend" / "models"
DATA_DIR = ROOT / "backend" / "data"
if MODELS_DIR.exists():
    datas.append((str(MODELS_DIR), "backend/models"))
if DATA_DIR.exists():
    datas.append((str(DATA_DIR), "backend/data"))

hiddenimports += [
    "uvicorn.logging",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.protocols.websockets.wsproto_impl",
    "fastapi",
    "pydantic",
    "pydantic_core",
    "starlette",
    "httptools",
    "websockets",
    "wsproto",
    "numpy",
    "sounddevice",
    "soundfile",
    "requests",
    "huggingface_hub",
    "tqdm",
    "psutil",
]

a = Analysis(
    ["backend_entry.py"],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "silero_vad_notorch", "PyInstaller"],
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
    name="assistant-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="assistant-backend",
)

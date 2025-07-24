# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

# --------------------------------------------------------------------
# Build a `datas` list of (src_path, dest_subdir)
# so that every file under src/moneymirror/resources/
# ends up under dist/moneymirror/resources/
# --------------------------------------------------------------------
proj_root = Path(os.getcwd())
res_src = proj_root / "src" / "moneymirror" / "resources"

datas = []
for root, _, files in os.walk(res_src):
    for filename in files:
        src_file = Path(root) / filename
        # relative to resources/ so we preserve subfolders (if any)
        rel_path = src_file.relative_to(res_src)
        # dest_subdir should be "resources" or "resources/subfolder"
        dest_subdir = Path("resources") / rel_path.parent
        datas.append((str(src_file), str(dest_subdir)))

# --------------------------------------------------------------------
# Now wire that into Analysis
# --------------------------------------------------------------------
a = Analysis(
    ["src/moneymirror/main.py"],
    pathex=[str(proj_root)],
    binaries=[],
    datas=datas,               # <-- your resources will be pulled in here
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="moneymirror",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    windowed=True,
    icon=str(res_src / "icon.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,   # <-- includes that `datas` list we built above
    strip=False,
    upx=True,
    name="moneymirror",
)


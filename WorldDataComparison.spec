# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.building.datastruct import TOC

root = Path(SPECPATH)

datas = [
    (str(root / "config"), "config"),
    (str(root / "data" / "worlddata.sqlite"), "data"),
    (str(root / "data" / "manifest.json"), "data"),
    (str(root / "data" / "quality_report.csv"), "data"),
    (str(root / "data" / "rejected.csv"), "data"),
]
for extra in (
    "NOTICE.txt",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "ROADMAP.md",
):
    if (root / extra).exists():
        datas.append((str(root / extra), "."))
if (root / "docs").is_dir():
    datas.append((str(root / "docs"), "docs"))
if (root / "data" / "groups.local.yaml").exists():
    datas.append((str(root / "data" / "groups.local.yaml"), "data"))

a = Analysis(
    [str(root / "launcher.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "matplotlib.backends.backend_qtagg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "matplotlib.backends.backend_tkagg",
        "notebook",
        "IPython",
        "jupyter",
        "pytest",
        "pyarrow",
        "sqlalchemy",
        "aiohttp",
        "zstandard",
        "tqdm",
        "pycountry",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtPdf",
        "PySide6.QtOpenGL",
        "PySide6.QtVirtualKeyboard",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
    ],
    noarchive=False,
    optimize=0,
)

# The PySide6 hook collects the whole Qt runtime. Drop Quick/QML/Pdf/OpenGL and
# translation/plugin assets the widget-only UI never touches.
QT_SKIP = (
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Pdf",
    "Qt6OpenGL",
    "Qt6VirtualKeyboard",
    "opengl32sw",
    "virtualkeyboard",
    "qmltooling",
    "scenegraph",
)
DATA_SKIP = ("\\translations\\", "\\imageformats\\", "\\qml\\")

a.binaries = TOC(
    [entry for entry in a.binaries if not any(token in entry[0] for token in QT_SKIP)]
)
a.datas = TOC(
    [
        entry
        for entry in a.datas
        if not any(token in entry[0].replace("/", "\\") for token in DATA_SKIP)
        and not any(token in entry[0] for token in QT_SKIP)
    ]
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WorldDataComparison",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WorldDataComparison",
)

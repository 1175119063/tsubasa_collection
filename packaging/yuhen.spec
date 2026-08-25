from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path(SPECPATH).parent
STATIC_DIR = PROJECT_ROOT / "backend" / "app" / "static"
MIGRATIONS_DIR = PROJECT_ROOT / "backend" / "app" / "migrations"

hiddenimports = [
    "app.api",
    "app.backup",
    "app.config",
    "app.database",
    "app.enums",
    "app.media_store",
    "app.models",
    "app.schemas",
    "app.services",
    "multipart",
    "pydantic_settings",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]
hiddenimports += collect_submodules("uvicorn")


a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "launcher.py")],
    pathex=[str(PROJECT_ROOT / "backend"), str(PROJECT_ROOT / "packaging")],
    binaries=[],
    datas=[
        (str(STATIC_DIR), "app/static"),
        (str(MIGRATIONS_DIR), "app/migrations"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="翼·时光记",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="翼·时光记",
)

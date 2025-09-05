# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import shutil
import sys

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Ensure yt_dlp resources are collected as well
try:
    ytdlp_ret = collect_all('yt_dlp')
    datas += ytdlp_ret[0]; binaries += ytdlp_ret[1]; hiddenimports += ytdlp_ret[2]
except Exception:
    pass

# Enforce bundling ffmpeg/ffprobe: fail the build if not found
missing_tools = []
for tool in ("ffmpeg", "ffprobe"):
    path = shutil.which(tool)
    if not path:
        missing_tools.append(tool)
    else:
        binaries.append((path, tool))

if missing_tools:
    sys.stderr.write(f"\nERROR: Missing required tools for bundling: {', '.join(missing_tools)}.\n"
                     f"Please install via Homebrew (e.g., 'brew install ffmpeg') and re-run.\n")
    raise SystemExit(2)


a = Analysis(
    ['/Users/valentinm2/Developer/Projects/YoutubeDownloader/main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='YouTubeDownloader',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='YouTubeDownloader',
)
app = BUNDLE(
    coll,
    name='YouTubeDownloader.app',
    icon=None,
    bundle_identifier=None,
)

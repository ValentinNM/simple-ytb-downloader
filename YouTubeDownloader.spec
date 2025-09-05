# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import shutil
import sys
from pathlib import Path

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

# Prefer vendored ffmpeg/ffprobe under vendor/ffmpeg/macos; fallback to PATH
# __file__ is not defined when executing specs via pyinstaller - use current working dir
root_dir = Path('.').resolve()
vend_ffmpeg = root_dir / 'vendor' / 'ffmpeg' / 'macos' / 'ffmpeg'
vend_ffprobe = root_dir / 'vendor' / 'ffmpeg' / 'macos' / 'ffprobe'

resolved = {}
for tool, vend in (('ffmpeg', vend_ffmpeg), ('ffprobe', vend_ffprobe)):
    if vend.exists():
        resolved[tool] = str(vend)
    else:
        path = shutil.which(tool)
        if path:
            resolved[tool] = path

missing = [t for t in ('ffmpeg', 'ffprobe') if t not in resolved]
if missing:
    sys.stderr.write(f"\nERROR: Missing required tools for bundling: {', '.join(missing)}.\n"
                     f"Provide vendor binaries under vendor/ffmpeg/macos/ or install via Homebrew, then re-run.\n")
    raise SystemExit(2)

# Place binaries next to the executable within the bundle
# Prefer packaging ffmpeg/ffprobe as datas under Resources/fftools
for tool in ('ffmpeg', 'ffprobe'):
    datas.append((resolved[tool], 'fftools'))


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

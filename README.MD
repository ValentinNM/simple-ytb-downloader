# YouTube Downloader GUI

A clean, minimal GUI for downloading YouTube videos using `yt-dlp` with drag & drop support and real-time progress tracking.
## Download

- Latest macOS build (DMG): https://github.com/ValentinNM/simple-ytb-downloader/releases/latest/download/YouTubeDownloader.dmg
- v1.0.0 (DMG): https://github.com/ValentinNM/simple-ytb-downloader/releases/download/v1.0.0/YouTubeDownloader.dmg


## Features

- **Simple Interface**: Drag & drop URLs or paste multiple links
- **High Quality Downloads**: Uses `yt-dlp` for best video+audio quality
- **Real-time Progress**: Speed, ETA (mm:ss), and batch progress indicators
- **Smart Naming**: Sanitized filenames with automatic uniqueness handling
- **Sequential Processing**: Downloads items one by one for UI responsiveness
- **Cancel Support**: Stop active downloads safely
- **Playlist Expansion**: Optional; when enabled, shows playlist item progress
- **Theme**: Auto/Light/Dark

## Prerequisites

### System Requirements
- **macOS** (Darwin)
- **Python 3.11** (managed via pyenv)
- **FFmpeg** - Required for video/audio merging
- **Tcl/Tk 8** - For GUI compatibility

### Install System Dependencies

```bash
# FFmpeg
brew install ffmpeg

# Tcl/Tk (prefer Homebrew build)
brew install tcl-tk || brew install tcl-tk@8

# Optional: ensure Tcl/Tk paths are visible during Python build
TCLTK_PREFIX=$(brew --prefix tcl-tk 2>/dev/null || brew --prefix tcl-tk@8)
export PATH="$TCLTK_PREFIX/bin:$PATH"
export LDFLAGS="-L$TCLTK_PREFIX/lib"
export CPPFLAGS="-I$TCLTK_PREFIX/include"
export PKG_CONFIG_PATH="$TCLTK_PREFIX/lib/pkgconfig"
```

### Python via pyenv (with Tk support)

```bash
# Build Python 3.11.9 against Homebrew Tcl/Tk
TCLTK_PREFIX=$(brew --prefix tcl-tk 2>/dev/null || brew --prefix tcl-tk@8)
env PYTHON_CONFIGURE_OPTS="--enable-framework \
  --with-tcltk-includes='-I$TCLTK_PREFIX/include' \
  --with-tcltk-libs='-L$TCLTK_PREFIX/lib -ltcl8.6 -ltk8.6'" \
  pyenv install 3.11.9

# Pin the repo to that Python version
pyenv local 3.11.9
```

### Create the Pipenv environment

```bash
# Create a project-scoped virtualenv and install deps from Pipfile
# PIPENV_IGNORE_VIRTUALENVS=1 forces Pipenv to create/use its own venv
# even if another venv is currently active.
PIPENV_IGNORE_VIRTUALENVS=1 pipenv install
```

## Running

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run python main.py
```

## Usage

- **Add URLs**: Drag & drop YouTube URL(s) into the text box, or paste them.
- **Pick folder**: Click "Choose Save Folder".
- **Download**: Click "Download". Items run sequentially. The status shows percent, speed, and ETA. A batch label shows "Item X of N".
- **Cancel**: Click "Cancel" to safely stop the current download.

Defaults:

- Highest quality video+audio via `yt-dlp`.
- Container defaults to `mkv` for broad codec compatibility.
- When `mp4` is selected, the app (by default) **prefers AVC/H.264 + AAC** for better compatibility/quality. You can toggle this via "Prefer AVC for MP4".
- Audio-only `mp3` is supported (extracts best audio via FFmpeg).

## Packaging (build the macOS app)

We provide a `YouTubeDownloader.spec` tuned for TkinterDnD2 and `yt_dlp`. It also attempts to bundle `ffmpeg` and `ffprobe` automatically if they are discoverable on your PATH at build time. You can also run one-shot commands.

### Clean previous artifacts

```bash
rm -rf build dist
```

### Build with PyInstaller (one-file + .app bundle)

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run pyinstaller --noconfirm --windowed --onefile \
  --name "YouTubeDownloader" \
  --collect-all tkinterdnd2 --collect-all yt_dlp \
  main.py
```

Or using the provided spec (recommended and enforces bundling ffmpeg/ffprobe):

```bash
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run pyinstaller YouTubeDownloader.spec
```

Artifacts appear under `dist/`:
- `dist/YouTubeDownloader` (single binary)
- `dist/YouTubeDownloader.app` (macOS bundle)

### FFmpeg bundling (required by spec)

The provided spec will FAIL the build if `ffmpeg`/`ffprobe` are not on your PATH. Install them first:

```bash
brew install ffmpeg
```

```bash
FFMPEG=$(which ffmpeg)
FFPROBE=$(which ffprobe)
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run pyinstaller --noconfirm --windowed --onefile \
  --name "YouTubeDownloader" \
  --add-binary "$FFMPEG:ffmpeg" \
  --add-binary "$FFPROBE:ffprobe" \
  main.py
```

## Release: DMG/PKG for GitHub

To distribute on GitHub Releases, create a DMG/PKG and upload.

Example (using `create-dmg`, optional):

```bash
brew install create-dmg
create-dmg --volname "YouTubeDownloader" --window-size 500 300 \
  --icon "YouTubeDownloader.app" 125 150 \
  --app-drop-link 375 150 \
  dist/YouTubeDownloader.dmg dist/YouTubeDownloader.app
```

Then attach the DMG to a GitHub Release. In this README, add a link like:

- Latest macOS build (DMG): https://github.com/ValentinNM/simple-ytb-downloader/releases/latest/download/YouTubeDownloader.dmg

Tip: If you don’t have `create-dmg`, you can also distribute the `.app` or the single-file binary directly. The DMG is preferred for a smoother UX.

## CLI/Log Notes and Common Warnings

- **HTTP Error 403: Forbidden / Unable to download format 616. Skipping...**: YouTube sometimes blocks specific format IDs. `yt-dlp` skips and falls back. Not fatal.
- **Testing format 616**: `yt-dlp` probes candidate formats before selecting the best available combination.
- **...has already been downloaded**: The output file already exists; `yt-dlp` skips re-downloading. Remove/rename the file or change the folder to force a new download.
- **Playlist URLs**: With "Expand playlist" enabled, items are planned and displayed with per-item labels.

## What does PIPENV_IGNORE_VIRTUALENVS=1 do?

When set, Pipenv ignores any currently active virtual environment and creates/uses the project’s own environment (under `~/.local/share/virtualenvs`), tied to the interpreter selected by `pyenv local 3.11.9`. This ensures a clean, reproducible venv for this project regardless of your shell state.

## Troubleshooting

- **Tkinter/Tk errors on macOS**: Rebuild Python via `pyenv` against Homebrew `tcl-tk` as shown above, then `pyenv local 3.11.9` and reinstall with `pipenv install`.
- **FFmpeg not found**: Install with `brew install ffmpeg` and ensure it is on your PATH.
- **Persistent 403s across all formats**: Network or regional restrictions may apply. Retrying later often helps; advanced users can provide cookies to `yt-dlp`.

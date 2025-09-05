DEFAULT_CONTAINER = "mkv"  # or "mp4"
DEFAULT_RESOLUTION_LABEL = "Auto (Best)"
FFMPEG_CHECK_TIMEOUT_SEC = 5
PROGRESS_POLL_MS = 100
SPEED_SMOOTH_WINDOW_SEC = 5.0

# Settings file stored in the user's home directory
SETTINGS_FILE_NAME = ".youtube_downloader_settings.json"

# Advanced option: when enabled, yt-dlp will fetch one fragment at a time
# to provide a steadier progress signal at the cost of peak speed.
DEFAULT_LIMIT_FRAGMENT_CONCURRENCY = False



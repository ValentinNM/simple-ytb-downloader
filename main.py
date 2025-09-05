#!/usr/bin/env python3

from app.ui import DownloaderApp
from app.ui_root import create_root


def main():
    root = create_root()
    _app = DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()




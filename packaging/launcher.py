from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


ROOT = bundle_root()
BACKEND_DIR = ROOT / "backend"
if BACKEND_DIR.exists():
    sys.path.insert(0, str(BACKEND_DIR))

if getattr(sys, "frozen", False):
    os.environ["YUHEN_DATA_DIR"] = str(ROOT / "data")
else:
    os.environ.setdefault("YUHEN_DATA_DIR", str(ROOT / "data"))


def open_browser(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动翼·时光记本地服务")
    parser.add_argument("--no-browser", action="store_true", help="启动时不打开浏览器")
    parser.add_argument("--port", type=int, default=8000, help="本地服务端口")
    return parser.parse_args()


def main() -> None:
    import uvicorn
    from app.main import app

    args = parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("端口必须位于 1 到 65535 之间。")
    url = f"http://127.0.0.1:{args.port}"
    print("翼·时光记正在启动……")
    print(f"浏览器地址：{url}")
    print("保持此窗口运行；按 Ctrl+C 可停止软件。")
    if not args.no_browser:
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="info",
        access_log=False,
    )
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()

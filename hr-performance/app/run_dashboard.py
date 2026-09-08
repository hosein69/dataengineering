# -*- coding: utf-8 -*-
"""راه‌انداز داشبورد — پورت آزاد را خودش پیدا می‌کند."""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def free_port(start: int = 8601, tries: int = 40) -> int:
    for p in range(start, start + tries):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    args = ap.parse_args()
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print("Streamlit نصب نیست:\n    pip install -r requirements.txt")
        return 1
    port = args.port or free_port()
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONUTF8="1")
    print(f"داشبورد: http://localhost:{port}")
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run",
         os.path.join(HERE, "dashboard.py"),
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false"], cwd=ROOT, env=env)


if __name__ == "__main__":
    sys.exit(main())

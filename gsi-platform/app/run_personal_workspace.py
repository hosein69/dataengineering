from __future__ import annotations
import subprocess, sys
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).with_name("personal_workspace.py")
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(target), *sys.argv[1:]]))

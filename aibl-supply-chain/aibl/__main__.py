# -*- coding: utf-8 -*-
"""نقطه ورود پیش‌فرض:  python -m aibl  [doctor|rules|run]"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "doctor":
        from .doctor import main as run
        return run()
    if cmd in ("diagnose", "joins"):
        from .diagnose import main as run
        return run()
    if cmd in ("rules", "validate"):
        from .rulebook.validate import main as run
        return run()
    if cmd in ("email", "mail", "daily-email"):
        from .integrations.daily_email import main as run
        return run(sys.argv[2:])
    if cmd in ("analyze", "analysis", "tahlil"):
        from .analytics.cli import main as run
        return run(sys.argv[2:])
    if cmd in ("studio", "dashboard"):
        import os, subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = os.path.join(root, "app", "studio.py")
        return subprocess.call([sys.executable, "-m", "streamlit", "run", app], cwd=root)
    if cmd == "run":
        from .doctor import main as doctor
        if doctor() != 0:
            print("\n⛔ اجرا متوقف شد چون محیط خطا دارد. موارد بالا را رفع کنید.")
            return 1
        # قفل فقط در نقطه ورود CLI گرفته می‌شود، نه داخل Pipeline.run —
        # تا فراخوانی کتابخانه‌ای و تست‌ها آزاد بمانند.
        from .config.settings import SETTINGS
        from .pipeline import main as run
        from .runlock import RunLock, RunLocked
        try:
            with RunLock(SETTINGS.OUTPUT_DIR):
                run()
        except RunLocked as ex:
            print(f"\n⛔ {ex}")
            return 2
        return 0
    print(f"دستور ناشناخته «{cmd}». گزینه‌ها: doctor | analyze | diagnose | rules | email | studio | run")
    return 2


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""نقطه ورود پیش‌فرض GSI."""
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
    if cmd in ("studio", "dashboard"):
        import os, subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = os.path.join(root, "app", "studio.py")
        return subprocess.call([sys.executable, "-m", "streamlit", "run", app, "--server.address=127.0.0.1"], cwd=root)
    if cmd in ("personal", "my-workspace"):
        import os, subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = os.path.join(root, "app", "personal_workspace.py")
        return subprocess.call([sys.executable, "-m", "streamlit", "run", app, "--server.address=127.0.0.1"], cwd=root)
    if cmd in ("publish-personal", "personal-publish"):
        from .pipeline import Pipeline
        from .personalization.publisher import publish_employee_snapshots
        import argparse
        ap = argparse.ArgumentParser(description="Publish scoped snapshots to shared folders")
        ap.add_argument("--employees", help="Comma-separated complete employee roster for this publication")
        ns = ap.parse_args(sys.argv[2:])
        employees = ns.employees.split(",") if ns.employees else None
        pipe = Pipeline()
        result = pipe.run(build_report=False)
        out = publish_employee_snapshots(result.main, employee_codes=employees, source_run_id="pipeline", ref_date=pipe.today.isoformat())
        print(f"Personal snapshots: users={out['users']} rows={out['rows']} missing={len(out['missing'])}")
        return 0
    if cmd in ("personal-open", "live-personal"):
        from .personalization.launcher import render_and_open
        out = render_and_open()
        print(out)
        return 0
    if cmd in ("personal-key", "derive-user-key"):
        import os
        from .personalization.store import derive_user_key_text, ProfileConfigurationError
        from .personalization.identity import resolve_employee_code
        emp = resolve_employee_code(sys.argv[2] if len(sys.argv) > 2 else None)
        master = os.environ.get("GSI_PROFILE_MASTER_KEY", "").strip()
        if not master:
            key_file = os.environ.get("GSI_PROFILE_KEY_FILE", "").strip()
            if key_file:
                from pathlib import Path
                from .personalization.store import _read_key_text
                master = _read_key_text(Path(key_file))
        if not master:
            raise ProfileConfigurationError("Master Key مرکزی برای استخراج User Key تنظیم نشده است.")
        print(derive_user_key_text(master, emp))
        return 0
    if cmd in ("personal-html", "my-html"):
        import argparse
        from pathlib import Path
        from .personalization.personal_html import build_personal_html
        from .personalization.identity import resolve_employee_code
        ap = argparse.ArgumentParser(description="Render personal HTML from encrypted shared-folder state")
        ap.add_argument("--employee", default=None)
        ap.add_argument("--output", default="GSI_Personal.html")
        ns = ap.parse_args(sys.argv[2:])
        emp = resolve_employee_code(ns.employee)
        out = Path(ns.output)
        from .personalization.launcher import render_live
        render_live(emp, output=out)
        print(out.resolve())
        return 0
    if cmd == "run":
        from .doctor import main as doctor
        if doctor() != 0:
            print("\n⛔ اجرا متوقف شد چون محیط خطا دارد. موارد بالا را رفع کنید.")
            return 1
        from .pipeline import main as run
        run()
        return 0
    print(f"دستور ناشناخته «{cmd}». گزینه‌ها: doctor | diagnose | rules | email | studio | personal | publish-personal | personal-html | personal-key | personal-open | run")
    return 2


if __name__ == "__main__":
    sys.exit(main())

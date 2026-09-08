# AIBL V26.2.1 — Studio Launcher Fix

- Fixed `app/run_platform.py` to launch the actual modular Studio entrypoint: `app/studio.py`.
- Added regression coverage so the launcher cannot silently point to the removed `platform.py`.
- No changes to Pipeline, criticality, Excel, HTML, or email business logic.
- Release version: 26.2.1.

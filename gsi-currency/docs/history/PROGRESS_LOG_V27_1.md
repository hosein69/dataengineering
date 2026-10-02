# GSI V27.1 — Progress Log

Status: **Completed / Release validated**
Date: 2026-09-18
Version: `27.1.0`

## Completed

1. File-share-only personal persistence — no HTTP/IP data transport.
2. AES-256-GCM encrypted `profile.gsi` and `current.gsi`.
3. SQLite payload stays in memory; no plaintext DB is written to Share.
4. Per-employee folder keyed by canonical `KEY_EMP`.
5. Master Key central-only; per-user derived key supported on clients.
6. Central Publisher scopes data by `KEY_EMP`.
7. Streamlit personal workspace reads only personal Shared Store for data.
8. Outlook-safe personal HTML + `gsi://personal` local live-view path.
9. Local installer persists identity/share config/key outside Shared data folder.
10. Separate ACL model: `state` writable, `snapshot` read-only for user.
11. Regression: **749 passed / 0 failed across 25 suites**.
12. RuleBook: **0 structural errors**; Doctor: **0 errors / 10 warnings**.

## Release boundary

Controlled Pilot/UAT ready. Production verification requires real SMB ACL, real Windows client, actual Outlook Group Policy behavior for the custom URI scheme, and organization snapshots.

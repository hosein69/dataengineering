# GSI V27.1.0 — Final Package Contents

## هسته محصول

- GSI end-to-end sourcing intelligence pipeline با 17 stage.
- RuleBook با 13 pack و Fail-Closed برای قواعد نیازمند تطبیق.
- Allocation Queue / Case Action / Money Flow / Supply Position / Commitment tracking.
- Design System و Audience-aware views برای expert / manager / executive / analyst.

## Personal Shared Store — No Reset

- `gsi/personalization/store.py` — SQLite in-memory + AES-256-GCM + atomic file replace + SMB-safe lock.
- `gsi/personalization/identity.py` — resolve کد پرسنلی بدون IP/HTTP.
- `gsi/personalization/publisher.py` — ساخت `snapshot/current.gsi` فقط از ردیف‌های همان `KEY_EMP`.
- `gsi/personalization/service.py` — API مشترک Profile + Snapshot برای Dashboard/Email.
- `gsi/personalization/personal_html.py` — HTML شخصی از Shared Store.
- `gsi/personalization/launcher.py` — Local Live View؛ Shared Folder → decrypt locally → local HTML cache.
- `app/personal_workspace.py` — Streamlit شخصی که برای Data Access فقط Shared Store را می‌خواند.
- `tools/windows/install_gsi_personal_protocol.py` — نصب HKCU برای `gsi://personal`، Identity/Config/User Key و launcher محلی.
- `tools/windows/apply_gsi_user_acl.ps1` — ACL پیشنهادی `state=Modify` و `snapshot=Read` برای کاربر.

## ساختار داده شبکه

```text
GSI_PROFILE_ROOT/
  <EMP_CODE>/
    state/profile.gsi
    snapshot/current.gsi
```

- `profile.gsi`: Preference / Saved View / UI State پایدار.
- `current.gsi`: Snapshot تازه عملیاتی؛ writer سیستم مرکزی، reader کاربر.
- هر دو فایل encrypted-at-rest هستند؛ SQLite plaintext روی Share نوشته نمی‌شود.
- Master Key فقط روی سیستم مرکزی؛ Client ترجیحاً فقط User Key خودش را دارد.

## Email / Dashboard

- HTML ایمیل Snapshot شخصی‌شده می‌سازد.
- لینک `gsi://personal` آخرین `profile.gsi + current.gsi` را دوباره از Shared Folder می‌خواند؛ هیچ HTTP/IP data transport لازم نیست.
- Streamlit شخصی همان Store را می‌خواند و Preferences را بین Sessionها حفظ می‌کند.
- Outlook Body برای JavaScript/File-System Fetch قابل اتکا فرض نشده است؛ Live View با Helper محلی انجام می‌شود.

## Validation

- Version: **27.1.0**
- Test suites: **25**
- Tests: **749 passed / 0 failed**
- Pipeline stages: **17**
- Rule packs: **13**
- RuleBook structural errors: **0**
- Rules needing official verification: **23**
- Manifest: **123 tracked files**
- Doctor: **0 errors / 10 warnings**
- Warnings are optional dependency / inaccessible internal shares / expiring or unverified regulatory overlays, not silent fallbacks.

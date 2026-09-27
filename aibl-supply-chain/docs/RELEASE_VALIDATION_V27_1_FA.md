# Release Validation — GSI V27.1.0

تاریخ اعتبارسنجی: 2026-09-18

## نتیجه

- نسخه: **27.1.0**
- مجموعه تست: **25**
- تست‌ها: **749 موفق / 0 ناموفق**
- Pipeline: **17 stage**
- RuleBook: **13 pack**
- خطای ساختاری RuleBook: **0**
- قواعد نیازمند تطبیق رسمی: **23**
- Manifest: **123 فایل tracked**
- Doctor: **0 خطا / 10 هشدار**

## تست‌ها

| Suite | Passed | Failed |
|---|---:|---:|
| Algorithm / business | 61 | 0 |
| Rules & resistance sources | 63 | 0 |
| Criticality | 34 | 0 |
| Architecture / contracts / eventlog | 42 | 0 |
| Report contracts | 14 | 0 |
| Dashboard / outputs | 79 | 0 |
| Import hygiene / deployment | 19 | 0 |
| Documentation claims | 8 | 0 |
| Email report | 11 | 0 |
| Studio | 5 | 0 |
| Report builder / grain | 35 | 0 |
| Ownership / supply views | 55 | 0 |
| System health | 49 | 0 |
| Oracle multisheet | 1 | 0 |
| Studio V26.12 compatibility | 2 | 0 |
| HTML Process compatibility | 1 | 0 |
| FX traceability | 5 | 0 |
| Money flow | 13 | 0 |
| Legacy knowledge | 16 | 0 |
| Allocation / case action / inventory | 15 | 0 |
| Runtime / grain / Outlook COM | 11 | 0 |
| Design System | 93 | 0 |
| Engine hardening | 47 | 0 |
| Audience / voice | 46 | 0 |
| Personal Shared Store V27.1 | 24 | 0 |
| **Total** | **749** | **0** |

> Runner یک‌تکه در محدودیت زمان محیط متوقف شد؛ مجموعه‌ها به‌صورت مستقل با همان entry pointها اجرا شدند. هیچ Suite ناموفق باقی نماند.

## Personal Shared Store checks

- Persistence بین instance/session حفظ می‌شود.
- فایل encrypted حاوی plaintext حساس یا `SQLite format 3` نیست.
- AES-GCM دستکاری ciphertext را تشخیص می‌دهد.
- Wrong key به plaintext fallback نمی‌کند.
- Per-user key کاربر دیگر فایل را باز نمی‌کند.
- Identity از IP/hostname resolve نمی‌شود.
- `personal_config.json + identity.json + profile.key` می‌توانند پس از Restart مسیر/هویت/کلید کاربر را بازیابی کنند.
- Central Publisher بدون Master Key حتی با وجود User Key اجرا نمی‌شود.
- Publisher هر `KEY_EMP` را فقط در `snapshot/current.gsi` خودش منتشر می‌کند.
- Personal HTML/Live View از Shared Store استفاده می‌کند و HTTP fetch برای Data Access ندارد.
- Windows protocol installer از launcher محلی و `--user-key-file` پشتیبانی می‌کند.

## RuleBook

`python -m gsi.rulebook.validate` با return code صفر اجرا شد. 23 Rule هنوز `needs_verification` هستند؛ بنابراین سیستم اجازه ندارد آن‌ها را به‌عنوان الزام قطعی جاری silently enforce کند.

دو overlay اضطراری در تاریخ اعتبارسنجی فقط 4 روز تا expiry داشتند و باید پیش از 2026-09-22 تمدید/جایگزین یا غیرفعال شوند:

- `fx_governance.regulatory_snapshot.emergency_deadline_overlay_1405_05_14`
- `customs.emergency_sata_waiver_1405`

## Doctor

`python -m gsi.doctor`:

- **0 errors**
- **10 warnings**

هشدارها شامل `jdatetime` اختیاری، 23 Rule نیازمند تطبیق، دو overlay نزدیک expiry و شش Share داخلی غیرقابل دسترس از این محیط هستند. دسترسی واقعی Shareها باید در شبکه سازمان UAT شود.

## Production boundary

این Release از نظر کد، تست، encryption contract و local-file architecture آماده Controlled Pilot/UAT است. برچسب **Production Verified** فقط بعد از آزمون روی Share واقعی، ACL واقعی Windows/SMB، Outlook policy برای `gsi://` و Snapshot واقعی کاربران قابل اعلام است.

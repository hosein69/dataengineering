# AIBL / GSI V26.19 — Legacy Knowledge Transfer

**Version:** `26.19.0`  
**Date:** 2026-09-17

## خلاصه

V26.19 دانش فایل‌های قدیمی رفع تعهد را از «فرمول و فایل پراکنده» به یک مدل versioned و قابل ممیزی تبدیل می‌کند. Money Flow Control Tower V26.18 حفظ شده و لایه جدید Root Cause / Evidence / Provenance روی آن سوار شده است.

## مهم‌ترین تغییرات

- Rule pack جدید `legacy_knowledge.yaml` با 22 Knowledge Item.
- شش کلاس دانش: historical rule، operational practice، data mapping، root cause، evidence requirement و technical antipattern.
- Stage جدید `legacy_knowledge_transfer` با order=57.
- `Payment without BL` → `UNALLOCATED_PAYMENT_CANDIDATE`؛ بدون BL مصنوعی.
- نرخ ثابت تاریخی از P&L واقعی جدا شد.
- Root-cause candidateهای تجربه قدیمی با Evidence Requirement نمایش داده می‌شوند.
- کاتالوگ Provenance و Knowledge Signal داخل Process View و شیت FX گزارش می‌آید.
- Legacy Rule Guard: auto-enforcement برای دانش قدیمی همیشه fail-closed است.
- دو تست نسل قدیمی که در اجرای مستقیم import path نداشتند نیز اصلاح شدند.

## صحت‌سنجی Release

- 19 مجموعه تست ثبت‌شده.
- 502 تست موفق، 0 تست ناموفق (اجرا در گروه‌های زمانی به علت سقف زمانی محیط ابزار).
- RuleBook: 0 خطای ساختاری؛ 19 Rule جاری همچنان `needs_verification` و جدا از Legacy Pack.
- نسخه واحد: `26.19.0`.

## فایل‌های اصلی جدید

- `aibl/knowledge/legacy.py`
- `aibl/rules/legacy_knowledge.yaml`
- `aibl/stages/s57_legacy_knowledge.py`
- `tests/test_legacy_knowledge_v26_19.py`
- `docs/LEGACY_KNOWLEDGE_TRANSFER_V26_19_FA.md`

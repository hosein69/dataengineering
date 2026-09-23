# rc1 — شواهد بازتولیدپذیر OPUS_FINAL_REVIEW

راستی‌آزمایی مستقل `GSI_29_7_7_RC1_OPUS_REVIEW.zip` در برابر `GSI_V29_7_6` و `OPUS_REVIEW.md`.
هیچ فایلی از RC اصلی تغییر نکرد؛ اصلاح‌ها به‌صورت `opus_rc1_fixes.patch` تحویل شده‌اند.

## اجرا

```bash
python3.12 -m venv venv
./venv/bin/pip install "pandas==2.2.3" "numpy==2.3.5" "openpyxl==3.1.5" \
                       "pytest==9.1.1" "streamlit==1.49.1" PyYAML cryptography plotly matplotlib

unzip GSI_29_7_7_RC1_OPUS_REVIEW.zip -d /tmp/rc
export PKG=/tmp/rc/gsi_2977_rc1
export GSI_DWH_PATH=/tmp/probe.sqlite          # برای هر probe یک فایل تازه

./venv/bin/python rc_isolation.py 2>/dev/null | grep -v "| WARNING\|| INFO\|| ERROR"
```

برای مقایسه «قبل/بعد»، همان probe را یک‌بار با `PKG` روی بسته 29.7.6 و یک‌بار روی RC اجرا کنید.
probeهای دور اول در `../probes/` هستند و بدون تغییر منطق روی RC هم اجرا می‌شوند.

## نگاشت probe به یافته

| فایل | چه چیزی را اندازه می‌گیرد | یافته‌ها |
|---|---|---|
| `rc_isolation.py` | ایزولاسیون انتشار از **مسیر واقعی `read_db`**، تغییرناپذیری snapshot، بقای داده منتشرشده پس از اجرای مسدود، انتخاب «آخرین PR» در چت‌بات، و حفره `nullable_key` در گیت | F001, F002, F018, F025 |
| `rc_merge.py` | کلید مرکب خالی / `NaN` / برخورد delimiter / کلید جزئی، حذف many-to-one، و دسترس‌پذیری `RowExplosionError` | F019, F020, N04 |
| `rc_residual.py` | سه یافته تازه: ثبت‌نشدن `SWIFT_SENT` در `STAGES`، تبدیل NaN به صفر در `s20_derive`، و بی‌تولیدکننده‌بودن `FIN_RECEIPT_DATE` | **RES-1, RES-2, RES-3** |
| `rc_fixverify.py` | اثبات اصلاح هر سه مورد بالا پس از اعمال patch | RES-1..3 |
| `rc_gatecheck.py` | اجرای انتها‌به‌انتها: نتیجه گیت و نوشته‌شدن خروجی رسمی در `output/runs/<run_id>/` | F012 |
| `rc_concurrency.py` | تلاش برای بازتولید RC03 با ۴ پروسه نویسنده همزمان روی یک DWH مشترک | RC03 (نتیجه **منفی**) |
| `../probes/p_dwh.py` | رابطه‌های `dwh_relation`، `evidence_count` در ingest مجدد، cross-product نمای هاب | F006 (رد), N02, N09 |
| `../probes/p_sap.py` | گرین SAP: PR item با چند PO item، تعارض PR هدر با `po.Purchase Requisition`، انباشت workflow | F017, F018, N06 |
| `../probes/p_status.py` | طبقه‌بندهای وضعیت فارسی، جمع چندارزی، تعهد تکراری، هویت پرونده فرایندی | F004, F005, F007, F008, F009, N03, N08 |
| `../probes/p_reach.py` | ممیزی مکانیکی producer/consumer روی `DERIVED` | F021, N05 |
| `../probes/p_drift2.py` | آیا تغییر نام هدر منبع دیده می‌شود | N01 |

## فایل‌های دیگر

- `opus_rc1_fixes.patch` — اصلاح RES-1/2/3 در برابر RC1 دست‌نخورده (۴ فایل). اعمال: `git apply` یا `patch -p1` از ریشه پکیج.
- `rcfix_full_suite.log` — لاگ کامل `python run_all_tests.py` **پس از** اعمال patch: `1048 موفق | 0 ناموفق`، exit 0.

## هشدار تفسیر

ورودی‌ها synthetic‌اند. این probeها وجود یا رفع نقص روی ورودی مشخص را اثبات می‌کنند، نه نرخ وقوع در داده تولیدی.
یک اجرای سبز synthetic معادل امضای مالی یا عملیاتی نیست.

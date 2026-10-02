# A/B بین دو نسخه GSI

هر دو نسخه روی **ورودی یکسان** اجرا می‌شوند و همه خروجی‌ها سلول‌به‌سلول مقایسه می‌شوند:
همه فریم‌ها (`df`, `main`, `to_resolve`, `excluded`, `audit`, همه extras)، شمارش‌ها، همه
شیت‌های Excel و خروجی HTML. هر تفاوتی که در فهرست «افزوده‌های مورد انتظار» نسخه جدید
نیست، یا باگ است یا تغییر رفتاری که باید توضیح داده شود.

```bash
# داده: نمونه واقعی‌سربرگ (0) و ۴۰ برابر (برای آستانه‌های آماری)
python tools/ab/make_scaled.py /tmp/ab/data_synth 0
python tools/ab/make_scaled.py /tmp/ab/data_scaled 40

# دو بازو (بسته‌های استخراج‌شده از ZIP)، هر کدام ۴ اجرای پشت‌سرهم برای ساختن سابقه
python tools/ab/ab_run.py /tmp/ab/A /tmp/ab/data_scaled/env.sh /tmp/ab/out/A_scaled 4
python tools/ab/ab_run.py /tmp/ab/B /tmp/ab/data_scaled/env.sh /tmp/ab/out/B_scaled 4
GSI_AB_UNPICKLE_PKG=/tmp/ab/B python tools/ab/ab_compare.py /tmp/ab/out scaled 4
GSI_AB_UNPICKLE_PKG=/tmp/ab/B python tools/ab/xls_align.py /tmp/ab/out scaled 3

# بازوی «درمان»: ناهنجاری تزریقی، تأیید ترمیم قبل از اجرای ۴، حذف نیمی از یک سورس قبل از اجرای ۵
python tools/ab/ab_treat.py /tmp/ab/A /tmp/ab/data_treat /tmp/ab/out/A_treat
python tools/ab/ab_treat.py /tmp/ab/B /tmp/ab/data_treat /tmp/ab/out/B_treat
```

نتیجه اولین استفاده (29.14.0 ↔ 29.15.0) و شش باگی که پیدا کرد: `docs/AB_TEST_29_15_1_FA.md`.

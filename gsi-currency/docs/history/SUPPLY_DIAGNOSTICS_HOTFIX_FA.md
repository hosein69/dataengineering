# Supply Diagnostics / Performance Hotfix — 2026-09-20

این اصلاح منطق کسب‌وکار Supply Position یا Criticality را تغییر نمی‌دهد.

- `s20_derive.py`: ساخت ستون‌های مشتق/بولی به‌صورت batch انجام می‌شود تا DataFrame fragmentation و PerformanceWarningهای تکراری حذف شوند.
- `s38_supply_position.py`: پوشش هر مؤلفه موجودی و تعداد KEY_MATERIAL / DAILY_NEED معتبر در لاگ ثبت می‌شود.
- `diagnose.py`: سه bucket کارشناسی موجودی و KEY_MATERIAL دو سورس Oracle/Commercial Expert به گزارش ستون‌های حیاتی اضافه شدند.
- Missing همچنان Zero محسوب نمی‌شود.

تست‌ها:
- `tests/test_supply_views.py`: 6/6 پاس.
- smoke test Missing/Zero/Complete: پاس.
- manifest.verify(): 0 اختلاف.
- یک تست قدیمی integration به share شبکه IKCO وابسته است و در محیط ساخت قابل اجرا نیست؛ این محدودیت به تغییر حاضر مربوط نیست.

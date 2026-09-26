# گیت نهایی بازبینی GSI 29.8.2 RC4-OPT2-H1

## نتیجه
این بسته از نظر regression قابل اجرای این محیط، **Review-Verified** است؛ اما همچنان **Production Certified نیست**. هیچ منطق production در این مرحله تغییر نکرده است. اصلاحات این مرحله فقط در زیرساخت تست و assertion منسوخ Excel بوده‌اند.

## مبنای ورودی
- بسته ورودی: `GSI_29_8_2_RC4_OPT2_H1_REVIEW.zip`
- SHA-256 بسته ورودی: `b9c9b12ec43bf036072f2704f35ede09b26cc254b7cf90137c7337e0b23ad97a`
- نسخه نرم‌افزار: `29.8.2`
- کانال داخلی: `rc4-opt2-h1-review`
- `production_certified=false` بدون تغییر باقی مانده است.

## Regression فعلی
Pytest canonical پس از افزودن `pytest.ini` دقیقاً **531 تست** را از `tests/` جمع‌آوری می‌کند. سه تست UI که مستقیم `streamlit.testing.v1.AppTest` را import می‌کنند در این محیط به دلیل نبود dependency `streamlit>=1.49` قابل اجرا نیستند. تلاش برای نصب dependency نیز به علت نبود دسترسی شبکه ممکن نشد.

نتیجه تست‌های قابل اجرا:
- Shard 1، بخش غیر-legacy: **134 passed / 3 deselected**
- Architecture legacy: **6 passed**
- Contracts legacy: **4 passed**
- Criticality legacy: **6 passed**
- Dashboard legacy: **8 passed**
- Shard 2: **82 passed**
- Shard 3A: **143 passed**
- Shard 3B: **50 passed**
- Shard 4A: **42 passed**
- Shard 4B: **53 passed**
- جمع: **528 passed / 0 functional failure / 3 environment-blocked UI tests**

هر سه تست مسدودشده فقط با خطای `ModuleNotFoundError: No module named 'streamlit'` متوقف می‌شوند و evidence آن در `review/h1_final/ui_dependency_blocked.log` ثبت شده است.

## H1 مالی و Authority
فایل `tests/test_fx_equivalent_authority_v29_8_2.py` در regression نهایی قرار دارد و هر **15 تست** آن پاس است. در نتیجه guardهای H1 زیر حفظ شده‌اند:
- نرخ خرید فقط با هویت `REG + Currency` همان پرونده مجاز است.
- fallback تخصیص فقط با `REG + NTSW_REQ_CURRENCY` همان پرونده مجاز است.
- نرخ پرونده یا ارز دیگر انتقال نمی‌یابد.
- REG متعارض از مخرج coverage حذف نمی‌شود و مبلغ متعارض وارد جمع قطعی نمی‌گردد.
- fan-out در معادل‌های تعهد/خرید به جمع قطعی تبدیل نمی‌شود.

## اصلاح تست legacy Excel
تست قبلی وجود هر فرمول در شیت «رفع تعهد ارزی» را با عنوان SUBTOTAL الزام می‌کرد. این assertion با قرارداد مالی فعلی ناسازگار بود، زیرا `SUBTOTAL(109)` روی ردیف‌های BL×Material می‌تواند fan-out ایجاد کند و ارزهای مختلف را بدون واحد جمع بزند. تست اکنون به‌جای مطالبهٔ آن رفتار، وجود نمایش `جمع Native قابل اتکا (REG/ارز)` و نبود `SUBTOTAL(109)` ناامن را کنترل می‌کند. production code برای عبور از تست تغییر نکرده است.

## اصلاح ایزولیشن تست
سه نشت state در suite legacy بسته شد:
1. discovery به `tests/` محدود شد تا کپی تاریخی `review/roadmap/uploaded_rc2/tests` دوباره collect نشود.
2. `logging.disable(...)` بعد از تست/factory به وضعیت قبلی restore می‌شود.
3. ماژول‌های legacy که synthetic source را در import-time می‌سازند، در هر تست به snapshot خود bind می‌شوند و registry/Settings پس از تست restore می‌گردد. fixture `res` نیز function-scoped شد تا قبل از ایزولیشن اجرا نشود.

این تغییرها test-only هستند و business/source authority/pipeline production را تغییر نمی‌دهند.

## Integrity
پیش از این تغییرات test-only، `PACKAGE_SHA256.json` برای **689/689** فایل کنترل‌شده بدون mismatch و بدون missing تأیید شد. mismatchهای بعدی فقط دو فایل تستیِ عمداً ویرایش‌شده بودند. manifest بستهٔ verified پس از افزودن evidenceها مجدداً ساخته و کنترل می‌شود.

## Release Gate
- Integrity ساختاری: **PASS**
- H1 FX authority/grain/coverage: **PASS**
- Regression قابل اجرا در محیط فعلی: **PASS (528/528)**
- UI AppTest: **BLOCKED BY ENVIRONMENT (3 tests; Streamlit absent)**
- Reconciliation روی snapshot واقعی همه منابع: **NOT VERIFIED**
- Output parity روی snapshot واقعی سازمان: **NOT VERIFIED**
- Idempotency روی snapshot واقعی سازمان: **NOT VERIFIED**
- Performance روی حجم واقعی سازمان: **NOT VERIFIED**
- Findings باز مانند F023/F031: **OPEN طبق KNOWN_LIMITATIONS.md**

بنابراین این artifact برای ادامهٔ review و اجرای gate روی محیط سازمانی مناسب است، ولی امضای انتشار عملیاتی فقط پس از اجرای سه تست UI در محیط کامل و reconciliation/performance روی snapshot واقعی قابل دفاع است.

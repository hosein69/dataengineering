# Validation — GSI 29.8.1 RC4-OPT1

## وضعیت

**Release candidate hardening؛ نه production certification.**

## تست‌های مستقیم اصلاحات

- `tests/test_rc4_performance_hardening.py`: 3 تست — archive reuse، `keep_sheets=False`، round-trip دقیق frame chunking.
- `tests/test_rc4_financial_accuracy_hardening.py`: 8 تست — REG fan-out، multi-currency، unknown balance، Excel total، scorecard، history، Stage KPI و Studio KPI.
- مجموعه مستقیم performance/warehouse/Streamlit-static/output/process قبل از financial hardening: 74 تست پاس.
- مجموعه ترکیبی financial/performance/legacy پس از اصلاح: 23 تست پاس.
- `tests/test_rc4_financial_accuracy_hardening.py + tests/test_dashboard.py`: 16 تست پاس و warning مربوط به `Font.copy` نیز رفع شد.

## محدودیت محیط تست

- پکیج `streamlit` در محیط ممیزی نصب نبود. دو تست `streamlit.testing.v1.AppTest` در `test_fullstack_v29_6_10.py` و یک تست مشابه در `test_cashflow_v29_7.py` به همین علت قابل اجرا نبودند؛ این failure وابستگی محیط است، نه assertion کد.
- اجرای کل `pytest tests` در محدودیت زمانی محیط پایان نیافت. اجرای broad با `-x` یک مشکل order/isolation در legacy test harness نشان داد (state مشترک `FAIL`)؛ اجرای همان تست به‌تنهایی پاس شد.
- یک تست pipeline در اجرای ترکیبی پس از تغییر state محیط، به علت در دسترس نبودن UNC sourceها fail شد؛ همان تست به‌تنهایی روی package پاس شد. این نشان می‌دهد suite هنوز وابستگی به state/env دارد.
- workbookهای واقعی شبکه سازمانی و دسترسی UNC تولید در این محیط وجود نداشت؛ بنابراین throughput و reconciliation production ادعا نمی‌شود.

## invariantهای حفظ‌شده

1. Archive bytes و physical cells حذف نمی‌شوند.
2. frame write همچنان در transaction واحد انجام می‌شود.
3. index، dtype، attrs و row order در round-trip حفظ می‌شوند.
4. هیچ currency متفاوتی در decision-facing total به یک float بی‌واحد تبدیل نمی‌شود.
5. unknown balance به zero/settled downgrade نمی‌شود.
6. conflicting amount برای یک REG/currency به‌جای حدس زدن، صریحاً conflict اعلام می‌شود.

## benchmark

جزئیات و اعداد A/B در `ARCHITECTURE_OPTIMIZATION_V29_8_1_FA.md` ثبت شده‌اند. benchmarkها synthetic/local هستند و فقط برای مقایسه نسخه‌ها معتبرند.

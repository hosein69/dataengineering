# اعتبارسنجی Release — V29.4.3

## تست‌های مستقیم تغییرات

- `test_v29_4_2_diagnose_business_semantics.py`
- `test_v29_4_3_relation_health_contract.py`
- `test_v29_4_1_runtime_diagnostics.py`
- `test_v29_4_resilience_editorial.py`
- `test_v29_business_dwh.py`
- `test_v29_reliability_gate.py`

نتیجه: **27 passed / 0 failed**

## تست‌های سازگاری Pipeline / Process / Runtime

- Process Cockpit
- Runtime V27.2.1
- Rules & Moghavemat
- Validation pipeline

نتیجه: **22 passed / 0 failed / 3 deselected**

سه deselected تست legacy به fixtureهای مستقل `res/df` نیاز دارند و به این تغییر وابسته نیستند.

## محدودیت اعتبارسنجی

دسترسی به Share واقعی IKCO در محیط Release وجود ندارد؛ بنابراین Source Matchهای واقعی باید بعد از نصب با:

```bash
python -m gsi.diagnose --excel --headers
```

دوباره تولید شوند. هدف این Release اصلاح منطق تشخیص است، نه ادعای نتیجه جدید برای داده‌ای که در این محیط قابل واکشی نیست.

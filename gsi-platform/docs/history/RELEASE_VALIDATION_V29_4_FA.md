# اعتبارسنجی Release V29.4

- `python -m py_compile` روی ماژول‌های تغییرکرده: PASS
- تست اختصاصی V29.4 (stale fallback، fault isolation، critical spine، editorial tokens): **4/4 PASS**
- مجموعه گسترده تست‌ها: **236 PASS / 0 FAIL / 4 deselected**
- 4 مورد deselected مربوط به تست‌های legacy هستند که fixtureهای `res/df` را در pytest تعریف نکرده‌اند؛ این مسئله از قبل وجود داشته و failure محصول نیست.
- تست‌های architecture/pipeline synthetic نیز در مجموعه بالا PASS شده‌اند.
- تست‌های وابسته به Share واقعی IKCO در این محیط قابل تأیید نیستند.

# Release Validation — V29.3

کنترل‌های این Release:

- Python syntax compile: PASS
- Static chatbot JavaScript syntax (`node --check`): PASS
- Static bundle build with knowledge + weekly lesson: PASS
- Zero-server assertion (`/api/chat` absent): PASS
- Source-root privacy in static index: PASS
- Report HTML opens static chatbot with prefilled question: PASS
- UNC -> `file://` conversion: PASS
- Regression suite مرتبط با HTML/Report/Studio/Process/AnythingLLM legacy compatibility: 28 PASS / 0 FAIL

هشدارهای مشاهده‌شده: سه هشدار NumPy `Mean of empty slice` در تست‌های قدیمی tab isolation؛ failure محسوب نمی‌شوند.

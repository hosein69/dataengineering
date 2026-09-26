# GSI V29.2 — Offline Knowledge Desk

## هدف
یک دستیار دانش بازرگانی بسیار سبک برای شبکه کاملاً آفلاین، بدون AnythingLLM/Docker/Vector DB اجباری.

## معماری
- Shared Folder = منبع دانش و آموزش‌ها
- SQLite + FTS5 = ایندکس محلی
- Python ThreadingHTTPServer = سرویس داخلی Chat بسیار سبک
- Streamlit = انتخاب مسیر، Build/Refresh، تست سؤال و مانیتورینگ
- HTML = کارت آموزش + mini chat + لینک fallback به صفحه مستقل

مسیر Share داخل HTML قرار نمی‌گیرد. HTML فقط `public_url` سرویس داخلی را می‌داند.

## روند کار مدیر
1. Streamlit → «دستیار دانش بازرگانی»
2. مسیر پایگاه دانش را با مرورگر پوشه داخلی انتخاب کنید.
3. مسیر آموزش‌های هفتگی را جدا انتخاب کنید.
4. آدرس قابل دسترس کاربران مانند `http://GSI-SERVER:8765` را تعیین کنید.
5. «ایجاد / به‌روزرسانی چت‌بات» را بزنید.

## Incremental Index
برای هر فایل path/hash/mtime/size ذخیره می‌شود. فایل بدون تغییر دوباره Parse نمی‌شود. فایل خراب یا parser‌نشده در `kb_quarantine` ثبت می‌شود و Build سایر فایل‌ها ادامه پیدا می‌کند.

## فرمت‌ها
بدون dependency اضافی: TXT, MD, HTML, JSON, CSV, XLSX/XLSM.
PDF با `pypdf` و DOCX با `python-docx` به شکل اختیاری پشتیبانی می‌شود. نبودن این packageها باعث crash کل سیستم نمی‌شود.

## رفتار HTML و Outlook
- اگر HTML به‌صورت فایل/attachment در مرورگر باز شود، mini-chat می‌تواند مستقیم با endpoint داخلی `/api/chat` صحبت کند.
- Outlook ممکن است JavaScript بدنه ایمیل را حذف کند؛ به همین دلیل همیشه یک لینک معمولی «باز کردن دستیار در صفحه مستقل» نیز وجود دارد.
- آدرس Shared Folder و SQLite در HTML افشا نمی‌شود.

## Fail-safe
Knowledge Desk یک sidecar است. خرابی آن نباید DWH، Streamlit Studio یا گزارش‌های اصلی را متوقف کند. هنگام restart Streamlit، اگر config فعال باشد سرویس به‌صورت خودکار دوباره start می‌شود.

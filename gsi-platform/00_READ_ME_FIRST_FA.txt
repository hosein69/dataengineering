GSI 29.9.0 — 2026-09-26

1) همین پوشه را روی یک دیسک محلی Extract کنید، مثلا:  D:\GSI_APP\
   (نه مسیر شبکه/UNC؛ فقط فایل‌های سورس از شبکه خوانده می‌شوند)

2) فقط این فایل را اجرا کنید:  00_RUN_GSI.cmd
   اولین اجرا: محیط Python (.venv) نصب می‌شود، سپس Control Panel باز می‌شود.

3) ترتیب اولین راه‌اندازی در Control Panel:
   Doctor  ←  Refresh data  ←  Verify published DWH  ←  Start GSI

   دفعات بعد فقط Start GSI.   داده جدید: Refresh ← Verify ← Start.
   Excel: Export Excel.   فضای مالی: RUN_FINANCIAL_WORKSPACE.cmd

DWH پیش‌فرض:      D:\GSI_DATA\warehouse.sqlite
تنظیم مسیرها فقط در: OPS\GSI_ENV.cmd

چه چیزی در این نسخه عوض شد؟   GSI_REVIEW_REPORT_V29_9_0_FA.md
راهنمای نصب:                   INSTALL.md
محدودیت‌های باز:               KNOWN_LIMITATIONS.md
اسناد نسخه‌های قبل:            docs\history\

GSI FINAL ONE PACKAGE — 2026-09-26

فقط همین پوشه را روی یک دیسک محلی Extract کنید، مثلا:
D:\GSI_APP\

سپس فقط این فایل را اجرا کنید:
00_RUN_GSI.cmd

در اولین اجرا اگر محیط Python آماده نباشد، نصب runtime انجام می‌شود و سپس Control Panel باز می‌شود.

ترتیب اولین راه‌اندازی در Control Panel:
1) Doctor
2) Refresh data
3) Verify published DWH
4) Start GSI

برای دفعات بعد فقط Start GSI کافی است.
برای ورود داده جدید: Refresh -> Verify -> Start.
برای Excel: Export Excel.

DWH پیش‌فرض:
D:\GSI_DATA\warehouse.sqlite

تنظیم مسیرها فقط در:
OPS\GSI_ENV.cmd

Core نهایی GSI دست‌نخورده است؛ این بسته فقط OPS را کنار Core قرار داده و یک Entry Point ساده اضافه کرده است.

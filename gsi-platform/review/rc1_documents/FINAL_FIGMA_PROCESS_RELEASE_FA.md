# GSI V28 — Final Figma Process-first Release

این Release بر پایه آخرین شاخه‌ی V28 شامل Commercial Expert Header fix و Dashboard Resistance binding ساخته شده است.

## تغییرات نهایی
- انتقال Design System فایل Figma `GSI — Process Operations Cockpit` به Streamlit.
- تب جدید `◈ مرکز عملیات` در Studio.
- Process Cockpit در Dashboard مستقل.
- Decision Cards، Process/WIP Strip، Operational Kanban، Material Resistance و Priority Cases.
- Kanban فقط از `case_actions` واقعی؛ بدون velocity/burndown ساختگی.
- responsive rules برای Desktop/Tablet/Mobile و `prefers-reduced-motion`.
- مقاومت اصلی: `(STOCK_IKCO + STOCK_SAPCO) / DAILY_NEED`.
- Missing هرگز Zero نیست.
- Oracle two-sheet policy و Commercial Expert `_GS`/header fixes نسخه پایه حفظ شده‌اند.
- گزارش‌ها/Templateها همچنان persona-separated هستند.

## اعتبارسنجی این Build
- 71 تست مستقل مرتبط: PASS.
- تست‌های مستقیم شبکه IKCO در محیط build قابل اجرا نیستند.
- Manifest پس از تغییرات بازسازی شده و باید 0 اختلاف گزارش کند.

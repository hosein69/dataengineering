# GSI V28 — Figma Process Operations Cockpit

این نسخه کد اجرایی را با فایل Figma `GSI — Process Operations Cockpit` همگام می‌کند.

- Figma key: `Abh0S2zpkk25P7HTNdpipa`
- Desktop reference node: `5:4`
- Mobile reference node: `6:54`

## قرارداد طراحی
- RTL فارسی و IRANSans-first font stack.
- Navy = Data/Trust، Teal/Aqua = Process/Flow، Gold فقط Decision accent.
- Decision Cards، Process/WIP strip، Operational Kanban، کم‌مقاومت‌ترین قطعات و Priority Cases.
- Responsive: 4→2→1 decision cards؛ process strip افقی؛ mobile task-first.
- `prefers-reduced-motion` رعایت می‌شود.
- Missing هرگز Zero نیست.
- Kanban فقط از `case_actions` واقعی ساخته می‌شود؛ velocity/burndown جعلی وجود ندارد.

## مسیر drill-down
Decision → Process/WIP → Kanban/Bottleneck → Material Resistance → Case → Event Timeline / Source Lineage.

## مقاومت
`(STOCK_IKCO + STOCK_SAPCO) / DAILY_NEED`

bucketهای نزد سازنده / در راه / گمرک اطلاعات تکمیلی Supply Position هستند و نبود آنها مانع طبقه‌بندی بحرانی مقاومت انبار نمی‌شود.

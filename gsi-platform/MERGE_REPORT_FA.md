# گزارش ادغام GSI V28 — Consolidated Full

## مبنا
- Source of Truth: `GSI_V28_SQLITE_DWH_FINAL`
- Donorها: `GSI_V28_CORRECTED_FULL`، `GSI_V28_1_FX_OBLIGATION`، `AIBL_V26_18_0_AUTOMOTIVE_STUDIO_FINAL`
- اصل ادغام: معماری و قراردادهای V28 حفظ شده و قابلیت/اصلاح donorها به namespace و pipeline خود GSI منتقل شده‌اند؛ AIBL موازی داخل محصول ساخته نشده است.

## اصلاحات و قابلیت‌های منتقل‌شده
- Corrected HTML hardening و escape امن JSON/script.
- nullable-boolean hardening در Event Log.
- حفظ قرارداد ثابت 17 شیت حتی در نبود Commercial Expert Data.
- Oracle multi-sheet union/resolution از V28.1.
- FX Obligation warehouse/mart و تست‌های آن.
- ایزوله‌سازی تست Control Center از Warehouse سراسری ماشین.
- Semantic metrics، metric registry و grain-aware aggregation از Studio قدیمی.
- Access scoping سطح ردیف/فیلد در Report Builder.
- Chart catalog توسعه‌یافته و انتخاب مستقل نمودار HTML و Email.
- Save/Load design شامل تنظیمات نمودار و Email composer.
- Email composer با TO/CC/Subject/Header/Intro و Outlook draft/send.
- HTML: فیلتر مرورگری، pagination، Excel از active slice، PDF/Print، Process Explorer مبتنی بر Event Log فیلترشده، lineage metadata.
- Excel chart RTL/fa-IR و IRANSans metadata.
- Historical SQLite warehouse compatibility به‌صورت لایه مستقل و بدون تداخل با DWH اصلی V28، به همراه CLI و Streamlit explorer.
- اصلاح KPI مانده تعهد برای جلوگیری از double-count ناشی از fan-out join.

## تست‌های ادغام اجراشده
- Oracle union + FX Obligation + Corrected HTML regression: 20 passed.
- V26.16 release regression: 13 passed.
- V26.18 charts/delivery/persistence: 21 passed.
- Historical warehouse V26.17: 19 passed.
- Browser HTML V26.17 (Playwright/Chromium): 9 passed.
- Control Center V27.2: 17 passed.
- Compile کل `gsi`, `app`, `tests`: موفق.
- اجرای تجمیعی `run_all_tests.py` تا سقف زمانی محیط ادامه یافت و در بخش‌های اجراشده شکست ثبت نشد؛ از جمله suiteهای 14/14 و 79/79. اجرای کامل runner به دلیل timeout محیط پایان طبیعی نداشت، بنابراین ادعای «کل runner 100% تمام شد» نشده است.

## نکته‌های نگهداری
- DWH جدید V28 همچنان warehouse اصلی است؛ Historical Warehouse فقط compatibility/history layer است.
- `gsi.warehouse.historical_store` عمداً lazy/direct import نگه داشته شده تا circular import با logging ایجاد نشود.
- هشدارهای pandas مربوط به DataFrame fragmentation در `s20_derive.py` عملکردی‌اند و در تست‌های فعلی خطای صحت ایجاد نکرده‌اند؛ برای بهینه‌سازی سرعت آینده می‌توان batch assignment/concat انجام داد.

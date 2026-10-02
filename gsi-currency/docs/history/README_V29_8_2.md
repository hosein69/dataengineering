# GSI 29.8.2 RC4-OPT2 — Source-authority FX Equivalent hardening

این نسخه روی 29.8.1 RC4-OPT1 ساخته شده و authority سورس یا RuleBook را عوض
نمی‌کند. هدف آن این است که اطلاعاتی که **همین حالا در Sourceها وجود دارد** —
نرخ ارز، معادل EUR و معادل IRR — در لایه Semantic و خروجی‌های تصمیم‌ساز به‌درستی
مصرف شود، بدون اینکه EUR/USD/CNY به‌صورت Native با هم جمع شوند.

قاعده authority در این نسخه روشن است: برای خرید ارز، `FX_EUR_VALUE` و
`FX_RIAL_VALUE` همان Source مرجع مستقیم‌اند؛ برای اعتبارات، `CRD_EUR_AMOUNT` و
`CRD_RIAL_AMOUNT` مرجع مستقیم‌اند. مانده تعهد NTSW در Release Commitment معادل
مستقیم EUR/IRR ندارد، بنابراین Equivalent آن فقط یک **reference valuation** است و
تنها از شاهد **همان REG + همان Currency** ساخته می‌شود. Basis هر عدد در خروجی
ذخیره می‌شود و نرخ پرونده یا ارز دیگری هرگز قرض گرفته نمی‌شود.

برای پرونده چندارزی، `FX_PURCHASED_AMOUNT` عدد بی‌واحد تولید نمی‌کند؛ Native به
تفکیک ارز نمایش داده می‌شود. نرخ موزون نیز فقط برای تک‌ارز عددی است و در
پرونده چندارزی نرخ هر ارز جدا نمایش داده می‌شود. Equivalentهای مستقیم Credit با
شماره LC dedupe می‌شوند و conflict به‌جای حدس‌زدن عدد، صریح علامت می‌خورد.

جزئیات در `FX_EQUIVALENT_AUTHORITY_V29_8_2_FA.md` و نتیجه تست‌ها در
`VALIDATION_V29_8_2_FX_EQUIVALENT_FA.md` است. این بسته production certification
نیست چون workbookهای واقعی UNC/شبکه سازمانی در محیط ممیزی در دسترس نبودند.

---

# نسخه مبتنی بر نقشه سورس‌ها

ابتدا SOURCE_ROADMAP_FA.md و UPDATED_CODE_AND_REPO_REVIEW_FA.md را بخوانید. evidence.txt شامل نمونه واقعی است، نه تمام فایل‌های تولیدی. مسیر SAP با GSI_GS_FULL_CHAIN قابل تنظیم است. در فایل رجیستری سفارشی، native_sheets مربوط به SAP و file_names مربوط به هر دو فایل خرید ارز را نیز منتقل کنید. هیچ ریپوی یادگیری وارد وابستگی‌ها نشده است. نتایج RC2 زیر تاریخی هستند؛ لاگ جاری در review/roadmap/final_full_regression.log قرار دارد.

# GSI 29.8.1 RC4-OPT1 — performance + financial accuracy hardening

این بسته روی RC4 ساخته شده و بازنویسی معماری نیست. دو هدف محدود دارد: کاهش
مصرف RAM/I/O در Warehouse و بستن جمع‌های مالی تصمیم‌ساز که در دانه ردیف
انجام می‌شدند. منطق RuleBook، authority سورس‌ها و فرمول هسته رفع تعهد تغییر
نکرده است.

تغییرات اصلی: نوشتن frameهای SQLite به‌صورت batch و اتمیک؛ reuse آرشیو
physical-cell برای workbook تکراری؛ عدم نگهداری هم‌زمان cell-map فایل‌های
Legacy در RAM؛ و یک summary مالی مشترک که «مانده تعهد/جریمه» را در دانه
ثبت سفارش یکتا و به تفکیک ارز نمایش می‌دهد. `BALANCE_IS_UNKNOWN` در
خروجی‌های تصمیم‌ساز دیگر صفر یا «تسویه‌شده» تلقی نمی‌شود. نمودارهای Excel،
Studio، ایمیل مدیریتی، scorecard و history از همان قرارداد استفاده می‌کنند.

جزئیات ممیزی، benchmark مصنوعی و محدودیت‌های اعتبارسنجی در
`ARCHITECTURE_OPTIMIZATION_V29_8_1_FA.md` و `VALIDATION_V29_8_1_OPT.md` است.
این نسخه production certification نیست؛ تست روی سورس‌های واقعی شبکه سازمانی
در این محیط ممکن نبود.

# GSI 29.8.0 RC4 — output integrity delivery

Start with RC4_OUTPUT_INTEGRITY_FA.md, then CONFIRMATIONS_AND_LIMITS_FA.md and
KNOWN_LIMITATIONS.md. This is not production sign-off.

What changed in RC4, all measured rather than asserted: every exported HTML now
declares which rows and columns it contains and which column names it left out;
the cash-flow bridge reads the real OF workbook instead of rejecting all of it,
and no longer fans a case-grain column out across its rows; empty report
sections state their own reason; `python -m gsi.warehouse reset --yes` wipes and
rebuilds the warehouse; the dashboard opens on the published snapshot instead of
rerunning the pipeline; and the process catalog gained seven Kanban/Scrum views
and two Kanban lane modes. The current full-runner result is in VALIDATION_RC4.md.

Install using INSTALL.md and requirements.txt. Run `python -m streamlit run app/cashflow.py` or RUN_FINANCIAL_WORKSPACE.cmd. The default financial source is the published DWH. No supplementary external ledger is required. Original corporate inputs and a valid published run remain necessary. Python/dependency wheels and real corporate data are not bundled.

All original source modules, tests, configuration and historical documentation remain included. Prior root review documents are preserved under review/rc1_documents. Current findings inherit every unresolved RC1 finding unless explicitly updated in FINDINGS_REGISTER.md.

Full-runner result for this release: VALIDATION_RC4.md. Synthetic browser checks and evidence are in review/rc2_validation. Read KNOWN_LIMITATIONS.md before deployment.


پیکربندی جاری: 13 بسته YAML. **23 قاعده** که باید با مالک مقررات تطبیق داده شوند. داشبورد — 17 شیت.

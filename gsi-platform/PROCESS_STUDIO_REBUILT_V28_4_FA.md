# GSI V28.4 — Process Studio Rebuilt

این Release یک patch ظاهری نیست؛ معماری Report Composer، Process Mining، Kanban و Cluster Scope بازسازی شده است.

## 1. Composer واقعی و مستقل در سطح تب
هر تب اکنون یک سند مستقل با `id` پایدار است و تنظیمات زیر را خودش نگه می‌دارد:
- Block order
- Fields
- Charts
- Process Views
- Kanban mode
- Kanban card fields
- Max rows

هیچ Chart/Process/Kanban به‌صورت global به همه تب‌ها inject نمی‌شود. برای مهاجرت Designهای قدیمی، نمودارهای global فقط به تب اول منتقل می‌شوند؛ تب‌های دیگر مستقل می‌مانند.

در HTML نیز `.pane[hidden]{display:none!important}` تضمین می‌کند فقط یک تب در هر لحظه دیده شود.

## 2. Composer مستقل برای هر Persona
`expert / manager / executive / analyst` دیگر یک `report_tabs` مشترک ندارند. State در `report_tabs_by_persona` جداست؛ تغییر چیدمان مدیر، کارشناس را تغییر نمی‌دهد. دکمه «کپی Composer» فقط زمانی استفاده می‌شود که کاربر عمداً بخواهد یک چیدمان را به Persona دیگر کپی کند و پس از کپی stateها مستقل‌اند.

## 3. Process Mining تخصصی
Process block می‌تواند به‌صورت مستقل این Viewها را داشته باشد:
- Process Map + WIP
- Stage Aging
- Bottleneck Ranking (Median/P90)
- Transition Heatmap
- Variant Explorer
- Conformance
- Event Coverage Funnel
- Interactive Case Timeline

تمام Viewها از Event Log/Case Table واقعی ساخته می‌شوند. Funnel نرخ تبدیل تجاری فرض نمی‌کند و Root-cause language از همبستگی فراتر نمی‌رود.

## 4. Kanban / Scrum Action Board
Board فقط از `case_actions` واقعی ساخته می‌شود؛ velocity/burndown ساختگی وجود ندارد.

Lane modeها:
- Due window
- Priority
- Owner
- Status

کارت‌ها می‌توانند Action، Owner، Due/Aging، Priority، Reason، Evidence Gap و Rule Basis را نشان دهند. در هر lane فقط 7 اقدام اول بر اساس Priority سپس Due/Aging نمایش داده می‌شود و باقی با `+ N مورد دیگر` جمع می‌شوند تا Board دوباره به جدول بلند تبدیل نشود.

Streamlit Process Cockpit نیز از `st.columns` ساده به Board HTML واقعی ارتقا یافته است.

## 5. Scope واقعی Process/Kanban برای خروجی نقش‌محور
پس از Access Scope روی Main DataFrame، Event Log، Case Table، Conformance و Action Queue نیز به همان case/order/registration/material universe محدود می‌شوند. Stage Queue، Variants و Bottlenecks از population scoped دوباره محاسبه می‌شوند.

بنابراین گزارش کارشناس/مدیر process/action data خارج از scope خود را نمی‌بیند.

## 6. Cluster Scope
Cluster membership اکنون واقعاً authorization است:
- Expert: فقط خود فرد
- Manager: خود مدیر + expertهای فعال همان cluster
- Executive: همه اعضای فعال همان cluster
- `scope_employee_codes`: override صریح و افزایشی

HR title/position به‌صورت ضمنی authorization نمی‌سازد.

## 7. Figma → Code
پیاده‌سازی با Design Context مستقیم Figma از nodeهای زیر تطبیق داده شد:
- `4:2` — GSI Operational Patterns
- `5:4` — Desktop Process Operations Cockpit

Design tokens، hierarchy، Process-first composition، Aqua/Teal + Navy، card radii، typography و Action Board به کد Streamlit/HTML map شده‌اند.

## 8. Browser QA واقعی
یک artifact سه‌تب ساخته و با Chromium/Playwright اجرا شد:
- Tab A: Process Mining فقط
- Tab B: Kanban فقط
- Tab C: KPI + Charts + Table فقط

نتیجه:
- visible pane در هر لحظه = 1
- Process در Kanban tab = 0
- Kanban در Process tab = 0
- Table در Process/Kanban tab = 0
- Case Timeline رندر شد
- Page JavaScript errors = 0

## 9. تست‌ها
Suite منتخب production/regression:
- `78 passed`
- `2 deselected`: دو تابع قدیمی `test_excel(res)` که fixture `res` در خود تست تعریف نشده است.

تست‌های جدید:
- `test_report_composer_tab_isolation_v284.py`
- `test_cluster_scope_v284.py`

## 10. قواعد غیرقابل تغییر
- Missing != Zero
- Main criticality resistance = `(IKCO + SAPCO) / DAILY_NEED`
- supplier / in-transit / customs مقاومت‌های جدا و تکمیلی‌اند
- هیچ KPI/Process/Kanban ساختگی برای زیباتر کردن خروجی تولید نمی‌شود

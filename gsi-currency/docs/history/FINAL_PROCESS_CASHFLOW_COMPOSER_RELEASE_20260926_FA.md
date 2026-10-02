# GSI — Process Cash Flow + Streamlit Report Composer — 2026-09-26

## Scope
این release ادامه مستقیم baseline نهایی GSI است و دو قابلیت مورد درخواست را به محصول اضافه می‌کند بدون تغییر semantics داده، KPI، grain، evidence یا قراردادهای انتشار.

## 1) Cash Flow Process Explorer
- استفاده مستقیم از renderer فلوچارت/Process Explorer موجود در بسته کاربر (`process-mining-ui-kit/pm_ui/charts/process_flow.py`).
- نمایش الگوریتمی مسیر پول در مراحل: ثبت سفارش، صف/درخواست تخصیص، تخصیص، تعهد، خرید ارز، تامین وجه، پرداخت/سوئیفت، حمل، گمرک، ترخیص، اسناد بانک و رفع/عودت تعهد.
- دو نمای گراف: Frequency و Performance.
- Drill-down پرونده و مرحله تا سطح event/evidence/document/source/reference/amount/currency/status.
- جدول «مسیر پول» برای هر پرونده.
- Currency safety: ارزهای ناهمگون با هم جمع نمی‌شوند.

## 2) Streamlit Report Composer
- Drag & Drop واقعی و آفلاین با Streamlit Components v1؛ بدون وابستگی npm/pip اضافی.
- Add/Remove/Reorder برای Blockهای گزارش، نمودارها و Process Views.
- اندازه‌گذاری full / half / third / quarter قبل از Export.
- layout انتخاب‌شده به HTML Export منتقل می‌شود.
- presentation state از data state جدا است؛ جابه‌جایی/حذف/resize هیچ داده یا KPI را تغییر نمی‌دهد.

## 3) Process-row preservation hotfix
- قرارداد preservation بر physical-row identity است، نه تعداد projectionهای semantic.
- Gate حذف یا تضعیف نشده؛ missing/unexpected physical evidence همچنان BLOCK می‌شود.

## Validation
- targeted integration tests: 17/17 PASS
- Python compileall: PASS
- supplied Process Explorer renderer/layout files: hash-verified by regression test
- HTML contains frequency/performance process graphs, money-path table and evidence drill-down

## Samples
- `samples/html/GSI_CASHFLOW_PROCESS_EXPLORER_FINAL_SAMPLE_20260926.html`
- `samples/html/GSI_SAMPLE_PROCESS_CASHFLOW_COMPOSER_20260926.html`

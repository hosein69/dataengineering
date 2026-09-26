# GSI — شروع نهایی 2026-09-24

## سه مسیر اجرایی جدا شده‌اند

### 1) استفاده روزمره / باز کردن UI
`START_GSI.cmd`

- DWH پیش‌فرض: `D:\GSI_DATA\warehouse.sqlite`
- فقط Snapshot منتشرشده را می‌خواند.
- ETL و خواندن SAP/NTSW/Oracle/Credit را خودکار اجرا نمی‌کند.
- اگر تاریخ انتخابی Snapshot دقیق نداشته باشد، آخرین Snapshot منتشرشده با علامت stale نشان داده می‌شود؛ داده تازه وانمود نمی‌شود.

### 2) Refresh صریح داده‌ها
`REFRESH_GSI_DATA.cmd`

- فقط زمانی اجرا شود که فایل‌های منبع تغییر کرده‌اند یا rebuild عمدی است.
- Source ingestion → pipeline → early quality gate → Business DWH → SQLite quality gate → atomic publish.
- اگر early gate رد شود، Business DWH و Excel ساخته نمی‌شوند و Snapshot سالم قبلی فعال می‌ماند.

### 3) خروجی Excel بدون ETL
`EXPORT_GSI_EXCEL.cmd`

- از آخرین Published Snapshot در warehouse می‌سازد.
- هیچ workbook عملیاتی را دوباره نمی‌خواند.
- خروجی پیش‌فرض در `D:\GSI_DATA\exports\` است.

## پذیرش عملیاتی پس از کپی این Build روی Windows

1. پکیج قبلی را دست‌نخورده نگه دارید و این ZIP را در پوشه جدید Extract کنید.
2. `.venv` و dependencyهای همان نصب قبلی را طبق روش سازمانی برقرار کنید.
3. ابتدا `START_GSI.cmd` را اجرا کنید؛ اگر Snapshot قبلی در `D:\GSI_DATA\warehouse.sqlite` وجود دارد UI باید بدون rebuild کامل بالا بیاید.
4. برای ساخت Snapshot جدید، `REFRESH_GSI_DATA.cmd` را اجرا کنید.
5. پیام موفقیت واقعی فقط این است: `🏁 اجرای کامل GSI با موفقیت پایان یافت و Snapshot جدید منتشر شد.`
6. برای Excel از `EXPORT_GSI_EXCEL.cmd` استفاده کنید؛ این مسیر نباید Refresh را اجرا کند.

## قراردادهای حیاتی این Build

- `REG`، `REG_FILE`، `ORDER` و `BL` هویت‌های جدا هستند.
- `sap/raw_rows` در grain فیزیکی `SAP_SOURCE_SHEET + SAP_SOURCE_ROW` کنترل می‌شود.
- Unknown مالی به Zero تبدیل نمی‌شود؛ Zero فقط با شاهد عددی صفر است.
- source lineage در merge حذف نمی‌شود؛ lineage سمت راست namespaced می‌شود.
- Streamlit مصرف‌کننده Published Snapshot است، نه trigger پیش‌فرض ETL.

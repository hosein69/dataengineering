# AIBL V26.17.0 — SQLite Warehouse & HTML-only Delivery

## هدف

این نسخه مرز بین **ذخیره/تحلیل داده** و **Artifact ارائه** را صریح می‌کند: SQLite سیستم ثبت تحلیلی AIBL است و HTML تنها artifact ارسالی Studio/Email است. Excel و PDF در مرورگر دریافت‌کننده از همان HTML تولید می‌شوند.

## Data Warehouse

- `dw_run`: lifecycle هر اجرا، شامل RUNNING/SUCCESS/FAILED و `run_id` سراسری.
- `source_run_log`: lineage، تعداد ردیف/ستون و fingerprint هر frame ورودی.
- `fact_case_snapshot`: Snapshot پهن تمام خروجی Pipeline با partition.
- `fact_event` + `bridge_run_event`: Event catalogue deduplicated/immutable و عضویت event در هر اجرا.
- `fact_transition_snapshot`: هر حرکت واقعی پرونده A→B، زمان ابتدا/انتها و `wait_days`.
- `fact_case_process_snapshot`: variant، throughput، rework و completeness هر case.
- `fact_kpi_snapshot`: KPIهای تاریخی برای trend.
- `case_state_log`: تفاوت state هر case بین snapshotها.
- `audit_log`: رویدادهای عملیاتی، runtime log، ساخت گزارش و ایمیل.

SQLite با WAL، foreign keys و busy timeout اجرا می‌شود. عملیات retention و compact از CLI در دسترس است.

## Studio

Studio به‌جای اجرای Pipeline در هر rerun، Snapshot همان تاریخ را از SQLite می‌خواند. تب Warehouse شامل Run History، Source Lineage، KPI Trend، Case Timeline، Snapshot Changes، Transition Bottlenecks و Audit Log است. Pipeline فقط با دکمه «به‌روزرسانی Warehouse» اجرا می‌شود.

## HTML-only

- Report Builder در Studio فقط HTML تحویل می‌دهد.
- Email روزانه فقط HTML تعاملی را attach می‌کند.
- HTML شامل `warehouse_run_id` برای traceability است.
- Export Excel روی active browser filter انجام می‌شود و cellهای عدد/تاریخ typed هستند.
- PDF از همان DOM با Print / Save as PDF مرورگر ساخته می‌شود تا RTL/Persian rendering حفظ شود.
- Process Explorer برای CASE_KEYهای active filter دوباره bottleneck/variant را محاسبه می‌کند.
- payload cap مانع تولید HTML چندصد مگابایتی می‌شود؛ دیتای کامل در Warehouse باقی می‌ماند.

## عملیات

```bash
python -m aibl warehouse stats
python -m aibl warehouse runs --limit 20
python -m aibl warehouse case CASE-123
python -m aibl warehouse bottlenecks --org "گمرک"
python -m aibl warehouse audit --limit 100
python -m aibl warehouse lineage
python -m aibl warehouse prune --keep 365
python -m aibl warehouse vacuum
```

## Environment

`AIBL_WAREHOUSE_ENABLED`, `AIBL_WAREHOUSE_PATH`, `AIBL_WAREHOUSE_REQUIRED`, `AIBL_STUDIO_SOURCE`, `AIBL_SQLITE_LOG`.

## Compatibility

Legacy Python APIs for official Excel/PDF remain available for backward compatibility, but Studio and Daily Email no longer use them as primary artifacts or storage. SQLite remains a single-writer analytical tier; the Warehouse API isolates persistence so a future PostgreSQL/SQL Server backend can be added without changing business stages.

## Final hardening

- `run_id` با UUID ساخته می‌شود تا refreshهای چندباره همان تاریخ collision نداشته باشند.
- backfill تاریخی فقط با آخرین state همان بازه زمانی مقایسه می‌شود و از آینده نشت نمی‌گیرد.
- KPI تاریخی «میانگین مقاومت»، KPI «مانده تعهد» و «جریمه برآوردی» همگی از Grain Registry استفاده می‌کنند.
- Event bridge شمار occurrence یکتا را ثبت می‌کند.
- سه suite قدیمی pytest-style حالا در Runner فایل‌محور نیز واقعاً اجرا می‌شوند.
- Browser runtime روی Chromium برای فیلتر، Excel typed، PDF/Print و خطاهای JavaScript اعتبارسنجی شد.

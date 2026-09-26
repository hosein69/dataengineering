# Runbook نهایی GSI — Data Warehouse & Orchestration

**نسخه مبنا:** GSI 29.8.2 RC4-OPT2 H1 — FINAL CLEAN — 2026-09-26  
**دامنه این سند:** فقط Data Warehouse، ingestion، orchestration، quality gate، snapshot، publish، startup، export، concurrency، backup/recovery و migration مسیر DWH.  
**اصل محافظت:** هیچ فایل Core، منطق کسب‌وکار، UI/UX، grain، relation، KPI یا RuleBook در این Ops Kit تغییر داده نمی‌شود.

---

## 1) خروجی نهایی که باید ران شود

فایل Core تأییدشده:

`GSI_29_8_2_RC4_OPT2_H1_FINAL_CLEAN_20260926.zip`

SHA-256 رسمی:

`167489cfd601365cca3e4e89b88ca4302fba1a7a207144460678be834e0cc09c`

Gate ثبت‌شده برای Clean Release:

- Compile: PASS
- Frozen independent audit: 173/173 PASS
- Extended audit: 77/77 PASS
- Targeted release regression: 85/85 PASS
- runtime/cache artifact داخل release: صفر
- package manifest missing/mismatch/extra: صفر

**قاعده:** Core ZIP را ویرایش نکنید. پوشه `OPS` این بسته را فقط به‌عنوان overlay کنار Core قرار دهید.

---

## 2) معماری عملیاتی نهایی

مسیر داده از صفر تا publish:

```text
Source files / network shares
        │
        ▼
Adapters + native grains + lineage
        │
        ▼
Core Pipeline / standardized frames / business stages
        │
        ▼
Persist forensic + mart frames into SQLite
        │
        ▼
EARLY QUALITY GATE
  source / grain / schema / runtime / process / partition
        │
   PASS │                     FAIL
        ▼                       └──> no Business DWH, no publish,
Business DWH                         previous good snapshot remains live
  native-grain facts
  entities / relations
  source evidence
        │
        ▼
SQLite integrity + FK checks
        │
        ▼
FINAL QUALITY GATE
        │
        ▼
Immutable semantic snapshot
        │
        ▼
Atomic publish of report + dwh slots
        │
        ├──> START_GSI / Studio: published snapshot only
        └──> EXPORT_GSI_EXCEL: published snapshot only, no ETL
```

این جداسازی عمداً مانع آن می‌شود که باز کردن UI، ساخت Excel یا refresh ناقص، pipeline سنگین را ناخواسته اجرا یا snapshot سالم قبلی را جابه‌جا کند.

---

## 3) محل فایل‌ها روی Windows

پیشنهاد نصب:

```text
D:\GSI_APP\                         ← کد Extract شده Clean Release
D:\GSI_APP\gsi\
D:\GSI_APP\app\
D:\GSI_APP\OPS\                    ← همین Ops Kit
D:\GSI_APP\.venv\                  ← Python virtual environment

D:\GSI_DATA\                        ← داده runtime؛ خارج از release
D:\GSI_DATA\warehouse.sqlite       ← operational warehouse اصلی
D:\GSI_DATA\warehouse.writer.lock  ← OS writer lock پایدار
D:\GSI_DATA\warehouse.writer.lock.meta.json
D:\GSI_DATA\warehouse.sqlite.frame_cache\  ← cache قابل بازسازی
D:\GSI_DATA\exports\               ← exportهای snapshot
D:\GSI_DATA\backups\               ← backupهای این Ops Kit
```

مسیر رسمی operational warehouse:

`D:\GSI_DATA\warehouse.sqlite`

اولویت resolve شدن مسیر در Core:

1. `GSI_DWH_PATH`
2. `GSI_DATA_ROOT\warehouse.sqlite`
3. `D:\GSI_DATA\warehouse.sqlite`

SQLite فعال باید روی **دیسک محلی** باشد. UNC و mapped network drive برای فایل اصلی SQLite عمداً رد می‌شوند. سورس‌های Excel می‌توانند روی share شبکه باشند؛ خود DWH نه.

Historical warehouse یک دیتابیس جداست و در صورت نیاز با `GSI_HISTORICAL_WAREHOUSE_PATH` تنظیم می‌شود؛ آن را با operational `warehouse.sqlite` یکی نکنید.

---

## 4) نصب Runtime — یک بار برای هر Extract جدید

حداقل Python: **3.11+**.

روش ساده:

`OPS\INSTALL_RUNTIME.cmd`

یا دستی:

```cmd
cd /d D:\GSI_APP
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

وابستگی‌های اصلی Core شامل pandas، numpy، openpyxl، PyYAML، cryptography، Streamlit، Plotly، streamlit-sortables و matplotlib هستند.

بعد از نصب، `.venv\Scripts\python.exe` باید موجود باشد. Launcherهای رسمی اگر venv نباشد عمداً اجرا را متوقف می‌کنند.

---

## 5) Environment عملیاتی

فایل:

`OPS\GSI_ENV.cmd`

به‌صورت پیش‌فرض فقط این دو مقدار را قطعی می‌کند:

```cmd
set "GSI_DATA_ROOT=D:\GSI_DATA"
set "GSI_DWH_PATH=%GSI_DATA_ROOT%\warehouse.sqlite"
```

مسیرهای سورس در خود محصول defaultهای سازمانی دارند. فقط اگر روی سیستم مقصد resolve نمی‌شوند override کنید:

- `GSI_FOREIGN`
- `GSI_BLS`
- `GSI_CLEARANCE`
- `GSI_HR`
- `GSI_GS_FULL_CHAIN`
- `GSI_GS_COMBINE`
- `GSI_ESMAEILI`
- `GSI_MOHAMADI`

**HR در `sources.yaml` دارای `required: true` است.** اگر HR load نشود یا فقط stale fallback داشته باشد، publication باید BLOCK شود. این behavior در real NTSW validation عمداً تثبیت شده است.

---

## 6) Source Registry که orchestration مصرف می‌کند

سورس‌های فعال فعلی:

| Source | نقش عمده | Join/native grain | Required |
|---|---|---|---|
| moghavemat | جمعیت/کارشناس و supply position | ORDER و ORDER×MATERIAL | خیر |
| ntsw | Import Licence / Allocation / Commitment | REG / REG_FILE | خیر |
| sap | PR / workflow / PO / inbound / GR | native SAP grains | خیر |
| oracle | inventory / daily requirement | MATERIAL | خیر |
| sata | bridge مستقیم logistics evidence | BL / ORDER / REG | خیر |
| abbasi | BL tracking enrichment | BL | خیر |
| clearance | customs clearance | BL | خیر |
| cotage | customs/cottage | BL | خیر |
| ilappend | registration-file bridge | REG / REG_FILE | خیر |
| fx_transaction | FX purchases | REG | خیر |
| credit | credit/LC | REG | خیر |
| doccheck | document status | ORDER | خیر |
| hr | employee hierarchy | EMP | **بله** |

`missmohammadi` در registry فعلی disabled است.

Business keyها مستقل‌اند: `ORDER`, `REG_FILE`, `REG`, `BL`, `PR`, `PO`, `MATERIAL`, `EMP`. هیچ کلید مفقود نباید از کلید دیگری جعل شود. SAP PO نیز ORDER فرض نمی‌شود مگر شاهد منبع صریح داشته باشد.

---

## 7) Preflight قبل از First Refresh

از ریشه پروژه:

```cmd
call OPS\GSI_ENV.cmd
.venv\Scripts\python.exe -m gsi doctor
```

Doctor این موارد را می‌بیند:

- package/module consistency و manifest
- Python dependencies
- RuleBook structure/expiry
- adapter registry
- source folders/files
- output/log writability

### وضعیت شناخته‌شده در تاریخ 2026-09-26

دو rule اضطراری موقت در 2026-09-22 منقضی شده‌اند و عمداً تمدید ساختگی نشده‌اند:

- `fx_governance.regulatory_snapshot.emergency_deadline_overlay_1405_05_14`
- `customs.emergency_sata_waiver_1405`

به همین دلیل Doctor تا ثبت successor authoritative برای آن‌ها ERR خواهد داشت. Ruleهای منقضی در runtime فعال نمی‌شوند. این موضوع یک **governance blocker** است، نه خرابی SQLite یا orchestration.

نکته اجرایی: `python -m gsi run` ابتدا Doctor را اجرا می‌کند و با ERR متوقف می‌شود؛ برای lifecycle تفکیک‌شده از Launcherهای رسمی `refresh`, `studio/start`, `export-excel` استفاده کنید. این کار rule منقضی را دور نمی‌زند یا معتبر نمی‌کند؛ rule همچنان inactive می‌ماند و sign-off مقرراتی تا successor رسمی باز است.

---

## 8) First Refresh روی نصب Clean

Clean Release عمداً `warehouse.sqlite`، cache و runtime data را در ZIP ندارد. بنابراین روی نصب تازه، قبل از نخستین publish هیچ snapshotی وجود ندارد.

پس ترتیب صحیح:

```text
Runtime installed
→ environment/path checked
→ source access checked
→ REFRESH_GSI_DATA.cmd
→ successful atomic publish
→ VERIFY_DWH.cmd = PASS
→ START_GSI.cmd
```

اجرای Refresh رسمی:

`REFRESH_GSI_DATA.cmd`

یا:

```cmd
call OPS\GSI_ENV.cmd
.venv\Scripts\python.exe -u -m gsi refresh
```

### علامت موفقیت واقعی

تنها بعد از atomic publish باید این پیام دیده شود:

`🏁 اجرای کامل GSI با موفقیت پایان یافت و Snapshot جدید منتشر شد.`

و CLI در پایان `Published snapshot: <run_id>` چاپ می‌کند.

پیام «core تمام شد» به معنی publish نیست. Business DWH، gate و publish بعد از core مسیر مستقل دارند.

---

## 9) Orchestration داخلی Refresh — دقیقاً چه اتفاقی می‌افتد

### 9.1 Run + writer lock

یک run جدید در `wh_run` با status=`running` ثبت می‌شود. Writer lock سیستم‌عامل روی `warehouse.writer.lock` می‌گیرد تا دو writer همزمان وارد DWH نشوند. metadata تشخیصی کنار آن ثبت می‌شود.

### 9.2 Configuration capture

`sources.yaml` و YAMLهای config/rules در خود warehouse به‌عنوان evidence همان run ذخیره می‌شوند تا بعداً بتوان فهمید run با چه configuration و rule set ساخته شده است.

### 9.3 Core pipeline

Adapters ورودی‌ها را load و استاندارد می‌کنند، lineage را نگه می‌دارند، stageهای کسب‌وکار را اجرا می‌کنند و mart/extras را داخل warehouse persist می‌کنند.

اگر یک source load fail شود، سیستم فقط در صورت وجود snapshot منتشرشده قبلی می‌تواند standardized frames قبلی را به‌عنوان stale continuity fallback استفاده کند؛ stale بودن ثبت می‌شود. روی نصب کاملاً تازه هیچ fallback قبلی وجود ندارد.

### 9.4 Early Gate

پیش از ساخت Business DWH سنگین، این دسته‌ها بررسی می‌شوند:

- source contracts / grains
- schema drift
- source runtime health / required sources
- process evidence row preservation
- derive coverage و Unknown semantics
- final partition row preservation

اگر Early Gate رد شود:

- Business DWH ساخته نمی‌شود.
- Excel ساخته نمی‌شود.
- run diagnostics ثبت می‌شود.
- publish رد می‌شود.
- snapshot سالم قبلی در `wh_current` جابه‌جا نمی‌شود.

### 9.5 Business DWH

فقط پس از PASS Early Gate ساخته می‌شود.

مهم‌ترین ساختارها:

- dimensions/entities برای ORDER / MATERIAL / BL / REG / REG_FILE / PR / PO / EMP
- evidence-based relations
- `dwh_fact_source_row`
- `dwh_fact_supply_position`
- `dwh_bridge_order_material_pr_item`
- Oracle material facts
- SAP PR / PO / workflow facts
- NTSW allocation request / commitment facts
- unresolved relation evidence
- registration hub view

SAP physical archive فقط یک‌بار از `raw_rows` ثبت می‌شود؛ semantic native-grain facts حذف نمی‌شوند و در fact tableهای تخصصی می‌مانند.

### 9.6 SQLite checks + Final Gate

پس از mutationهای DWH، integrity/FK checks اجرا و کل Quality Gate دوباره ثبت می‌شود.

### 9.7 Immutable semantic snapshot

از هر `dwh_*` current table، snapshot run-scoped در `snap_dwh_*` ثبت می‌شود. Snapshot برای UPDATE/DELETE immutable است. خواننده‌ها به published run pin می‌شوند؛ نه به state در حال ساخت writer.

### 9.8 Atomic publish

فقط run completed و بدون failed `BLOCK/CRITICAL/FATAL` می‌تواند publish شود.

`report` و `dwh` slots در `wh_current` با هم جابه‌جا می‌شوند. Publish event ثبت می‌شود. انتشار به run قدیمی‌تر نیز رد می‌شود.

---

## 10) ساختار Core Warehouse

هسته audit/persistence:

- `wh_meta`
- `wh_run`
- `wh_audit`
- `wh_file`
- `wh_ingest`
- `wh_sheet`
- `wh_raw_row`
- `wh_issue`
- `wh_frame`
- `wh_frame_row`
- `wh_config`
- `wh_current`
- `wh_quality_check`
- `wh_schema_baseline`
- `wh_publish_event`
- view `wh_source_reconciliation`

Snapshot layer:

- `wh_semantic_snapshot`
- `snap_dwh_*`

Business layer شامل `dwh_*` dimensions, relation, facts, bridges و views است.

این separation باعث می‌شود raw evidence، run audit، mart persistence، Business DWH و published semantic state با هم قاطی نشوند.

---

## 11) Grain مهم SAP

در workbook native، `SAP_SOURCE_ROW` در هر sheet از 1 دوباره شروع می‌شود. بنابراین grain فیزیکی معتبر:

`SAP_SOURCE_SHEET + SAP_SOURCE_ROW`

نتیجه:

- row 1 در `pr` و row 1 در `po` duplicate محسوب نمی‌شوند.
- تکرار واقعی همان sheet+row باید gate را fail کند.

Workbook native SAP نیز یک‌بار باز می‌شود و `pr / pack / po / inbound / GR` از همان lifecycle parse می‌شوند؛ از open مجدد برای هر sheet جلوگیری شده است.

---

## 12) Unknown ≠ Zero در مالی

برای شش فیلد حساس زیر، missing/invalid/non-finite evidence باید Missing بماند و فقط صفر واقعی source به 0 تبدیل شود:

- `CB_VALUE`
- `BALANCE`
- `ALLOCATED_AMOUNT`
- `OPEN_QUEUE_AMOUNT`
- `REJECTED_ALLOC_AMOUNT`
- `ALLOC_REQUESTED_GROSS`

اگر در log یا خروجی دیدید Unknown به صفر تبدیل شده، آن behavior regression است.

---

## 13) Verify بعد از هر Publish مهم

اجرای توصیه‌شده:

`OPS\VERIFY_DWH.cmd`

یا:

```cmd
call OPS\GSI_ENV.cmd
.venv\Scripts\python.exe OPS\gsi_dwh_ops.py verify
```

این helper **read-only** است و موارد زیر را می‌سنجد:

- فایل وجود دارد.
- `PRAGMA user_version == 1`
- core tables وجود دارند.
- `PRAGMA integrity_check == ok`
- `PRAGMA foreign_key_check` صفر است.
- هر دو slot `report` و `dwh` وجود دارند و به یک run اشاره می‌کنند.
- published run status=`completed` است.
- published run هیچ failed quality check با severity `BLOCK/CRITICAL/FATAL` ندارد.
- published run دقیقاً semantic snapshot ثبت‌شده دارد.
- publish event برای run جاری وجود دارد.

خروجی مطلوب:

`VERIFY_RESULT=PASS`

`OPS\STATUS_DWH.cmd` نیز برای بررسی سریع run/publish بدون تغییر دیتابیس است.

---

## 14) استفاده روزانه بعد از First Publish

### باز کردن محصول

`START_GSI.cmd`

یا گزینه Start در `OPS\GSI_DWH_CONTROL.cmd`.

START فقط published snapshot را می‌خواند. اگر تاریخ انتخابی snapshot دقیق نداشته باشد، آخرین published snapshot را با stale status نشان می‌دهد. اگر هیچ snapshot منتشرشده‌ای وجود نداشته باشد، UI از شما Refresh می‌خواهد؛ نباید ETL را خودش شروع کند.

### ورود داده جدید

فقط:

`REFRESH_GSI_DATA.cmd`

هر باز و بسته کردن UI نباید refresh ایجاد کند.

### Excel

`EXPORT_GSI_EXCEL.cmd`

Export هیچ source workbook را نمی‌خواند و ETL اجرا نمی‌کند. اگر output path ندهید، خروجی زیر parent DWH می‌رود:

`D:\GSI_DATA\exports\<reference-date>_GSI_PUBLISHED_SNAPSHOT.xlsx`

---

## 15) Concurrency و رفتار Lock

- فقط یک writer مجاز است.
- writer lock سیستم‌عامل مرجع حقیقت است؛ وجود یک فایل lock قدیمی به‌تنهایی دلیل writer فعال نیست.
- metadata lock برای diagnostics است.
- DB write timeout: 30s و `busy_timeout=30000`.
- خواننده‌های UI از read-only connection استفاده می‌کنند و به published snapshot pin می‌شوند.
- lazy analytical extra اگر موقتاً DB busy باشد نباید به صفر تبدیل شود؛ load error/None ثبت می‌شود.
- frame cache disposable است و source of truth نیست؛ SQLite source of truth است.

اگر Refresh دوم همزمان شروع شود باید fail/busy شود؛ راه درست این نیست که lock file را دستی پاک کنید. ابتدا writer واقعی را پیدا/متوقف کنید.

---

## 16) Backup استاندارد

گزینه 6 در:

`OPS\GSI_DWH_CONTROL.cmd`

یا:

`OPS\BACKUP_DWH.cmd`

یا CLI:

```cmd
call OPS\GSI_ENV.cmd
.venv\Scripts\python.exe OPS\gsi_dwh_ops.py backup
```

خروجی پیش‌فرض:

`D:\GSI_DATA\backups\warehouse_YYYYMMDDTHHMMSSZ.sqlite`

Backup با SQLite online backup API ساخته و سپس دوباره با integrity/FK check بررسی می‌شود.

**برای backup از copy خام `warehouse.sqlite` در حین Refresh استفاده نکنید.**

---

## 17) Migration از AppData قدیمی به D:\GSI_DATA

اگر DWH معتبر قبلی هنوز اینجاست:

`C:\Users\10213984\AppData\Local\GSI\warehouse.sqlite`

روش امن:

1. همه پنجره‌های GSI/Streamlit و Refreshها را ببندید.
2. مطمئن شوید `D:\GSI_DATA\warehouse.sqlite` از قبل فایل دیگری نیست.
3. از ریشه پروژه اجرا کنید:

```cmd
set "GSI_DWH_PATH=C:\Users\10213984\AppData\Local\GSI\warehouse.sqlite"
.venv\Scripts\python.exe OPS\gsi_dwh_ops.py status
.venv\Scripts\python.exe OPS\gsi_dwh_ops.py backup --output D:\GSI_DATA\warehouse.sqlite
```

4. سپس environment را به مسیر جدید برگردانید:

```cmd
set "GSI_DATA_ROOT=D:\GSI_DATA"
set "GSI_DWH_PATH=D:\GSI_DATA\warehouse.sqlite"
.venv\Scripts\python.exe OPS\gsi_dwh_ops.py verify
```

5. فقط اگر Verify PASS شد، `START_GSI.cmd` را اجرا کنید.
6. فایل AppData قدیمی را تا چند روز و تا یک Refresh موفق جدید حذف نکنید.

اگر DWH قدیمی از generation قبل باشد و immutable semantic snapshot نداشته باشد، Verify عمداً FAIL می‌شود. در آن حالت migration را به‌عنوان archive نگه دارید و یک Refresh کامل جدید روی Clean Release بسازید؛ schema/state قدیمی را با دست patch نکنید.

تغییر `GSI_DWH_PATH` به‌تنهایی فایل قدیمی را جابه‌جا نمی‌کند.

---

## 18) Restore / Disaster Recovery

Restore در Ops Kit عمداً one-click نشده چون destructive است.

رویه:

1. Refresh و Streamlit را کامل متوقف کنید.
2. از warehouse فعلی در صورت سالم بودن backup جدید بگیرید.
3. backup candidate را با helper و یک `GSI_DWH_PATH` موقت Verify کنید.
4. current DB را rename نگه دارید، حذف نکنید.
5. backup تأییدشده را در path configured قرار دهید.
6. `VERIFY_DWH.cmd` را اجرا کنید.
7. سپس START را اجرا کنید.
8. اگر Verify یا UI fail شد، به نسخه قبلی برگردید.

`reset()` Core وجود دارد اما روی active production warehouse راه recovery معمول نیست. Reset فقط با درخواست صریح، lock انحصاری و backup انجام می‌شود؛ برای خطای عادی هرگز اولین اقدام نباشد.

---

## 19) Frame Cache

مسیر معمول:

`D:\GSI_DATA\warehouse.sqlite.frame_cache\`

این cache فقط acceleration است و source of truth نیست. failure آن نباید transaction DWH را خراب کند. در صورت corruption cache، پس از بستن GSI می‌توان cache را حذف کرد تا از SQLite بازسازی شود.

خود `warehouse.sqlite` را به همین روش پاک نکنید.

---

## 20) Historical Warehouse

Operational DWH و Historical Warehouse دو lifecycle متفاوت دارند.

متغیر:

`GSI_HISTORICAL_WAREHOUSE_PATH`

CLI:

```cmd
.venv\Scripts\python.exe -m gsi historical-warehouse stats
.venv\Scripts\python.exe -m gsi historical-warehouse runs --limit 20
.venv\Scripts\python.exe -m gsi historical-warehouse case <CASE_KEY>
.venv\Scripts\python.exe -m gsi historical-warehouse bottlenecks --limit 20
.venv\Scripts\python.exe -m gsi historical-warehouse audit --limit 100
.venv\Scripts\python.exe -m gsi historical-warehouse lineage
```

Historical DB را جای `warehouse.sqlite` نگذارید.

---

## 21) Failure Playbook

### `No published GSI snapshot exists`

علت: نصب clean است یا هنوز publish موفق ندارید.  
اقدام: Source preflight → `REFRESH_GSI_DATA.cmd` → Verify.

### `source/hr:SOURCE_LOAD_FAILED`

علت: HR required است و load نشده.  
اقدام: `GSI_HR`، دسترسی share، pattern فایل و فایل واقعی HR را بررسی کنید. Publish ناقص نباید انجام شود.

### `QUALITY_GATE_BLOCKED`

علت: یک check با severity block/critical/fatal fail شده.  
اقدام: همان `contract:code` را رفع کنید؛ DB را reset نکنید. snapshot خوب قبلی باید live بماند.

### `sap/raw_rows:GRAIN_UNIQUENESS`

اول مطمئن شوید نسخه Clean Release است. row number مشترک بین دو sheet نباید fail کند؛ duplicate واقعی همان `SAP_SOURCE_SHEET + SAP_SOURCE_ROW` باید fail کند.

### `WAREHOUSE_WRITER_BUSY`

یک writer دیگر فعال است یا عملیات write هنوز تمام نشده.  
اقدام: Refresh دوم را متوقف کنید؛ lock را دستی delete نکنید. writer واقعی را ببندید و دوباره اجرا کنید.

### `database is locked` در read

UI reader bounded wait دارد. اگر writer در commit کوتاه باشد retry کنید. اگر طولانی/دائمی است writer stuck و processهای باز را بررسی کنید.

### Doctor فقط دو expired-rule error نشان می‌دهد

این همان governance issue شناخته‌شده 2026-09-22 است. کد/manifest را برای خاموش کردن error تغییر ندهید؛ successor authoritative را versioned وارد RuleBook کنید.

### `VERIFY_RESULT=FAIL` بعد از Refresh با exit code 0

این وضعیت را production success تلقی نکنید. خروجی Verify مشخص می‌کند mismatch، FK، integrity، publish slot یا snapshot کدام است؛ تا علت رفع نشده START را برای تصمیم‌گیری رسمی مبنا قرار ندهید.

---

## 22) Offline Diagnostic

برای evidence پذیرش package/environment:

`RUN_OFFLINE_DIAGNOSTIC.cmd`

خروجی استاندارد در `offline_feedback\GSI_FEEDBACK_*.zip` تولید می‌شود.

Offline diagnostic جای First Refresh روی سورس‌های واقعی را نمی‌گیرد؛ مکمل آن است.

---

## 23) Acceptance Criteria اولین اجرای واقعی Windows

اجرای واقعی فقط وقتی از نظر DWH/orchestration بسته است که همه این موارد برقرار باشند:

1. Clean Release hash با SHA رسمی یکی باشد.
2. Runtime 3.11+ و imports اصلی سالم باشند.
3. sourceهای لازم resolve و HR required load شود.
4. SAP native workbook یک lifecycle read داشته باشد.
5. SAP grain روی sheet+row باشد، نه row تنها.
6. Unknown مالی به zero ساختگی تبدیل نشود.
7. Early Gate قبل از Business DWH unsafe run را قطع کند.
8. SQLite integrity=`ok` و FK error=0 باشد.
9. Final Gate PASS شود.
10. semantic snapshot immutable ثبت شود.
11. `report` و `dwh` atomically به یک run publish شوند.
12. فقط بعد از publish پیام موفقیت نهایی چاپ شود.
13. `OPS\VERIFY_DWH.cmd` → `VERIFY_RESULT=PASS`.
14. START هیچ ETL ضمنی اجرا نکند.
15. EXPORT هیچ source workbook را باز نکند.
16. snapshot قبلی در failure جدید جابه‌جا نشود.
17. backup تست‌شده ساخته شود.
18. successor رسمی دو rule منقضی برای governance production ثبت شود.

---

## 24) وضعیت شواهد واقعی موجود

روی real `NTSW-IKCO.xlsx`:

- ingest SQLite موفق بود.
- `PRAGMA integrity_check = ok`.
- FK error = 0.
- row preservation = 14935/14935.
- NTSW-only publication به‌درستی به علت نبود required HR با `source/hr:SOURCE_LOAD_FAILED` block شد و snapshot ناقص publish نشد.

این شواهد behavior gate را تأیید می‌کنند، اما full multi-source production certification همچنان نیازمند اجرای همین Clean Release روی تمام sourceهای واقعی سازمان است.

---

## 25) ترتیب عملی پیشنهادی برای شما

از این نقطه فقط این sequence را اجرا کنید:

```text
A. Extract Clean Release to D:\GSI_APP
B. Extract Ops Kit into همان root → D:\GSI_APP\OPS
C. OPS\INSTALL_RUNTIME.cmd      (فقط اگر .venv ندارید)
D. OPS\GSI_ENV.cmd را بازبینی کنید
E. OPS\GSI_DWH_CONTROL.cmd → Doctor
F. source access را رفع کنید؛ HR باید موجود باشد
G. Control → Refresh
H. منتظر پیام final publish باشید، نه پیام core-complete
I. Control → Verify  → باید PASS باشد
J. Control → Backup
K. Control → Start
L. در ورود داده جدید فقط Refresh؛ برای Excel فقط Export
```

اگر هر مرحله fail شد، مرحله بعد را اجرا نکنید؛ علت همان مرحله را رفع کنید. مهم‌ترین اصل این release این است که **failure جدید نباید snapshot سالم قبلی را خراب کند**.

---

## 26) فایل‌های Ops Kit

```text
OPS\GSI_ENV.cmd             مسیر عملیاتی DWH و overrideهای اختیاری سورس
OPS\INSTALL_RUNTIME.cmd     ساخت .venv و نصب requirements
OPS\GSI_DWH_CONTROL.cmd     منوی عملیات DWH/orchestration
OPS\gsi_dwh_ops.py          status / verify / backup امن
OPS\STATUS_DWH.cmd          status فقط خواندنی
OPS\VERIFY_DWH.cmd          acceptance check فقط خواندنی
OPS\BACKUP_DWH.cmd          backup سازگار SQLite + verify
README_FIRST_RUN_FA.txt      شروع سریع
GSI_DWH_ORCHESTRATION_RUNBOOK_FA.md  همین سند
```

هیچ‌کدام جای فایل‌های Core را نمی‌گیرند.

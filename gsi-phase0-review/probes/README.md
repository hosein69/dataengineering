# Probes — شواهد بازتولیدپذیر OPUS_REVIEW

این اسکریپت‌ها **بیرون** درخت source پکیج GSI اجرا می‌شوند و هیچ فایلی از پکیج را تغییر نمی‌دهند.

## اجرا

```bash
python3.12 -m venv venv && ./venv/bin/pip install pandas pytest openpyxl PyYAML cryptography
unzip GSI_V29_7_6_SAP_SEMANTIC_DWH_SMART_CHATBOT.zip -d /tmp/gsi

export PKG=/tmp/gsi/gsi_2976
export GSI_DWH_PATH=/tmp/probe.sqlite      # هر probe یک DB تازه لازم دارد
./venv/bin/python p_merge.py
```

`p_merge.py` مسیر پکیج را به‌صورت literal در `sys.path.insert` دارد؛ بقیه از `$PKG` می‌خوانند.
برای هر اسکریپت `GSI_DWH_PATH` را به یک فایل تازه بدهید (چند probe وضعیت DWH را بین مراحل مقایسه می‌کنند).
خروجی JSON روی stdout است؛ لاگ‌های فارسی پکیج هم روی stdout می‌آیند، پس:
`... 2>/dev/null | grep -v "| WARNING\|| INFO\|| ERROR"`

## نگاشت probe به یافته

| فایل | کد در سند | چه چیزی را اثبات می‌کند | یافته‌ها |
|---|---|---|---|
| `p_merge.py`  | OP-01 | کلید مرکب خالی، کلید `NaN`، برخورد delimiter، حذف many-to-one، دسترس‌ناپذیری `RowExplosionError` | F019, F020, N04 |
| `p_dwh.py`    | OP-02 | نبود رابطه از `moghavemat/main`، تورم `evidence_count`، cross-product هاب، انتقال `last_seen_run` توسط اجرای مسدود | F002 · **رد F006** · N02, N09 |
| `p_sap.py`    | OP-03 | PR item با چند PO item، انتساب PR/Material هدر، انباشت workflow، حفره `nullable_key` | F017, F018, F025, N06 |
| `p_status.py` | OP-04 | طبقه‌بندهای وضعیت فارسی، جمع چندارزی، تعهد تکراری، ادغام پرونده با متریال، ناپایداری شناسه پرونده، حذف observation تکراری | F004, F005, F007, F008, F009, N03, N08 |
| `p_gate.py`   | OP-05 | «آخرین PR» لغوی در چت‌بات، نشت اجرای مسدود، گیت خودغیرفعال‌شونده، نام فایل منبع | F001, F018, N07, N11 |
| `p_drift.py`  | OP-07a | حذف هدر منبع: ستون‌ها یکسان، مقدار خالی، drift فقط dtype را می‌بیند | N01 |
| `p_drift2.py` | OP-07b | تغییر نام هدر منبع: fingerprint یکسان و `SCHEMA_DRIFT` **پاس** | N01 |
| `p_reach.py`  | OP-06 | ممیزی مکانیکی producer/consumer روی `DERIVED` (۱۰ از ۱۰۴ بی‌تولیدکننده) | F021, N05 |

## هشدار تفسیر

ورودی‌ها synthetic‌اند. این probeها **وجود نقص روی ورودی مشخص** را اثبات می‌کنند، نه نرخ وقوع در داده تولید.

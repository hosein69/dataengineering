# داشبورد زنده GSI | Global Sourcing Intelligence

```bash
pip install streamlit plotly
python app/run_dashboard.py              # پورت آزاد را خودش پیدا می‌کند
python app/run_dashboard.py --port 8600  # پورت دلخواه
```

| فایل | نقش |
|---|---|
| `dashboard.py` | لایه نمایش Streamlit |
| `ui_kit.py` | منطق خالص — بدون Streamlit، کاملاً تست‌شده |
| `run_dashboard.py` | راه‌انداز با یافتن خودکار پورت |

## خروجی‌ها
- **اکسل کامل** — همان ۱۶ شیت گزارش
- **اکسل داده فیلترشده** — دقیقاً همان چیزی که روی صفحه می‌بینید
- **HTML مستقل** — CSS و JS درون‌خط، بدون وابستگی بیرونی، با دکمه «ذخیره به PDF»

## چرا منطق جداست
Streamlit در زمان import کد سطح-ماژول را اجرا می‌کند، پس `dashboard.py`
به‌تنهایی قابل تست خودکار نیست. هر چیزی که منطق است در `ui_kit.py` قرار
دارد و با `tests/test_dashboard.py` سنجیده می‌شود (۳۶ تست).


## Executive Email Pack

```bash
python -m gsi email --no-display
python -m gsi email
python -m gsi email --send
```

فایل رسمی Excel با نام `YYYY-MM-DD_Systemmatic Material.xlsx` داخل پوشه همان تاریخ ذخیره می‌شود. گیرندگان با `GSI_EMAIL_TO` قابل override هستند.

## GSI Studio — Modular Platform

Run:

```bash
python app/run_platform.py
```

Install `streamlit-sortables==0.3.1` for the drag-and-drop Layout Studio. The platform keeps the existing GSI Pipeline and Executive Email integration as the source of truth, while adding modular visual composition, live filtering, dynamic HTML/CSS/JS export, custom Excel export, and layout JSON export.

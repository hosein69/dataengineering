# Hotfix — Windows Temp Excel Handle

علت خطای `WinError 32` هنگام پایان خواندن سورس، باز ماندن handle مربوط به `pandas.ExcelFile/openpyxl` روی فایل موقت بود.

اصلاحات:
- `gsi/dataio/reader.py::read_sheet` اکنون `pd.ExcelFile` را با context manager باز می‌کند و قبل از cleanup پوشه موقت می‌بندد.
- مسیر `all_data_sheets` نیز workbook اکتشافی را به‌صورت قطعی می‌بندد.
- هیچ تغییری در منطق انتخاب شیت، تبدیل داده یا KPI ایجاد نشده است.
- هشدار openpyxl درباره Data Validation extension غیرمسدودکننده است و علت crash نبود.

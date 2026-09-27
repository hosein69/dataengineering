# GSI V27.1 — نمونه نصب/اجرای فضای شخصی بدون API/IP برای Data Access
# اجرای Installer یک‌بار روی سیستم کاربر: مسیر Share + Identity + User Key محلی ذخیره می‌شوند.
# روش پیشنهادی: User Key از فایل امن خوانده شود، نه از command line.

python tools\windows\install_gsi_personal_protocol.py `
  --employee 00123456 `
  --root "\\server\share\GSI\Users" `
  --user-key-file "C:\Secure\00123456.key"

# از این به بعد لازم نیست مسیر Share/کد پرسنلی را هر بار وارد کنید.
# داشبورد شخصی — داده فقط از Shared Store رمزگذاری‌شده
python -m gsi personal

# Live HTML محلی از همان Store
python -m gsi personal-open

# ایمیل‌های قدیمی/جدید می‌توانند به gsi://personal لینک بدهند.

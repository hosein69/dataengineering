# GSI V27.1 — Personal Shared Store

## هدف

این لایه برای این سناریو ساخته شده است: هر کاربر با کد پرسنلی خودش یک State پایدار و یک Snapshot عملیاتی اختصاصی در **پوشه مشترک شبکه** دارد. سیستم کاربر برای داده شخصی هیچ API، HTTP یا IP سازمانی را صدا نمی‌زند؛ فقط فایل‌های رمزگذاری‌شده همان فولدر را می‌خواند.

## ساختار فایل

```text
GSI_PROFILE_ROOT/
  00123456/
    state/
      profile.gsi      # قابل Read/Modify برای همان کاربر
    snapshot/
      current.gsi      # فقط Read برای کاربر؛ Writer = سیستم مرکزی
  00128743/
    state/profile.gsi
    snapshot/current.gsi
```

`profile.gsi` شامل Preference، Saved View و UI State است. `current.gsi` شامل آخرین داده scope‌شده همان کاربر است. هیچ‌کدام SQLite plaintext نیستند؛ SQLite در حافظه ساخته و سپس با AES-256-GCM به یک Blob رمزگذاری‌شده تبدیل می‌شود.

## اصل No Reset

باز و بسته شدن Streamlit، بستن Browser، دریافت ایمیل جدید و ارتقای GSI نباید Preferences را پاک کند. تنظیمات در `profile.gsi` می‌ماند و Data تازه مستقل در `current.gsi` جایگزین می‌شود. `current.gsi` هر بار Replace می‌شود، Merge نمی‌شود؛ بنابراین فیلدهای قدیمی بی‌صدا زنده نمی‌مانند.

## Identity بدون IP

هویت با این ترتیب resolve می‌شود:

1. `employee_code` صریح از برنامه مرکزی/HR؛
2. `GSI_EMP_CODE`؛
3. فایل محلی `%LOCALAPPDATA%\GSI\identity.json` (Windows).

IP، hostname و درخواست شبکه برای تشخیص کاربر استفاده نمی‌شود.

## کلیدها

سیستم مرکزی فقط `GSI_PROFILE_MASTER_KEY` یا `GSI_PROFILE_KEY_FILE` دارد. برای هر کد پرسنلی User Key مستقل با HKDF ساخته می‌شود. روی سیستم کاربر بهتر است فقط User Key همان شخص نصب شود:

```text
%LOCALAPPDATA%\GSI\profile.key
```

Master Key نباید روی سیستم کاربران و نباید داخل Shared Folder قرار بگیرد.

## Publish مرکزی

```powershell
$env:GSI_PROFILE_ROOT="\\server\share\GSI\Users"
$env:GSI_PROFILE_KEY_FILE="C:\Secure\gsi_master.key"
python -m gsi publish-personal
```

Publisher روی DataFrame اصلی `KEY_EMP` را Group می‌کند و فقط ردیف‌های هر فرد را در `snapshot/current.gsi` خودش می‌نویسد.

## User Key

روی سیستم مرکزی:

```powershell
$env:GSI_PROFILE_KEY_FILE="C:\Secure\gsi_master.key"
python -m gsi personal-key 00123456 > C:\Secure\00123456.key
```

کلید باید از یک کانال امن سازمانی تحویل شود؛ Email معمولی محل توزیع Key نیست.

## نصب Local Live View

روی سیستم کاربر پس از نصب Python/GSI:

```powershell
python tools\windows\install_gsi_personal_protocol.py --employee 00123456 `
  --root "\\server\share\GSI\Users" `
  --user-key-file "C:\Secure\00123456.key"
```

Installer فایل `personal_config.json` محلی را هم می‌سازد تا مسیر Share بین اجراها Reset نشود، یک `gsi_personal_launcher.py` محلی می‌سازد تا حتی بدون نصب pip مسیر همین پکیج GSI پیدا شود، و در HKCU پروتکل `gsi://personal` را ثبت می‌کند. Identity/User Key در `%LOCALAPPDATA%\GSI` قرار می‌گیرند و برای Key فایل ACL محلی best-effort محدود می‌شود. برای Production از `--user-key-file` استفاده کنید تا Key در command line و shell history ظاهر نشود.

سپس این دکمه در HTML/Email قابل استفاده است:

```html
<a href="gsi://personal">مشاهده وضعیت زنده</a>
```

کلیک روی آن یک Helper محلی اجرا می‌کند؛ Helper مستقیماً `profile.gsi + current.gsi` را از Share می‌خواند، HTML تازه را در Cache محلی می‌سازد و در Browser باز می‌کند. هیچ HTTP API برای Data Access استفاده نمی‌شود.

> محدودیت Outlook: برخی Policyهای سازمانی ممکن است Custom URI Scheme را مسدود کنند. در آن حالت Shortcut محلی `python -m gsi personal-open` همان کار را انجام می‌دهد. بدنه ایمیل Outlook خودش JavaScript فعال یا File-System Fetch قابل اتکا ندارد، بنابراین Live Refresh داخل خود Body ایمیل ادعا نمی‌شود.

## Streamlit شخصی

```powershell
$env:GSI_PROFILE_ROOT="\\server\share\GSI\Users"
$env:GSI_EMP_CODE="00123456"
$env:GSI_PROFILE_USER_KEY_FILE="$env:LOCALAPPDATA\GSI\profile.key"
python -m gsi personal
```

این Surface Pipeline مرکزی را اجرا نمی‌کند و به NTSW/Oracle/Customs وصل نمی‌شود؛ داده را فقط از Shared Store همان کاربر می‌خواند.

## ACL پیشنهادی

امنیت برنامه جای ACL شبکه را نمی‌گیرد. پیشنهاد:

- فولدر `00123456` فقط برای همان کاربر + سرویس مرکزی + Admin قابل مشاهده باشد.
- `state/` برای کاربر Modify باشد.
- `snapshot/` برای کاربر Read-only و برای سرویس مرکزی Modify باشد.
- Master Key فقط روی سیستم مرکزی، خارج از Share و با ACL محدود نگهداری شود.

App isolation + Encryption بدون ACL کافی نیست؛ ACL لایه اول، Per-user crypto لایه دوم است.

## Fail-Closed

- اگر Profile Root تنظیم نشده باشد: Personal Store اجرا نمی‌شود.
- اگر Key نباشد یا غلط باشد: داده به شکل plaintext fallback نمی‌شود.
- اگر Ciphertext دستکاری شود: AES-GCM خطای Integrity می‌دهد.
- اگر `KEY_EMP` وجود نداشته باشد: Publish متوقف می‌شود.
- اگر Central Publisher فقط User Key داشته باشد: Publish گروهی مجاز نیست؛ Master Key لازم است.


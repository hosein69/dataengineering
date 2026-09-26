# GSI V27.1.0 — Personal Shared Store / No Reset

این نسخه Persistence شخصی را از Browser/Session جدا می‌کند و به یک Store فایل‌محور، رمزگذاری‌شده و per-employee منتقل می‌کند.

## اضافه‌شده

- `gsi.personalization.store`: SQLite in-memory + AES-256-GCM + atomic write + lock.
- Per-user key derivation: Master Key مرکزی، User Key مستقل روی Client.
- `state/profile.gsi`: Preferences و UI state پایدار.
- `snapshot/current.gsi`: Data تازه و scope‌شده بر اساس `KEY_EMP`.
- `publish-personal`: ساخت Snapshotهای per-user از Pipeline مرکزی.
- `personal`: Streamlit محلی که فقط Shared Store را می‌خواند.
- `personal-html`: ساخت HTML از Shared Store.
- `personal-open`: بازسازی HTML تازه و بازکردن در Browser بدون HTTP/API data transport.
- Windows `gsi://personal` protocol installer برای Live View از Email/HTML.
- Personal email helper برای Outlook Draft از Store همان کاربر.
- 24 تست امنیت/Persistence/Isolation/Publisher/Live View/Installer Config.

## مرز امنیتی

فایل‌های User Data همیشه رمزگذاری‌شده‌اند. Master Key داخل Shared Folder قرار نمی‌گیرد. Client ترجیحاً فقط User Key خودش را دارد. ACL شبکه همچنان الزامی است: `state/` قابل Modify و `snapshot/` فقط Read برای کاربر.

## محدودیت آگاهانه

Outlook HTML قابل اتکا برای JavaScript/File-System Fetch نیست. بنابراین «Live» با Custom Local Protocol/Helper انجام می‌شود، نه با ادعای Refresh مستقیم داخل Email Body.

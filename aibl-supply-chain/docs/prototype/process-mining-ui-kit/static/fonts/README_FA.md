# فونت در محیط سازمانی

فونت طراحی زنده GSI **IRANSansWeb** است. این بسته هیچ فایل `.ttf/.otf/.woff/.woff2` توزیع نمی‌کند.

اگر سازمان مجوز IRANSansWeb دارد، فونت را روی Windows نصب کند یا فایل‌های مجاز را در محل داخلی خودش قرار دهد و `FontSource.LOCAL_STATIC` / `NETWORK_SHARE` را مطابق محیط تنظیم کند. نام‌های مورد انتظار برای حالت فایل محلی `IRANSansWeb-Regular.woff2`، `IRANSansWeb-Medium.woff2` و `IRANSansWeb-Bold.woff2` هستند.

در نبود فونت مجاز، CSS از fallbackهای نصب‌شده سیستم استفاده می‌کند. وجود نام فونت در CSS به معنای توزیع فایل فونت نیست.

# فونت‌های محلی (بدون اینترنت)

این پوشه محل فایل‌های فونت است که `pm_ui/theme.py` وقتی
`FontSource.LOCAL_STATIC` فعال باشد به آن‌ها ارجاع می‌دهد.

## چرا این‌جا خالی است

فایل فونت (`.woff2`) دارایی توزیع‌پذیر با مجوز جداگانه است و در مخزن کد
جای درستی ندارد. برای فعال‌سازی ظاهر لوکس IRANSans/Yekan Bakh:

1. فایل‌های زیر را (با همین نام‌ها) از منبع مجاز سازمانی خودتان این‌جا کپی کنید.
   «IRANSansWeb» اولویت اول است — دقیقاً همان فونتی که در فایل فیگمای
   دیزاین‌سیستم شما (GSI Foundations) استفاده شده؛ بقیه جایگزین‌اند:

   ```
   IRANSansWeb-Regular.woff2  IRANSansWeb-Bold.woff2
   IRANSansX-Regular.woff2    IRANSansX-Medium.woff2
   IRANSansX-Bold.woff2       IRANSansX-Black.woff2
   YekanBakh-Regular.woff2    YekanBakh-Medium.woff2
   YekanBakh-Bold.woff2       YekanBakh-Black.woff2
   ```

2. در `app.py`، خط زیر را:

   ```python
   theme.apply(font_source=theme.FontSource.SYSTEM_ONLY)
   ```

   به این تغییر دهید:

   ```python
   theme.apply(font_source=theme.FontSource.LOCAL_STATIC)
   ```

3. مطمئن شوید `enableStaticServing = true` در `.streamlit/config.toml`
   فعال است (پیش‌فرض همین پروژه همین‌طور است).

## اگر فونت‌ها روی یک شیر شبکهٔ داخلی هستند

به‌جای `LOCAL_STATIC` از `FontSource.NETWORK_SHARE` استفاده کنید و آدرس
پوشهٔ فونت روی شبکهٔ داخلی/اینترانت سازمانی را در `font_base_url` بدهید:

```python
theme.apply(font_source=theme.FontSource.NETWORK_SHARE,
            font_base_url="http://fonts.internal.company.local/fa")
```

## اگر هیچ‌کدام در دسترس نیست

هیچ اقدامی لازم نیست — پیش‌فرض `SYSTEM_ONLY` است و رابط با فونت‌های
از‌پیش‌نصب‌شدهٔ ویندوز سازمانی (Tahoma) به‌درستی و خوانا کار می‌کند؛ فقط
ظاهر IRANSans را ندارد.

> نکتهٔ مهم: خروجی HTML ایمیل (`pm_ui/export/html_report.py`) عمداً هرگز
> از `@font-face` استفاده نمی‌کند — اکثر کلاینت‌های ایمیل فونت وب را
> بارگذاری نمی‌کنند یا با تأخیر امنیتی مسدود می‌کنند.

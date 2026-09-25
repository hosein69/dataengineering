# فونت‌های محلی

## آن‌چه همین حالا کار می‌کند — Vazirmatn

`Vazirmatn-Variable.woff2` همین‌جا در مخزن است و **همیشه، بدون هیچ
تنظیمی** استفاده می‌شود (هم در Streamlit، هم در هر دو خروجی HTML). فونت
متن‌باز است (SIL Open Font License — نگاه کنید به `Vazirmatn-OFL.txt`
همین پوشه)، پس برخلاف IRANSans/Yekan Bakh، مجاز به توزیع در مخزن کد است.
این یعنی از همان اولین اجرا، بدون کپی‌کردن هیچ فایلی، ظاهر یک فونت فارسی
واقعی (نه Tahoma) را می‌بینید — چون Vazirmatn سومین اولویت در خواستهٔ
اولیهٔ فونت بود («اولیت iransans، بعد Yekan Bakh، سپس Vazirmatn»).

خروجی HTML مستقل (`pm_ui/export/standalone_html.py`) همین فایل را
به‌صورت base64 در خودِ سند جاسازی می‌کند — یک فایل خودبسنده که فونتش هم
همراهش می‌آید، نه وابسته به این‌که ماشین مقصد چه فونتی نصب دارد.

## اگر فایل مجوزدار IRANSansWeb/Yekan Bakh را دارید

این دو دارایی توزیع‌پذیر نیستند (مجوز جداگانه دارند) و در مخزن کد جای
درستی ندارند؛ ولی اگر از منبع مجاز سازمانی خودتان فایل واقعی را دارید،
اولویت اول می‌نشینند (جلوتر از Vazirmatn):

1. فایل‌های زیر را (با همین نام‌ها) این‌جا کپی کنید:

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

   > نکته: خروجی HTML مستقل هنوز فقط Vazirmatn را جاسازی می‌کند (نه
   > فایل‌های IRANSansWeb/Yekan Bakh که این‌جا اضافه می‌کنید) چون آن‌ها
   > مجوزدارند و نباید بدون اجازهٔ صریح در یک فایل توزیع‌شونده جاسازی
   > شوند؛ فقط خودِ Streamlit از آن‌ها استفاده می‌کند.

## اگر فونت‌ها روی یک شیر شبکهٔ داخلی هستند

به‌جای `LOCAL_STATIC` از `FontSource.NETWORK_SHARE` استفاده کنید و آدرس
پوشهٔ فونت روی شبکهٔ داخلی/اینترانت سازمانی را در `font_base_url` بدهید:

```python
theme.apply(font_source=theme.FontSource.NETWORK_SHARE,
            font_base_url="http://fonts.internal.company.local/fa")
```

> نکتهٔ مهم: خروجی HTML ایمیل (`pm_ui/export/html_report.py`) عمداً هرگز
> از `@font-face` استفاده نمی‌کند (نه Vazirmatn، نه هیچ‌چیز دیگر) —
> اکثر کلاینت‌های ایمیل فونت وب را بارگذاری نمی‌کنند یا با تأخیر امنیتی
> مسدود می‌کنند، پس آن یکی خروجی عمداً فقط به فونت سیستمی تکیه می‌کند.

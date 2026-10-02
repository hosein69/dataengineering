# وضعیت نهایی Figma و تطبیق رابط — ۲۰۲۶-۰۹-۲۵

در این Build اتصال زنده Figma بررسی شد؛ ادعای قدیمی «Figma قابل خواندن نبود» دیگر معتبر نیست.

## فایل‌های تأییدشده
- `oMZKwzm97e65g7nQWnUog8` — فریم `2:43`، الگوی مالی/شواهد RTL.
- `Abh0S2zpkk25P7HTNdpipa` — فریم `1:152`، Cover/Vision.
- `T9Ps72EYpriHdov9fmNFQu` — فریم `3:2`، **GSI Foundations و منبع حقیقت Design System**.

## فونت
بازخوانی زنده Text nodeها:
- صفحه مالی: ۲۷/۲۷ متن با IRANSansWeb.
- Cover: ۱۱/۱۱ متن با IRANSansWeb.
- Foundations: ۲۰۳/۲۰۳ متن با IRANSansWeb.

وزن‌های مورد استفاده Regular/Medium/Bold و letter-spacing فارسی صفر است. کد این Build نیز IRANSansWeb را در اولویت Typography قرار می‌دهد. **هیچ فایل فونت باینری داخل بسته توزیع نمی‌شود**؛ سازمان باید فایل/نصب مجاز IRANSansWeb را خودش تأمین کند. در نبود آن، CSS به fallbackهای سیستم می‌رود.

## توکن‌های همگام‌شده
- Page: `#F6F8F9`
- Raised: `#FFFFFF`
- Sunken: `#EEF2F4`
- Navy/Data & Trust: `#0B1F33`
- Teal/Process & Flow: `#0A7C86`
- Gold/Decision surface: `#C79A4A`
- Text Teal: `#076670`
- Text Gold: `#7A5A15`
- Radius: 0 / 6 / 10 / 14 / 20 / pill
- Spacing: 0, 2, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64

Typography ramp با Foundations همگام است: Display 32/700/1.35، H1 25/700/1.4، H2 20/700/1.45، H3 17/700/1.5، H4 15/700/1.55، body-lg 14/400/1.75، body 13/400/1.75، small 12/400/1.65، caption 11/400/1.55، overline 11/700/1.4، metric 26/700/1.2 و metric-sm 19/700/1.25.

## معماری صفحه عملیاتی
تصمیم تثبیت‌شده سه View است و در Export جدید نیز همین ساختار رعایت شده:
1. **وضعیت و اقدام** — آخرین Activity، وضعیت مشاهده‌شده، Owner، کیفیت شاهد، Next Action و زمان مشاهده؛ نبود فیلد صریح با «مشاهده نشده» نمایش داده می‌شود.
2. **مسیر فرآیند** — نمودار + جدول مبدأ/مقصد؛ Unique Case و Occurrence جدا؛ Median/P90 فاصله Eventها با واحد ساعت.
3. **تحویل بین واحدها** — فقط از from_team/to_team صریح؛ اگر قرارداد منبع وجود نداشته باشد «قابل محاسبه نیست» و صفر جعل نمی‌شود.

Gold برای توجه/تصمیم محدود است و وضعیت فقط با رنگ منتقل نمی‌شود. شبکه تحلیلی پیچیده جایگزین نمای ساده پیش‌فرض نشده است.

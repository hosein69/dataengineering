# خروجی نهایی Diagram / Flowchart / EFD — GSI

تاریخ: ۲۰۲۶-۰۹-۲۵

این پوشه مستقیماً بر مبنای تصمیم‌های تثبیت‌شده GSI ساخته شده و سه افزونه درخواستی کاربر در آن به‌کار رفته‌اند:

- **Diagram Maker**: معماری سیستم و Process Map با تفکیک منبع، Snapshot، Quality Gate، Process Intelligence، Pattern Observation و خروجی/انتشار.
- **Flowchart Maker**: Swimlane عملیاتی با تصمیم‌ها، مسیر Fail-closed، فعال/غیرفعال بودن Pattern config و انتشار شبکه.
- **EW AI Flowchart**: مدل مهندسی `EFD 2.1` با ID پایدار، Stage، Organization Unit، Position/System Actor، RACI، Layout و Draw.io mapping.

## فایل‌ها

- `GSI_FINAL_ARCHITECTURE.mmd` + `.dot` + `.svg`
- `GSI_FINAL_PROCESS_SWIMLANE.mmd` + `.dot` + `.svg`
- `GSI_PATTERN_OBSERVATION_FLOW.mmd` + `.dot` + `.svg`
- `../efd/GSI_FINAL_OPERATING_MODEL.efd.json`
- `../efd/GSI_FINAL_OPERATING_MODEL_VALIDATION.json`

## مرزهای حقیقت

1. Diagramها از کد و قرارداد فعلی محصول ساخته شده‌اند؛ شاخص عملکرد یا ساختار سازمانی جدیدی اختراع نشده است.
2. Pattern Observation فقط مشاهده است و به Risk/SLA/Violation/Action خودکار تبدیل نمی‌شود.
3. نام رسمی واحدها و عناوین شغلی بهره‌برداری/حاکمیت در منابع تثبیت نشده‌اند؛ در EFD با متن صریح «تعیین در استقرار» و RACI `pending` نگه داشته شده‌اند.
4. EFD مدل جریان نرم‌افزار و انتشار است، نه جایگزین مدل فرآیند تجارت خارجی واقعی سازمان.
5. فونت طراحی `IRANSansWeb` در مشخصات Diagram/EFD آمده اما هیچ فایل باینری فونت در بسته توزیع نشده است.

## نتیجه اعتبارسنجی EFD

- ساختار و قرارداد مرجع EFD 2.1: **PASS**
- Stable ID uniqueness: **PASS**
- Reference integrity: **PASS**
- Start/End + reachability: **PASS**
- Decision outcomes: **PASS**
- Layout/Draw.io mapping coverage: **PASS**
- خطای ساختاری: **0**
- Warningهای باقیمانده: فقط نام رسمی واحد/عنوان مسئول انسانی که باید در استقرار تأیید شود.

نکته: skill نصب‌شده به `scripts/validate_efd_json.py` اشاره می‌کند، اما آن script در resource catalog در دسترس نبود؛ بنابراین validation معادل و deterministic روی همان Contract/Schema انجام و نتیجه داخل بسته ثبت شده است.

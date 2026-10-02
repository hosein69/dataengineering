# نقشهٔ سورس‌ها — GSI 29.7.9 RC3

دامنهٔ این نسخه فقط ناسازگاری‌های مستند در evidence.txt و بررسی پچ تازهٔ کاربر است. بازطراحی تازهٔ UI، تغییر استک یا افزودن عامل یادگیرنده انجام نشده است.

نقشه شامل ۱۴ نام منبع، ۴۱ شیت، آمار ۶۳۱٬۵۷۶ ردیف و ۱٬۰۸۹ ردیف نمونه است. ۶۳۱٬۵۷۶ ردیف واقعی در اختیار نیست. errors=[] نتیجهٔ اجرای پروفایلر است، نه گواه صحت مالی. نسخهٔ تستی پیوست تنها نشانی‌های تماس را حذف کرده است؛ هش فایل اصلی در SOURCE_COVERAGE.json ثبت است.

| پروفایل | منبع / شیت | ردیف اعلام‌شده | نمونه | مقصد و تصمیم |
|---|---|---:|---:|---|
| 0 | SAP / pr | 17029 | 30 | sap / pr_items — native independent grain; no wide cross-join |
| 1 | SAP / pack | 9141 | 30 | sap / workflow_rows — native independent grain; no wide cross-join |
| 2 | SAP / po | 69608 | 30 | sap / po_items — native independent grain; no wide cross-join |
| 3 | SAP / inbound | 50301 | 30 | sap / inbound_deliveries — native independent grain; no wide cross-join |
| 4 | SAP / GR | 380909 | 30 | sap / goods_receipts — native independent grain; no wide cross-join |
| 5 | Commercial_Expert / Expert Data | 7483 | 30 | moghavemat / lines/inventory/order_material_pr_item — existing contract, sample transformed |
| 6 | Oracle / 1 | 1415 | 30 | oracle / main — existing non-additive cross-sheet resolution; source owner still needed for within-sheet inventory aggregation |
| 7 | Oracle / SAPCO_IK | 418 | 30 | oracle / main — existing non-additive cross-sheet resolution; source owner still needed for within-sheet inventory aggregation |
| 8 | NTSW / Import License | 2403 | 30 | ntsw / import_license — status/identity retained; request and commitment grains remain separate |
| 9 | NTSW / Allocation | 4755 | 30 | ntsw / allocation_rows — status/identity retained; request and commitment grains remain separate |
| 10 | NTSW / Release Commitment | 4859 | 30 | ntsw / commitment_rows — status/identity retained; request and commitment grains remain separate |
| 11 | NTSW / Quota | 978 | 30 | ntsw / raw/staging — archived and staged only; quota/declaration/assistant not promoted into financial totals without approved contracts |
| 12 | NTSW / Overall Quota | 8 | 8 | ntsw / raw/staging — archived and staged only; quota/declaration/assistant not promoted into financial totals without approved contracts |
| 13 | NTSW / Quota Season | 8 | 8 | ntsw / raw/staging — archived and staged only; quota/declaration/assistant not promoted into financial totals without approved contracts |
| 14 | NTSW / Custom Declaration | 1000 | 30 | ntsw / raw/staging — archived and staged only; quota/declaration/assistant not promoted into financial totals without approved contracts |
| 15 | NTSW / Assistant | 3634 | 30 | ntsw / raw/staging — archived and staged only; quota/declaration/assistant not promoted into financial totals without approved contracts |
| 16 | IL_Append / Append | 2884 | 30 | ilappend / main — status and amendment identity retained; no latest amendment inferred |
| 17 | Abbasi / DATES | 40151 | 30 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 18 | Abbasi / BLs Tracking | 7402 | 30 | abbasi / main — existing contracted operational sheet |
| 19 | Abbasi / FP | 196 | 30 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 20 | Abbasi / HDM-33  | 24 | 24 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 21 | Abbasi / HDM-34 | 24 | 24 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 22 | Abbasi / HDM-35 | 25 | 25 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 23 | Abbasi / HDM-36 | 25 | 25 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 24 | Abbasi / HDM-37 | 25 | 25 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 25 | Abbasi / HDM-38 | 24 | 24 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 26 | Abbasi / Data | 4 | 4 | abbasi / raw archive only — calendar/lookup/forecast/form sheet; not another BL transaction ledger |
| 27 | SATA / Sata Tracking | 6199 | 30 | sata / main — existing contracted operational sheet |
| 28 | SATA / Data | 13 | 13 | sata / raw archive only — lookup table |
| 29 | FX_Transactions_1405 / گزارش اخذ سوئيفت | 31 | 30 | fx_transaction / raw archive only — summary report; not a purchase ledger |
| 30 | FX_Transactions_1405 / خريد جاري1405 | 513 | 30 | fx_transaction / main/quarantine — both exact filenames discovered; layouts mapped separately; no proforma or SWIFT currency substituted for purchase currency |
| 31 | FX_Transactions / Sheet1 | 1743 | 30 | fx_transaction / main/quarantine — both exact filenames discovered; layouts mapped separately; no proforma or SWIFT currency substituted for purchase currency |
| 32 | Sea_Clearance / Sea Clearance | 1633 | 30 | clearance / main — all operational sheets by header contract; canonical mapping before union |
| 33 | Sea_Clearance / Sheet2 | 23 | 23 | clearance / raw archive only — lookup table |
| 34 | Land_Clearance / Land Clearance | 923 | 30 | clearance / main — all operational sheets by header contract; canonical mapping before union |
| 35 | Land_Clearance / Data | 23 | 23 | clearance / raw archive only — lookup table |
| 36 | Air_Clearance / Air Clearance | 3424 | 30 | clearance / main — all operational sheets by header contract; canonical mapping before union |
| 37 | Air_Clearance / data | 23 | 23 | clearance / raw archive only — lookup table |
| 38 | Customs / Cottage Tracking | 7037 | 30 | cotage / main — existing contracted operational sheet |
| 39 | Customs / Data | 198 | 30 | cotage / raw archive only — lookup table |
| 40 | Credit_Dept / PURCREDIT | 5060 | 30 | credit / main — allocation/SWIFT amount and currency distinct; proforma rial equivalent is not funding cash |

## تغییرات قابل ردیابی

1. پروفایل‌های ۰ تا ۴: SAP پنج‌شیتی و مسیر GS_Full Chain، همراه حفظ سازگاری Data. PR، PO، بسته، تحویل و حرکت کالا در دانه‌های جدا هستند. شیت‌های جدید به‌صورت شاهد native در DWH و مسیر عمومی شواهد فرایندی حفظ می‌شوند؛ برای آن‌ها مرحلهٔ فرایندی یا KPI تازه اختراع نشده است.
2. پروفایل ۲: Our Reference مختلط است؛ نمونه 6100000380 به سفارش ارتقا نمی‌یابد. مقدار در SAP_ORDER_REFERENCE_CANDIDATE حفظ می‌شود. وجود کد در ستون مشترک، قرارداد قطعی نوع شناسه نیست.
3. پروفایل ۴: برگشت 122 با مقدار منفی، منفی می‌ماند. مراحل BLOCKED_RECEIPT و BLOCKED_RELEASE جدا ثبت می‌شوند؛ مقدار علامت‌دار، جمع عمومی موجودی نیست. انواع حرکت بدون قرارداد معتبر ناشناخته می‌مانند. کلید سال مالی سند و جامعیت شناسه حرکت هنوز نیازمند قرارداد تولیدی است.
4. پروفایل‌های ۳۰ و ۳۱: هر دو فایل خرید ارز با نام دقیق کشف می‌شوند؛ شیت‌ها پیش از اتحاد جدا نگاشت می‌شوند. ارز پروفرما، خرید و سوئیفت جداست؛ نوع ارز.1 در فایل قدیمی می‌تواند «حواله» باشد و ارز سوئیفت فرض نمی‌شود. داده خام هر دو فایل محفوظ است؛ یکتایی رویداد مشترک بین نسخه‌ها بدون شناسه واقعی تضمین نشده است.
5. پروفایل ۴۰: مبلغ دریافت سوئیفت و ارز6 و مبلغ تخصیص و ارز5 حفظ شدند؛ ارز خالی با ارز پروفرما پر نمی‌شود. تاریخ تأمین وجه شاهد مرحله است، ولی معادل ریالی پروفرما رویداد نقدی نیست.
6. پروفایل‌های ۸، ۹ و ۱۶: وضعیت/تاریخ مجوز به مصرف‌کننده فرایند می‌رسد؛ درخواست ردشده با تاریخ تاریخی به تخصیص قطعی تبدیل نمی‌شود؛ وضعیت و شناسه/تاریخ اصلاحیه IL حفظ می‌شود.
7. پروفایل‌های ۳۲، ۳۴ و ۳۶: انتخاب بزرگ‌ترین شیت کنار گذاشته شد؛ تمام شیت‌های دارای «بارنامه» و «پرونده ترخیص» خوانده و قبل از concat نگاشت می‌شوند. lookupها وارد تراکنش‌ها نمی‌شوند.
8. پچ تازه: scope مجموع تعهد پذیرفته و اصلاح شد. اجرای صریح فاقد فایل به اجرای دیگری گسترش نمی‌یابد؛ بدون انتشار، مجموع پیش‌فرض خالی است. coverage و chain قدیمی هنوز تمام آرشیو را می‌بینند؛ F023 کاملاً بسته نیست.

## نقش‌های بازبینی

این نقش‌ها زاویه‌های ارزیابی یک بازبینی هستند، نه ادعای تأیید چند تیم مستقل.

| نقش | نتیجه در دامنهٔ نقشه |
|---|---|
| Architecture Owner | حفظ استک و مرز native source؛ رد ورود عامل یادگیرنده به مرجع مالی |
| Principal Data Architect | تفکیک REG_FILE، REG، ORDER، PO، PR و مرجع نامشخص |
| Senior Data Warehouse Engineer | scope نسخهٔ منتشرشده، حفظ شواهد native و ثبت پوشش ۴۱ شیت |
| Senior Python Backend Engineer | تطبیق پچ‌ها و سازگاری شیت Data با قالب native |
| Process Intelligence Architect | وضعیت و تاریخ شاهد؛ عدم ساخت مرحله از مبلغ پروفرما یا درخواست ردشده |
| BI Architect | منع جمع عمومی مراحل حرکت کالا و ارزهای مختلف |
| Data Quality Engineer | تست با نمونه واقعی، تعارض هدر و نبود قرارداد صریح |
| Cash Flow / FX Logic Reviewer | علامت برگشت، تفکیک ارز خرید/سوئیفت/پروفرما و عدم اختراع تأمین وجه |
| Semantic Chatbot Architect | استفاده از شواهد موجود؛ بدون تبدیل درس مدل به واقعیت مالی |
| Senior Full-Stack Reviewer | رابط عمومی adapterها و مصرف‌کنندگان موجود حفظ شد |
| UI/UX Technical Reviewer | دامنهٔ جدید تغییر ظاهری ندارد؛ نمایش نامعلوم و منبع از RC2 حفظ شد |

## حدود تأیید

تطبیق نمونه‌ها جای اجرای ۱۷ فایل تولیدی با تمام ردیف‌ها و فرمول‌ها را نمی‌گیرد. Quotaها، کارتابل Assistant و بعضی فرم‌ها فقط raw/staging هستند؛ ادعای پوشش محاسباتی تمام ستون‌ها نمی‌کنیم. مشکلات باز F031، F037، N08، RC03، F019/N04 و سیاست رویداد/نسخه و تاریخ مشاهده باقی‌اند. این نسخه برای بازبینی است.

## تکمیل کنترل مصرف‌کنندگان

تست سرتاسری رابطهٔ PO↔BL نشان داد شیت inbound پچ تازه وارد raw_rows نمی‌شد و DWH فقط از raw_rows رابطه می‌ساخت. اکنون inbound و GR نیز در raw_rows حفظ می‌شوند؛ رابطه‌های مستقیم PO↔BL و PO↔REG_FILE با شاهد همان ردیف ثبت می‌شوند. هیچ join از Our Reference نامشخص ساخته نمی‌شود.

وضعیت «دربرنامه خرید» از رویداد خرید انجام‌شده در کش‌فلو و مصرف‌کنندگان فرایند/رویداد جدا شد. در مراحل قدیمی ۵۵ و ۵۶ هم مبلغ تأمین وجه نامعلوم می‌ماند و مبلغ/ارز سوئیفت از CRD_SWIFT_AMOUNT/CURRENCY می‌آید؛ معادل یورویی پروفرما دیگر سوئیفت فرض نمی‌شود. سایر خلاصه‌های legacy خارج از این اصلاح محدود همچنان مشمول محدودیت F031 هستند.

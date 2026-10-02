# GSI V29.6.0 — End-to-End Money Flow Reconciliation

## هدف
بستن جریان پول از ثبت سفارش تا رفع تعهد با حفظ Evidence و بدون فرض صفر برای داده مفقود.

## تغییرات اصلی
- `fx_money_ledger`: دفتر کل رویداد-محور در سطح REG برای ارزش ثبت سفارش/پروفرم، درخواست تخصیص، تخصیص، خرید ارز، تامین وجه ریالی، سوئیفت، پرداخت به ذی‌نفع، تعهد اولیه، مبلغ رفع‌شده و مانده تعهد.
- `fx_money_reconciliation`: تطبیق فقط داخل همان ارز؛ جمع بین‌ارزی ممنوع است.
- تفکیک `SWIFT` از `SUPPLIER_PAYMENT` و استفاده از `FX_RECEIPT_DATE` به‌عنوان شاهد مستقل وصول در صورت وجود.
- کنترل معادله تعهد: `Initial = Released + Balance` و تولید `OBLIGATION_RECON_STATUS`.
- وضعیت‌های تطبیق: `RECONCILED`, `OPEN_AMOUNT_GAP`, `EVIDENCE_GAP`, `ACCOUNTING_MISMATCH`.
- اضافه شدن خروجی‌های `FX_MONEY_RECON_STATUS`, `FX_MONEY_EVIDENCE_GAPS`, `FX_OBLIGATION_RECON_STATUS` به سطح پرونده.
- Export دو جدول جدید در Report Builder و شیت FX داشبورد: «دفتر کل صفر تا صد پول» و «تطبیق مبالغ و تعهد».
- عنوان مرحله سوئیفت به «سوئیفت / تبدیل / وصول ذی‌نفع» ارتقا یافت بدون تغییر تعداد 11 مرحله برای سازگاری.

## اصول کنترلی
- Missing ≠ Zero.
- SWIFT ≠ Supplier Receipt.
- اختلاف درخواست/تخصیص/خرید/پرداخت الزاماً خطا نیست و به‌صورت `OPEN_AMOUNT_GAP` گزارش می‌شود.
- فقط شکست معادله حسابی تعهد `ACCOUNTING_MISMATCH` است.
- ارزهای متفاوت بدون پل نرخ صریح با هم reconcile نمی‌شوند.

## Regression
- تست جدید `tests/test_money_flow_v29_6.py`.
- 12/12 تست مستقیم جریان پول/FX (V29.6 + V26.18 + V26.16) موفق.
- تست‌های متریال V29.5 نیز جداگانه حفظ شده‌اند.
- اجرای خام `pytest` کل repository: 279 passed؛ 1 failure و 6 fixture errors قدیمی/نامرتبط با این تغییر مشاهده شد (AnythingLLM offline text assertion و تست‌هایی که fixtureهای res/df ندارند).

# Business Key & Grain Map — V29

## قانون پایه

هیچ «کلید عمومی» برای کل زنجیره وجود ندارد. کلید تابع grain هر Fact است.

| حوزه | Grain / کلید اصلی | توضیح |
|---|---|---|
| Supply Position | `ORDER + MATERIAL` | snapshot کارشناسی؛ duplicate line نباید sum شود |
| Oracle | `MATERIAL` | موجودی/نیاز روزانه material-level |
| NTSW Import Licence | `REG_FILE + REG` به‌عنوان evidence | Hub اتصال پرونده ثبت سفارش و کد ثبت سفارش |
| IL Append | `REG_FILE + REG (+ ORDER اگر موجود)` | شاهد مستقیم اتصال به بیزینس |
| NTSW Allocation | `REQUEST_KEY` | هر درخواست یک بار در ledger؛ retry history دوباره‌شماری نمی‌شود |
| NTSW Commitment | `REG` در summary | ردیف‌های تعهد خام چندتایی‌اند و summary جمع کنترل‌شده است |
| SAP current | `PR` | آخرین snapshot workflow؛ history باید fact جدا باشد |
| Event Log | `CASE + ACTIVITY + TIMESTAMP + discriminator` | event تکراری نباید دو بار شمرده شود |

## Direct Evidence Bridges

فقط وقتی دو کلید معتبر در **همان ردیف شاهد** باشند bridge ساخته می‌شود:

- Order ↔ Material
- Order ↔ PR
- PR ↔ Material
- Order ↔ BL
- BL ↔ REG
- Order ↔ REG
- REG_FILE ↔ REG
- REG_FILE ↔ Order
- Order ↔ Employee

رابطه ترانزیتی فقط هنگام query resolve می‌شود. مثال:

`Allocation(REG) -> Import Licence(REG, REG_FILE) -> IL(REG_FILE, ORDER) -> Order`

این مسیر در Graph قابل پیمایش است ولی `Allocation -> Order` به‌عنوان شاهد مستقیم ذخیره نمی‌شود.

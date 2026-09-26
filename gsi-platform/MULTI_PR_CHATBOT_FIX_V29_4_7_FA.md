# GSI V29.4.7 — Multi-PR Lineage + Chatbot Visibility

## Commercial Expert Data
- Supply Position همچنان در Grain صحیح `Order × Material` باقی می‌ماند.
- یک Frame مستقل `order_material_pr_item` اضافه شد با Grain `Order × Material × PR × PR Item`.
- ردیف‌های تکراری همان رابطه حذف نمی‌شوند؛ به `MOGH_EVIDENCE_COUNT` و `MOGH_SOURCE_ROWS` تبدیل می‌شوند.
- در سطح سفارش `MOGH_PR_COUNT`, `MOGH_PRS_ALL`, `MOGH_PR_ITEMS_ALL`, `MOGH_MULTI_PR` اضافه شد.
- DWH جدول `dwh_bridge_order_material_pr_item` دارد تا PR دوم/سوم در تجمیع سفارش گم نشود.

### نمونه واقعی قفل‌شده در Regression Test
- Order `843115`, Material `9654003280` دو PR مستقل `6100002273` و `6100002723` دارد.
- Order `843120`, Material `9654003280`, PR `6100002854`, Item `20` دو ردیف Raw (169 و 170) دارد؛ Bridge یک رابطه با `evidence_count=2` نگه می‌دارد.

## Chatbot
- عبارت «آموزش هفتگی» از UI اصلی حذف شد؛ نام بخش فقط «چت‌بات» است.
- چت‌بات دیگر به وجود فایل محتوای تکمیلی وابسته نیست.
- علت باگ نمایش‌ندادن: `html_export` کل Chat UI را داخل شرط `learning_lesson` رندر می‌کرد. این coupling حذف شد.
- اگر مسیر محتوای اختیاری خالی باشد، دیگر `Path("")` باعث scan شدن کل working directory نمی‌شود.
- Sidecar جدید `chatbot_content.json` ساخته می‌شود؛ `weekly_lessons.json` فقط برای backward compatibility باقی مانده و user-facing نیست.

## اصول
- Raw evidence حفظ می‌شود.
- Aggregation نباید relationship را نابود کند.
- Chatbot مستقل از optional curated content است.

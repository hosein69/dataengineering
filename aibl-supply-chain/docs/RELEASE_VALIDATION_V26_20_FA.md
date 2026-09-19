# گزارش اعتبارسنجی Release — GSI V26.20

**تاریخ:** 2026-09-17  
**نسخه:** 26.20.0

## نتیجه
**Release candidate برای Controlled Pilot / UAT آماده است.**

## شناسنامه زنده
خروجی `python -m gsi.factsheet`:
- Rule packs: 12
- YAML rule files: 13
- Rules needing verification: 19
- Adapters/sources: 13 / 13
- Pipeline stages: 16
- Dashboard sheets: 17
- Python package files: 90
- Test files: 20

## تست‌ها
۲۰ مجموعه تست به‌صورت مستقل پس از آخرین تغییرات اجرا شدند:

| # | Suite | Passed | Failed |
|---:|---|---:|---:|
| 1 | validation | 61 | 0 |
| 2 | rules_and_moghavemat | 63 | 0 |
| 3 | criticality | 34 | 0 |
| 4 | architecture | 36 | 0 |
| 5 | contracts_report | 14 | 0 |
| 6 | dashboard | 77 | 0 |
| 7 | import_hygiene | 19 | 0 |
| 8 | doc_claims | 8 | 0 |
| 9 | email_report | 11 | 0 |
| 10 | studio | 5 | 0 |
| 11 | report_builder | 32 | 0 |
| 12 | supply_views | 55 | 0 |
| 13 | system_health | 49 | 0 |
| 14 | oracle_multisheet | 1 | 0 |
| 15 | studio_v26_12 | 2 | 0 |
| 16 | html_export_v26_15 | 1 | 0 |
| 17 | fx_traceability_v26_16 | 5 | 0 |
| 18 | money_flow_v26_18 | 13 | 0 |
| 19 | legacy_knowledge_v26_19 | 16 | 0 |
| 20 | v26_20_case_action_inventory | 15 | 0 |
| **Total** |  | **517** | **0** |

Runner یک‌تکه در این محیط به‌دلیل مدت اجرای مجموعه‌های سنگین Dashboard به timeout ابزار خورد؛ تا نقطه timeout همه suiteهای اجراشده سبز بودند. برای اجتناب از گزارش نادرست، عدد 517/0 بر مبنای اجرای مستقل تمام 20 suite است.

## RuleBook
`python -m gsi.rulebook.validate`:
- Structural errors: **0**
- Needs verification: **19**

این 19 مورد عمداً Fail-Closed هستند و نباید بدون اصل/نسخه جاری بخشنامه، deadline یا finding قطعی بسازند.

## Manifest / Doctor
Manifest پس از آخرین تغییرات بازتولید شد:
- **105 tracked files**

`python -m gsi.doctor`:
- Errors: **0**
- Warnings: **8**

هشدارها:
- 6 Share سازمانی از این runtime در دسترس نیست؛
- `jdatetime` اختیاری نصب نیست و مبدل داخلی وجود دارد؛
- 19 Rule نیازمند تطبیق رسمی‌اند.

## کنترل‌های V26.20 که تست شده‌اند
- Unknown inventory != zero.
- Expert supplier/in-transit/customs + Oracle IKCO/SAPCO five-component formula.
- Lower-bound/coverage on missing data.
- NTSW request history deduplication.
- Open vs allocated amounts separated.
- Partial allocation remains visibly in queue.
- Queue rank not fabricated.
- Clearance / Bank Docs / Settlement separated.
- Case action human review required.
- Outlook email defaults to draft.
- GSI package identity and absence of active `aibl` package.

## نتیجه UAT موردنیاز داخل شبکه
1. تأیید نام واقعی سه ستون موجودی کارشناسان و grain آن‌ها.
2. تأیید request identifiers/status values واقعی NTSW Allocation export.
3. تأیید Evidence فیلد ارائه/تطبیق سند گمرکی نزد بانک.
4. تأیید recipient/owner resolution از HR.
5. نمونه‌گیری دستی از حداقل 20 REG شامل partial allocation، cross-currency، multiple BL، clearance-without-SATA و open commitment.

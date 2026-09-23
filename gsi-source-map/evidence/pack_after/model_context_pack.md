# GSI Model Context Evidence Pack

Generated: 2026-09-23T08:20:23 · tool `2.0.0-reviewed`
Config: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/sources_fixed.yaml`

## Source coverage

| Source | Status | Frames | Rows | Detail |
| --- | --- | --- | --- | --- |
| SAP | PROFILED | 1 | 3 |  |
| Commercial_Expert | PROFILED | 1 | 2 |  |
| NTSW | PROFILED | 3 | 6 |  |
| Oracle | PROFILED | 1 | 1 |  |
| FX_Transactions | PROFILED | 1 | 1 |  |
| Customs | PROFILED | 1 | 1 |  |

## Interpretation rules

- Samples maximise process/key/status coverage; they are not statistical samples.
- Grain and relation findings are heuristic unless confirmed by contracts or code.
- Co-observed keys are not automatically authoritative joins.
- Missing evidence must not be read as proof that a process step did not occur.
- A column carrying a date, amount, quantity, currency or status is never treated as a business key.
- Persian/Arabic spellings and digits are folded for counting only; every value printed is the raw source value.

## Cross-source key map

_Representative key column per role per frame. Secondary columns that share a role are listed in `process_key_index.json` under `secondary_role_columns` and are deliberately kept out of the join map._

| Role | Frames | Sources | Columns |
| --- | --- | --- | --- |
| BL | 3 | Commercial_Expert, Customs, FX_Transactions | Commercial_Expert/Expert Data: BL No.; FX_Transactions/Sheet1: شماره بارنامه; Customs/SeaClearance: شماره بارنامه |
| COMPARISON | 1 | SAP | SAP/Data: Comparision ID |
| COTTAGE | 1 | Customs | Customs/SeaClearance: کوتاژ |
| CUSTOMS_FILE | 1 | Customs | Customs/SeaClearance: پرونده ترخیص |
| MATERIAL | 3 | Commercial_Expert, Oracle, SAP | SAP/Data: Material; Commercial_Expert/Expert Data: Material; Oracle/Total_Report 14050610: شماره فنی |
| NATIVE_ROW_ID | 2 | NTSW | NTSW/Release Commitment: شماره ردیف تعهد; NTSW/Allocation: ردیف درخواست |
| ORDER | 4 | Commercial_Expert, Customs, FX_Transactions, NTSW | Commercial_Expert/Expert Data: Order No. (Our Reference); NTSW/Import Licence: شماره سفارش; FX_Transactions/Sheet1: شماره سفارش; Customs/SeaClearance: شماره سفارش |
| PO | 1 | SAP | SAP/Data: Purchase order |
| PO_ITEM | 1 | SAP | SAP/Data: po.Item |
| PR | 2 | Commercial_Expert, SAP | SAP/Data: Purchase Requisition; Commercial_Expert/Expert Data: Purchase Requisition |
| PR_ITEM | 2 | Commercial_Expert, SAP | SAP/Data: Item of requisition; Commercial_Expert/Expert Data: Item of requisition |
| REG | 4 | FX_Transactions, NTSW | NTSW/Import Licence: کد ثبت سفارش; NTSW/Release Commitment: کد ثبت سفارش; NTSW/Allocation: کد ثبت سفارش; FX_Transactions/Sheet1: ثبت سفارش |
| REG_FILE | 1 | NTSW | NTSW/Import Licence: شماره پرونده ثبت سفارش |
| SUPPLIER | 1 | SAP | SAP/Data: po.Supplier |
| WORKFLOW | 1 | SAP | SAP/Data: WorkFlow ID |

## ⚠️ Same-role key conflicts

_Two columns claim the same role but disagree on the same native row. Treating them as one key fabricates lineage._

| Frame | Role | A | B | Rows both | Disagree |
| --- | --- | --- | --- | --- | --- |
| SAP/Data | PR_ITEM | Item of requisition (header) | po.Item of requisition (po) | 2 | 1 (50.0%) |
| SAP/Data | PR | Purchase Requisition (header) | po.Purchase Requisition (po) | 2 | 1 (50.0%) |
| SAP/Data | MATERIAL | Material (header) | po.Material (po) | 2 | 1 (50.0%) |

---
## Source: SAP / Sheet: Data

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/SAP.xlsx`
- Domain: `Planning / Procurement`
- Authority: `Domain evidence`
- Rows: **3**
- Columns: **28**
- Sample: `samples/SAP__Data__sample.csv`

### Grain candidate
`PO_ITEM` on `Purchase order, po.Item` — uniqueness `1.0`, coverage `0.6667`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| COMPARISON | Comparision ID | header |
| MATERIAL | Material | header |
| PO | Purchase order | header |
| PO_ITEM | po.Item | po |
| PR | Purchase Requisition | header |
| PR_ITEM | Item of requisition | header |
| SUPPLIER | po.Supplier | po |
| WORKFLOW | WorkFlow ID | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| Processing status | مورد تایید | 1 |  |
| Processing status | تایید نشده | 1 |  |
| Processing status | در گردش | 1 |  |
| Deletion Indicator | X | 1 |  |
| WorkFlow Status | RELEASED | 2 |  |
| WorkFlow Status | IN PROCESS | 1 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| PR (Purchase Requisition) | PO (Purchase order) | 1:N | 2 | 2 | yes |
| PR (Purchase Requisition) | PO (po.Purchasing Document) | 1:N | 2 | 2 |  |
| PR (po.Purchase Requisition) | PO (Purchase order) | 1:1 | 2 | 1 |  |
| PR (po.Purchase Requisition) | PO (po.Purchasing Document) | 1:1 | 2 | 1 |  |
| PR (Purchase Requisition) | MATERIAL (Material) | 1:1 | 2 | 1 | yes |
| PR (Purchase Requisition) | MATERIAL (po.Material) | 1:N | 2 | 2 |  |
| PR (po.Purchase Requisition) | MATERIAL (Material) | N:1 | 2 | 1 |  |
| PR (po.Purchase Requisition) | MATERIAL (po.Material) | 1:1 | 2 | 1 |  |
| PR (Purchase Requisition) | PR_ITEM (Item of requisition) | 1:1 | 2 | 1 | yes |
| PR (Purchase Requisition) | PR_ITEM (po.Item of requisition) | 1:N | 2 | 2 |  |
| PR (po.Purchase Requisition) | PR_ITEM (Item of requisition) | N:1 | 2 | 1 |  |
| PR (po.Purchase Requisition) | PR_ITEM (po.Item of requisition) | 1:1 | 2 | 1 |  |
| PO (Purchase order) | MATERIAL (Material) | N:1 | 2 | 1 | yes |
| PO (Purchase order) | MATERIAL (po.Material) | 1:1 | 2 | 1 |  |
| PO (po.Purchasing Document) | MATERIAL (Material) | N:1 | 2 | 1 |  |
| PO (po.Purchasing Document) | MATERIAL (po.Material) | 1:1 | 2 | 1 |  |
| PO (Purchase order) | PO_ITEM (po.Item) | 1:1 | 2 | 1 | yes |
| PO (po.Purchasing Document) | PO_ITEM (po.Item) | 1:1 | 2 | 1 |  |

### Repeated composite keys
- `PR_ITEM` on `['Purchase Requisition', 'Item of requisition']` → duplicate rows **2**; examples: `[{"key": "6500029693 | 00010", "count": 2}]`

### Repeated single keys
- `PR` / `Purchase Requisition` → duplicate rows **2**; examples: `[{"key": "6500029693", "count": 2}]`
- `MATERIAL` / `Material` → duplicate rows **2**; examples: `[{"key": "9654003280", "count": 2}]`

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`Material Description`, `Material Group`, `Purchasing Group`, `Name of Supplier`, `po.شماره پرونده`

---
## Source: Commercial_Expert / Sheet: Expert Data

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/experts.xlsx`
- Domain: `Commercial`
- Authority: `Tier 1`
- Rows: **2**
- Columns: **14**
- Sample: `samples/Commercial_Expert__Expert_Data__sample.csv`

### Grain candidate
`PR_ITEM` on `Purchase Requisition, Item of requisition` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| BL | BL No. | header |
| MATERIAL | Material | header |
| ORDER | Order No. (Our Reference) | header |
| PR | Purchase Requisition | header |
| PR_ITEM | Item of requisition | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| وضعیت سفارش | مورد تایید | 1 |  |
| وضعیت سفارش | تایید نشده | 1 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| PR (Purchase Requisition) | ORDER (Order No. (Our Reference)) | N:1 | 2 | 1 | yes |
| PR (Purchase Requisition) | MATERIAL (Material) | 1:1 | 2 | 1 | yes |
| PR (Purchase Requisition) | PR_ITEM (Item of requisition) | 1:1 | 2 | 1 | yes |
| ORDER (Order No. (Our Reference)) | BL (BL No.) | 1:N | 2 | 2 | yes |
| ORDER (Order No. (Our Reference)) | MATERIAL (Material) | 1:N | 2 | 2 | yes |

### Repeated single keys
- `ORDER` / `Order No. (Our Reference)` → duplicate rows **2**; examples: `[{"key": "502805", "count": 2}]`

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`Data type`, `Material Description`, `نزد سازنده`, `در راه`, `گمرک`

---
## Source: NTSW / Sheet: Import Licence

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/ntsw.xlsx`
- Domain: `Registration / FX`
- Authority: `Tier 1`
- Rows: **2**
- Columns: **5**
- Sample: `samples/NTSW__Import_Licence__sample.csv`

### Grain candidate
`ORDER_REG` on `شماره سفارش, کد ثبت سفارش` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| ORDER | شماره سفارش | header |
| REG | کد ثبت سفارش | header |
| REG_FILE | شماره پرونده ثبت سفارش | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| وضعیت | فعال | 2 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| ORDER (شماره سفارش) | REG (کد ثبت سفارش) | 1:1 | 2 | 1 | yes |
| REG (کد ثبت سفارش) | REG_FILE (شماره پرونده ثبت سفارش) | 1:1 | 2 | 1 | yes |

---
## Source: NTSW / Sheet: Release Commitment

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/ntsw.xlsx`
- Domain: `Registration / FX`
- Authority: `Tier 1`
- Rows: **2**
- Columns: **11**
- Sample: `samples/NTSW__Release_Commitment__sample.csv`

### Grain candidate
`REG_NATIVE_ROW` on `کد ثبت سفارش, شماره ردیف تعهد` — uniqueness `0.5`, coverage `1.0`, repeated-key rows `1`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| EXPORT_ROW_NO | ردیف | header |
| NATIVE_ROW_ID | شماره ردیف تعهد | header |
| REG | کد ثبت سفارش | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| وضعیت رفع تعهد | رفع تعهد نشده | 2 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| REG (کد ثبت سفارش) | NATIVE_ROW_ID (شماره ردیف تعهد) | 1:1 | 1 | 1 | yes |

### Repeated composite keys
- `REG_NATIVE_ROW` on `['کد ثبت سفارش', 'شماره ردیف تعهد']` → duplicate rows **2**; examples: `[{"key": "98404279 | 7", "count": 2}]`

### Repeated single keys
- `REG` / `کد ثبت سفارش` → duplicate rows **2**; examples: `[{"key": "98404279", "count": 2}]`

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`شعبه`, `شرکت`

---
## Source: NTSW / Sheet: Allocation

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/ntsw.xlsx`
- Domain: `Registration / FX`
- Authority: `Tier 1`
- Rows: **2**
- Columns: **15**
- Sample: `samples/NTSW__Allocation__sample.csv`

### Grain candidate
`REG_NATIVE_ROW` on `کد ثبت سفارش, ردیف درخواست` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| EXPORT_ROW_NO | ردیف | header |
| NATIVE_ROW_ID | ردیف درخواست | header |
| REG | کد ثبت سفارش | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| وضعیت | تایید نشده | 1 |  |
| وضعیت | تخصيص يافته | 1 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| REG (کد ثبت سفارش) | NATIVE_ROW_ID (ردیف درخواست) | 1:N | 2 | 2 | yes |

### Repeated single keys
- `REG` / `کد ثبت سفارش` → duplicate rows **2**; examples: `[{"key": "98404279", "count": 2}]`

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`فرآیند فعلی`, `محل تامین ارز`, `نوع درخواست`, `شعبه`, `شرکت`

---
## Source: Oracle / Sheet: Total_Report 14050610

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/oracle.xlsx`
- Domain: `Inventory`
- Authority: `Domain evidence`
- Rows: **1**
- Columns: **10**
- Sample: `samples/Oracle__Total_Report_14050610__sample.csv`

### Grain candidate
`MATERIAL` on `شماره فنی` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| MATERIAL | شماره فنی | header |

### Status values
_None detected._

### Co-observed relation candidates
_None detected._

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`کد جنس`, `شرح جنس`, `گروه تامین`, `کارشناس خرید خارجی`

---
## Source: FX_Transactions / Sheet: Sheet1

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/fx_transactions.xlsx`
- Domain: `Treasury`
- Authority: `Domain evidence`
- Rows: **1**
- Columns: **14**
- Sample: `samples/FX_Transactions__Sheet1__sample.csv`

### Grain candidate
`ORDER_REG` on `شماره سفارش, ثبت سفارش` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| BL | شماره بارنامه | header |
| ORDER | شماره سفارش | header |
| REG | ثبت سفارش | header |

### Status values
| Column | Value | Count | Raw variants |
| --- | --- | --- | --- |
| وضعیت | تایید شده | 1 |  |

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| ORDER (شماره سفارش) | REG (ثبت سفارش) | 1:1 | 1 | 1 | yes |
| ORDER (شماره سفارش) | BL (شماره بارنامه) | 1:1 | 1 | 1 | yes |

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`نام ذینفع`, `ارز خریداری شده`, `ارز سوئیفت`

---
## Source: Customs / Sheet: SeaClearance

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/customs.xlsx`
- Domain: `Customs`
- Authority: `Domain evidence`
- Rows: **1**
- Columns: **12**
- Sample: `samples/Customs__SeaClearance__sample.csv`

### Grain candidate
`ORDER_BL` on `شماره سفارش, شماره بارنامه` — uniqueness `1.0`, coverage `1.0`, repeated-key rows `0`.

### Representative keys
| Role | Column | Side |
| --- | --- | --- |
| BL | شماره بارنامه | header |
| COTTAGE | کوتاژ | header |
| CUSTOMS_FILE | پرونده ترخیص | header |
| ORDER | شماره سفارش | header |

### Status values
_None detected._

### Co-observed relation candidates
| From | To | Card. | Pairs | Max fanout | Primary |
| --- | --- | --- | --- | --- | --- |
| ORDER (شماره سفارش) | BL (شماره بارنامه) | 1:1 | 1 | 1 | yes |
| BL (شماره بارنامه) | COTTAGE (کوتاژ) | 1:1 | 1 | 1 | yes |
| BL (شماره بارنامه) | CUSTOMS_FILE (پرونده ترخیص) | 1:1 | 1 | 1 | yes |

### Unclassified columns
_No role was asserted for these; they are reported rather than guessed._

`نوع حمل`, `ترخیص کامل`, `ترخیص درصدی`, `تعرفه`

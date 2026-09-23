# GSI Model Context Evidence Pack

Generated: 2026-09-23T08:10:38
Config: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/sources_local.yaml`

## Interpretation rules

- Samples maximize process/key/status coverage; they are not statistical samples.
- Grain and relation findings are heuristic unless confirmed by contracts/code.
- Co-observed keys are not automatically authoritative joins.
- Missing evidence must not be interpreted as proof that a process step did not occur.
- Preserve source authority and domain semantics.

## Cross-source key map

| Role | Occurrences | Sources | Columns |
| --- | --- | --- | --- |
| PR | 3 | Commercial_Expert, SAP | SAP/Data: Purchase Requisition; SAP/Data: po.Purchase Requisition; Commercial_Expert/Expert Data: Purchase Requisition |
| PR_ITEM | 3 | Commercial_Expert, SAP | SAP/Data: Item of requisition; SAP/Data: po.Item of requisition; Commercial_Expert/Expert Data: Item of requisition |
| MATERIAL | 6 | Commercial_Expert, SAP | SAP/Data: Material; SAP/Data: Material Description; SAP/Data: Material Group; SAP/Data: po.Material; Commercial_Expert/Expert Data: Material; Commercial_Expert/Expert Data: Material Description |
| ORDER | 6 | Commercial_Expert, Customs, FX_Transactions, SAP | SAP/Data: Purchase order; SAP/Data: po.Net Order Value; Commercial_Expert/Expert Data: Order No. (Our Reference); Commercial_Expert/Expert Data: Quantity In Order; FX_Transactions/Sheet1: شماره سفارش; Customs/SeaClearance: شماره سفارش |
| PO | 11 | SAP | SAP/Data: Purchase order; SAP/Data: po.Purchasing Document; SAP/Data: po.Item; SAP/Data: po.Purchase Requisition; SAP/Data: po.Item of requisition; SAP/Data: po.Material; SAP/Data: po.Supplier; SAP/Data: po.Net Order Value |
| SUPPLIER | 2 | SAP | SAP/Data: Name of Supplier; SAP/Data: po.Supplier |
| WORKFLOW | 2 | SAP | SAP/Data: WorkFlow ID; SAP/Data: WorkFlow Status |
| PO_ITEM | 2 | SAP | SAP/Data: po.Item; SAP/Data: po.Item of requisition |
| REG_FILE | 2 | Customs, SAP | SAP/Data: po.شماره پرونده; Customs/SeaClearance: پرونده ترخیص |
| BL | 3 | Commercial_Expert, Customs, FX_Transactions | Commercial_Expert/Expert Data: BL No.; FX_Transactions/Sheet1: شماره بارنامه; Customs/SeaClearance: شماره بارنامه |
| REG | 3 | FX_Transactions, NTSW | NTSW/Release Commitment: کد ثبت سفارش; NTSW/Allocation: کد ثبت سفارش; FX_Transactions/Sheet1: ثبت سفارش |
| COTTAGE | 2 | Customs | Customs/SeaClearance: کوتاژ; Customs/SeaClearance: تاریخ  دریافت شماره کوتاژ |

---
## Source: SAP / Sheet: Data

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/SAP.xlsx`
- Domain: `Planning / Procurement`
- Authority: `Domain authority for SAP PR/PO/workflow evidence`
- Rows: **3**
- Columns: **28**
- Sample: `samples/SAP__Data__sample.csv`

### Grain candidate
`PO_ITEM` using `Purchase order, po.Item` — uniqueness ratio `1.0`.

### Semantic columns
| Role | Columns |
| --- | --- |
| PR | Purchase Requisition, po.Purchase Requisition |
| PR_ITEM | Item of requisition, po.Item of requisition |
| MATERIAL | Material, Material Description, Material Group, po.Material |
| ORDER | Purchase order, po.Net Order Value |
| PO | Purchase order, po.Purchasing Document, po.Item, po.Purchase Requisition, po.Item of requisition, po.Material, po.Supplier, po.Net Order Value, po.Currency, po.Document Date, po.شماره پرونده |
| DATE | Requisition date, Changed On, Release Date, po.Document Date |
| STATUS | Release Date, Processing status, Deletion Indicator, WorkFlow Status |
| QUANTITY | Quantity requested, Quantity ordered |
| SUPPLIER | Name of Supplier, po.Supplier |
| WORKFLOW | WorkFlow ID, WorkFlow Status |
| PO_ITEM | po.Item, po.Item of requisition |
| AMOUNT | po.Net Order Value |
| CURRENCY | po.Currency |
| REG_FILE | po.شماره پرونده |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| Release Date | 2026-01-06 | 2 |
| Release Date | 2026-03-02 | 1 |
| Processing status | مورد تایید | 1 |
| Processing status | تایید نشده | 1 |
| Processing status | در گردش | 1 |
| Deletion Indicator | X | 1 |
| WorkFlow Status | RELEASED | 2 |
| WorkFlow Status | IN PROCESS | 1 |

### Co-observed relation candidates
| From | To | Pairs | Max fanout |
| --- | --- | --- | --- |
| PR (Purchase Requisition) | PO (Purchase order) | 2 | 2 |
| PR (Purchase Requisition) | ORDER (Purchase order) | 2 | 2 |
| PR (Purchase Requisition) | MATERIAL (Material) | 2 | 1 |

### Repeated-key signals
- `['Purchase Requisition']` → duplicate rows: **2**; examples: `[{"key": "6500029693", "count": 2}]`
- `['Item of requisition']` → duplicate rows: **2**; examples: `[{"key": "00010", "count": 2}]`
- `['po.Currency']` → duplicate rows: **2**; examples: `[{"key": "EUR", "count": 2}]`
- `['po.شماره پرونده']` → duplicate rows: **2**; examples: `[{"key": "664823825", "count": 2}]`
- `['Material']` → duplicate rows: **2**; examples: `[{"key": "9654003280", "count": 2}]`
- `['Material Description']` → duplicate rows: **2**; examples: `[{"key": "واشر تخت", "count": 2}]`
- `['Material Group']` → duplicate rows: **2**; examples: `[{"key": "MG-11", "count": 2}]`
- `['Name of Supplier']` → duplicate rows: **2**; examples: `[{"key": "ACME", "count": 2}]`

---
## Source: Commercial_Expert / Sheet: Expert Data

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/experts.xlsx`
- Domain: `Commercial`
- Authority: `Tier 1 commercial source`
- Rows: **2**
- Columns: **14**
- Sample: `samples/Commercial_Expert__Expert_Data__sample.csv`

### Grain candidate
`PR_ITEM` using `Purchase Requisition, Item of requisition` — uniqueness ratio `1.0`.

### Semantic columns
| Role | Columns |
| --- | --- |
| ORDER | Order No. (Our Reference), Quantity In Order |
| MATERIAL | Material, Material Description |
| PR | Purchase Requisition |
| PR_ITEM | Item of requisition |
| BL | BL No. |
| CURRENCY | نوع ارز |
| AMOUNT | PI Line Value |
| QUANTITY | Quantity In Order |
| STATUS | وضعیت سفارش |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| وضعیت سفارش | مورد تایید | 1 |
| وضعیت سفارش | تایید نشده | 1 |

### Co-observed relation candidates
| From | To | Pairs | Max fanout |
| --- | --- | --- | --- |
| PR (Purchase Requisition) | ORDER (Order No. (Our Reference)) | 2 | 1 |
| PR (Purchase Requisition) | MATERIAL (Material) | 2 | 1 |
| ORDER (Order No. (Our Reference)) | BL (BL No.) | 2 | 2 |

### Repeated-key signals
- `['Order No. (Our Reference)']` → duplicate rows: **2**; examples: `[{"key": "502805", "count": 2}]`

---
## Source: NTSW / Sheet: Release Commitment

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/ntsw.xlsx`
- Domain: `Registration / FX allocation / commitment`
- Authority: `Tier 1 commercial/registration source`
- Rows: **2**
- Columns: **11**
- Sample: `samples/NTSW__Release_Commitment__sample.csv`

### Grain candidate
`REG` using `کد ثبت سفارش` — uniqueness ratio `0.5`.

### Semantic columns
| Role | Columns |
| --- | --- |
| REG | کد ثبت سفارش |
| CURRENCY | ارز |
| AMOUNT | مانده تعهد |
| DATE | تاریخ ایجاد تعهد |
| STATUS | وضعیت رفع تعهد |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| وضعیت رفع تعهد | رفع تعهد نشده | 2 |

### Co-observed relation candidates
_None detected._

### Repeated-key signals
- `['کد ثبت سفارش']` → duplicate rows: **2**; examples: `[{"key": "98404279", "count": 2}]`

---
## Source: NTSW / Sheet: Allocation

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/ntsw.xlsx`
- Domain: `Registration / FX allocation / commitment`
- Authority: `Tier 1 commercial/registration source`
- Rows: **2**
- Columns: **15**
- Sample: `samples/NTSW__Allocation__sample.csv`

### Grain candidate
`REG` using `کد ثبت سفارش` — uniqueness ratio `0.5`.

### Semantic columns
| Role | Columns |
| --- | --- |
| REG | کد ثبت سفارش |
| STATUS | وضعیت, تاریخ تایید |
| AMOUNT | مبلغ درخواست |
| CURRENCY | ارز درخواست, محل تامین ارز, نرخ ارز |
| DATE | تاریخ ایجاد درخواست, تاریخ تخصیص, تاریخ تایید |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| وضعیت | تایید نشده | 1 |
| وضعیت | تخصيص يافته | 1 |

### Co-observed relation candidates
_None detected._

### Repeated-key signals
- `['کد ثبت سفارش']` → duplicate rows: **2**; examples: `[{"key": "98404279", "count": 2}]`

---
## Source: FX_Transactions / Sheet: Sheet1

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/fx_transactions.xlsx`
- Domain: `Treasury / FX / Payment`
- Authority: `Domain evidence`
- Rows: **1**
- Columns: **14**
- Sample: `samples/FX_Transactions__Sheet1__sample.csv`

### Grain candidate
`ORDER_REG` using `شماره سفارش, ثبت سفارش` — uniqueness ratio `1.0`.

### Semantic columns
| Role | Columns |
| --- | --- |
| DATE | تاریخ خرید, تاریخ سوئیفت, تاریخ تایید وصول |
| REG | ثبت سفارش |
| ORDER | شماره سفارش |
| CURRENCY | ارز خریداری شده, نوع ارز خریداری شده, نرخ ارز خریداری شده, مبلغ ارز پروفرم, نوع ارز, ارز سوئیفت |
| AMOUNT | مبلغ ارز پروفرم |
| STATUS | تاریخ تایید وصول, وضعیت |
| BL | شماره بارنامه |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| وضعیت | تایید شده | 1 |

### Co-observed relation candidates
| From | To | Pairs | Max fanout |
| --- | --- | --- | --- |
| ORDER (شماره سفارش) | REG (ثبت سفارش) | 1 | 1 |
| ORDER (شماره سفارش) | BL (شماره بارنامه) | 1 | 1 |

---
## Source: Customs / Sheet: SeaClearance

- Path: `/tmp/claude-0/-home-user-dataengineering/58ee2be6-321f-501c-b83a-d123925e2458/scratchpad/maptest/data/customs.xlsx`
- Domain: `Customs / Clearance`
- Authority: `Domain evidence`
- Rows: **1**
- Columns: **12**
- Sample: `samples/Customs__SeaClearance__sample.csv`

### Grain candidate
`ORDER_BL` using `شماره سفارش, شماره بارنامه` — uniqueness ratio `1.0`.

### Semantic columns
| Role | Columns |
| --- | --- |
| REG_FILE | پرونده ترخیص |
| STATUS | پرونده ترخیص, ترخیص کامل, ترخیص درصدی |
| BL | شماره بارنامه |
| ORDER | شماره سفارش |
| COTTAGE | کوتاژ, تاریخ  دریافت شماره کوتاژ |
| DATE | تاریخ  دریافت شماره کوتاژ, تاریخ بارگیری 6 (کامل) |
| AMOUNT | ارزش فاکتور |
| CURRENCY | ارزش فاکتور, نوع ارز |

### Status values
| Column | Value | Count |
| --- | --- | --- |
| پرونده ترخیص | CF-1 | 1 |
| ترخیص کامل | * | 1 |

### Co-observed relation candidates
| From | To | Pairs | Max fanout |
| --- | --- | --- | --- |
| ORDER (شماره سفارش) | BL (شماره بارنامه) | 1 | 1 |
| BL (شماره بارنامه) | COTTAGE (کوتاژ) | 1 | 1 |

# تحلیل بستهٔ بازخورد `GSI_FEEDBACK_20260924_142807`

اجرای واقعی روی ویندوز: `F:\BI\T4`، Windows 11، Python 3.13.9، ۱۴:۲۸ تا ۱۴:۵۶.
`release_gate: HOLD` با ۸ blocker. `FEEDBACK_SHA256.json` کامل تأیید شد (۱۰۵/۱۰۵)،
و قرارداد «هیچ ردیف کسب‌وکاری خامی وارد بازخورد نمی‌شود» **رعایت شده است** —
هیچ نام مشتری یا تأمین‌کنندهٔ واقعی در ۱۰۶ فایل بسته نیست.

---

## ۰) دو نکته که قبل از هر چیز باید روشن شود

### این بازخورد از بیلد دیگری است، نه از پکیجی که بررسی کردم

`feedback_summary.json` می‌گوید `release_channel: rc4-opt2-h1-offline-diagnostic-20260924`
و `base: 29.8.2 RC4-OPT2 H1 NTSW Verified Final`. پکیجی که برای ممیزی فرستادید
`final-production-rewrite-20260924` بود. این دو یکی نیستند، و دست‌کم یک باگی که
این بازخورد گزارش می‌کند در پکیج بررسی‌شده **از قبل اصلاح شده است** (بخش ۲).

### هیچ سورس واقعی‌ای در این اجرا خوانده نشده است

`environment.json` می‌گوید:

```json
"env_keys_present": []
```

یعنی هیچ‌کدام از `GSI_FOREIGN` / `GSI_BLS` / `GSI_CLEARANCE` / `GSI_HR` / … ست
نشده بود، و `cwd` هم خودِ `F:\BI\T4` بوده. پس probe به‌جای شبکهٔ سازمان، **درخت
خود پکیج** را جست‌وجو کرده است. این یعنی:

> این اجرا **رویداد پذیرش عملیاتی** («اولین refresh/publish موفق روی سورس‌های
> سازمان») نیست. برای آن، باید مسیرهای `GSI_*` به شیر واقعی اشاره کنند.

---

## ۱) پنج blocker از هشت‌تا، «یافته» نیستند

| blocker | واقعیت |
|---|---|
| `INDEPENDENT_SEMANTIC_FAILURES` (۴۳ ناموفق) | خودِ پکیج پیش‌بینی کرده بود: `known_baseline_on_latest_package.frozen_failed: 43`. نتیجهٔ واقعی دقیقاً ۱۳۰/۴۳ شد و هر ۴۳ مورد به یافته‌های شناخته‌شدهٔ IA01–IA17 نگاشت شد، با `unmapped_failures: []`. این **محمولهٔ تشخیصی** است، نه رگرسیون. |
| `EXTENDED_DIAGNOSTIC_FAILURES` (۳۳ ناموفق) | همان‌طور: اعلام‌شده `extended_failed: 33`، واقعی ۴۴/۳۳. |
| `INTERNAL_ORDER_NORMAL_FAIL` / `..._REVERSE_FAIL` | هر دو صرفاً چون تست‌های داخلی ناموفق‌اند exit=1 داده‌اند. وابستگی به ترتیب اجرا **دیده نشد**؛ این دو blocker مستقل نیستند. |
| `REQUIRED_SOURCE_MISSING` | نتیجهٔ بخش ۰ است: سورسی پیکربندی نشده بود. |
| `NTSW_REAL_DATA_PROBE_ERROR` | نتیجهٔ بخش ۲ است. |

**سه blocker واقعی می‌مانند:** شکست‌های داخلی، timeoutها، و خطای probe.

---

## ۲) `NTSW_REAL_DATA_PROBE_ERROR` — علت دقیق، و در پکیج بررسی‌شده بسته است

خطا: `ValueError: Excel file format cannot be determined, you must specify an engine manually.`

علتش در `source_inventory.json` دیده می‌شود: probe برای `ntsw` وضعیت **FOUND**
داده، ولی «فایل»‌هایی که پیدا کرده اینها هستند:

```
ntsw   FOUND   ntsw_probe_child.py, a50_ntsw.py, NTSW_FINAL_GATE.json, NTSW_DWH_AUDIT.txt
oracle FOUND   ORACLE_TWO_SHEET_POLICY_FA.md, a40_oracle.py, test_oracle_union_v28_1.py
sata   FOUND   a20_sata.py
```

یعنی **کد و مستندات خود پکیج به‌عنوان سورس کسب‌وکاری تبلیغ شده‌اند**. بعد
`probe_ntsw_semantics` اولین «فایل» را برمی‌دارد و `pd.ExcelFile()` روی یک فایل
`.py` صدا می‌زند — و همان ValueError بالا می‌آید.

**این باگ در پکیجی که ممیزی کردم وجود ندارد.** `offline_validation/source_probe.py`
در آن پکیج دقیقاً همین را می‌بندد (`DATA_SUFFIXES` و شرط شیت‌های اعلام‌شده)، با
همین کامنت: «Broad filename patterns must never promote .py/.md files into
business sources». اجرای همان probe شیپ‌شده روی همان درخت و بدون `GSI_*`:

```
MISSING_OPTIONAL   ntsw     []
MISSING_OPTIONAL   oracle   []
MISSING_OPTIONAL   sata     []
MISSING_REQUIRED   hr       []
```

صفر فایل، بدون هیچ ترفیع `.py`/`.md`. پس ماشین `F:\BI\T4` نسخهٔ قدیمی‌تری اجرا
می‌کند. **اول پکیج آن ماشین را به‌روز کنید، بعد دوباره اجرا بگیرید.**

---

## ۳) شکست‌های داخلی: ۱۶ فایل، ولی نصفش «شکست» نیست

از ۹۰ فایل: ۷۰ موفق، ۱۶ ناموفق، ۴ timeout. آن ۱۶ تا دو چیز کاملاً متفاوت‌اند:

**هشت فایل با `exit=5` — یعنی «هیچ تستی جمع نشد»، نه شکست.**
`test_design_system`, `test_email_report`, `test_studio`, `test_v26_20_runtime_and_grain`,
`legacy_test_html_browser_v26_17`, `legacy_test_v26_16_release`,
`legacy_test_v26_18_charts_delivery_persistence`, `legacy_test_warehouse_v26_17`.
اینها فایل‌های سبک-اسکریپت‌اند که `run_all_tests.py` آنها را به‌صورت اسکریپت اجرا
می‌کند، نه از طریق pytest. runner بازخورد همه را با pytest صدا می‌زند و exit=5 را
شکست می‌شمارد. **این نقص runner است، نه محصول** — و نیمی از این blocker را می‌سازد.

**هشت فایل شکست واقعی، و یک علت بر نصفشان غالب است:**

| فایل | علت |
|---|---|
| `test_fx_obligation_v28_1` (۸) | `PermissionError: [WinError 32]` |
| `test_control_center_v27_2` (۵) | `PermissionError: [WinError 32]` |
| `test_fx_adapter_quarantine_v28` (۲) | `PermissionError: [WinError 32]` |
| `test_opus_rc4_warehouse_reset` (۴) | `PermissionError: [WinError 32]` |
| `test_knowledge_desk_offline_v292` (۱) | `WinError 10013` — سیاست شرکتی bind سوکت محلی را ممنوع کرده |
| `test_import_hygiene` (۵ خطا) | Doctor روی Python 3.13 برای حالت فایل تخت کد خروجی ۱ نمی‌دهد |
| `test_dashboard` (۲ خطا) | خطای legacy check |
| `test_personalization_v27_1` (۱) | `IdentityError` |

**WinError 32 یک ریشه دارد:** ویندوز اجازهٔ حذف یا جایگزینی فایلی را که هنوز
handle بازی دارد نمی‌دهد. روی لینوکس این نامرئی است (unlink روی فایل باز کار
می‌کند)، برای همین در هر دو اجرای لینوکسی (۱۱۷۵/۱ و ۱۱۷۷/۰) دیده نشد.

---

## ۴) چه چیزی را اصلاح کردم

`Warehouse.reset()` مال من است و واقعاً روی ویندوز می‌شکست. اصلاح شد:

- `_unlink_with_retry` — پس از `gc.collect()` چند بار با backoff کوتاه تلاش
  می‌کند (CPython اتصال sqlite بدون ارجاع را در finalizer می‌بندد).
- اگر باز هم نشد، **reset شکست نمی‌خورد**: قرارداد این متد «انبار خالی است»
  بود نه «فایل حذف شد»، پس محتوای فایل را با SQL خالی می‌کند
  (`_drop_all_objects` + `VACUUM`) و `emptied_in_place: true` را گزارش می‌دهد.
- فایلی که حذف نشد در `undeleted` گزارش می‌شود؛ هیچ حذفی بی‌صدا نیست.

تست تازه این مسیر را با شبیه‌سازی `PermissionError(32)` می‌سنجد و تأیید می‌کند که
انبار بعدش خالی، سالم (`integrity_check: ok`) و بلافاصله قابل استفاده است.

`test_knowledge_desk_offline_v292` هم حالا وقتی ماشین اجازهٔ bind سوکت نمی‌دهد
**skip** می‌کند نه fail — امتناع ماشین، شکست محصول نیست.

باقی‌مانده و اصلاح‌نشده: `test_import_hygiene`، `test_dashboard`،
`test_personalization_v27_1` و همان WinError 32 در control_center و fx_obligation.
اینها کد من نیستند و بدون یک ماشین ویندوزی برای تأیید، اصلاحشان حدس می‌شد.

---

## ۵) دو مورد دیگر که باید ببینید

**وابستگی‌ها روی ماشین هدف با `requirements.txt` نمی‌خوانند.** فایل
`streamlit-sortables==0.3.1` را **پین دقیق** کرده، ولی ماشین `0.2.0` دارد.
همچنین numpy 2.2.2، pytest 9.0.2، streamlit 1.51.0، و Python 3.13 (پکیج ۳٫۱۱+
اعلام می‌کند و من روی ۳٫۱۲ آزمودم). یک پین نقض‌شده یعنی هیچ‌کس نصب را اعتبارسنجی
نکرده است.

**سقف timeout برای این ماشین تنگ است.** `test_validation.py` در ۱۸۰٫۱۶۷ ثانیه
**موفق** شد — یعنی درست لبهٔ سقف ۱۸۰ ثانیه. چهار فایل timeout شدند
(`test_architecture`, `test_contracts_report`, `test_criticality`,
`test_rules_and_moghavemat`) و `test_v26_20_case_action_inventory` هم ۱۳۵ ثانیه
گرفت. سقف را دست‌کم به ۶۰۰ ثانیه ببرید وگرنه نمی‌دانید شکست واقعی است یا کندی.

---

## ۶) ترتیب کاری پیشنهادی

1. پکیج ماشین `F:\BI\T4` را با نسخهٔ ممیزی‌شده جایگزین کنید — باگ ترفیع
   `.py`/`.md` به سورس کسب‌وکاری و در نتیجه خطای probe همان‌جا می‌افتد.
2. `GSI_*` را به مسیرهای واقعی شبکه ست کنید. تا آن نشود، `source_inventory`،
   `REQUIRED_SOURCE_MISSING` و probe هیچ حرفی دربارهٔ دادهٔ واقعی نمی‌زنند.
3. سقف timeout را به ۶۰۰ ثانیه ببرید.
4. runner را طوری اصلاح کنید که فایل‌های سبک-اسکریپت را مثل `run_all_tests.py`
   اجرا کند، یا `exit=5` را «بدون تست» بشمارد نه شکست.
5. `streamlit-sortables` را به `0.3.1` برسانید یا پین را عمداً باز کنید.
6. بعد دوباره اجرا بگیرید. آن‌وقت gate چیزی دربارهٔ محصول می‌گوید.

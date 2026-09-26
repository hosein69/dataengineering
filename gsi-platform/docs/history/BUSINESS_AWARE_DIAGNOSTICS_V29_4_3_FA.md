# GSI V29.4.3 — Relation Health Contract و تشخیص بدون گمراهی

این نسخه بر اساس خروجی واقعی Join Diagnostics بازطراحی شد تا «کم بودن پوشش» با «خراب بودن Join» اشتباه نشود.

## تغییرات اصلی

- `Source Match Rate = intersection / unique source keys` معیار اصلی سلامت Join است.
- `Base Coverage Rate = intersection / unique base keys` فقط دامنه بیزینسی سورس را نشان می‌دهد و به تنهایی خطا نیست.
- SAP فعلاً با policy صریح `diagnostic_status: known_incomplete` از ارزیابی سلامت خارج است. این policy هیچ join جعلی ایجاد نمی‌کند و پس از تکمیل سورس باید حذف شود.
- Relation Health Contract اکنون ابعاد جداگانه دارد: Semantic، Source Match، Base Coverage، Cardinality Health، Scope Alignment و Temporal Alignment.
- Moghavemat و DocCheck برای Orderهای unmatched کالبدشکافی می‌شوند:
  - `NORMALIZATION_CANDIDATE`: فقط شباهت شکل بعد از حذف punctuation؛ auto-match ممنوع.
  - `OUTSIDE_BASE_SCOPE`: Order در یک شاهد مستقیم دیگر دیده شده ولی در Abbasi فعلی نیست.
  - `UNRESOLVED`: شاهد کافی برای توضیح وجود ندارد؛ رکورد حذف نمی‌شود.
- صفر overlap دیگر به اشتباه «فرمت کلید خراب است» گزارش نمی‌شود؛ وضعیت `NO_COMMON_EVIDENCE` یعنی رابطه هنوز اثبات نشده و باید semantics/population/time بررسی شود.
- Joinهای mostly-aligned با unmatched محدود `HEALTHY_WITH_GAPS` و INFO هستند، نه خطای کاذب.
- هشدارهای scope/unmatched به تنهایی exit code ابزار Diagnose را خراب نمی‌کنند؛ فقط ERROR/BLOCKER/FATAL کد خروج 1 می‌دهند.
- خروجی Excel Diagnose یک شیت جدید `تحلیل unmatched سفارش` دارد.
- نرمال‌سازی candidate فقط برای forensic classification است و هرگز روی Core Join اعمال نمی‌شود.

## رفتار SAP تا زمان تکمیل سورس

در `sources.yaml`:

```yaml
diagnostic_status: known_incomplete
```

بنابراین zero-match فعلی SAP:
- در Diagnose = `KNOWN_INCOMPLETE_SOURCE`
- در System Health = INFO/OK با توضیح روشن
- باعث DEGRADED کاذب Run نمی‌شود
- داده SAP به صورت جعلی به PR دیگری وصل نمی‌شود

## اصل طراحی

`Low Base Coverage != Bad Join`

و نیز:

`Candidate similarity != Proven relation`

هیچ fuzzy match، حذف punctuation یا normalization تهاجمی بدون Rule بیزینسی و شاهد معتبر وارد Core نمی‌شود.

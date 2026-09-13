# مشخصات الگوریتمی سطح‌پایین — از درخواست HTTP تا عدد نهایی واچ‌لیست

این سند، پایین‌ترین سطح قابل‌نوشتن از کل مسیر کد است: ساختمان داده‌ها، بازگشتی‌های عددی (recurrences)، ترتیب دقیق عملیات در حلقه‌ی کندل‌به‌کندل، معناشناسی NaN، شرط‌های مرزی و پیچیدگی زمانی. هرچه اینجا ادعا شده مستقیماً از خواندن سورس نصب‌شده‌ی `vibe-trading-ai==0.1.15` و کدهای خودمان استخراج و در چند مورد با اجرای واقعی تأیید شده است.

سند بالادستی و مفهومی‌تر: [`ALGORITHM.md`](./ALGORITHM.md). این یکی جایگزینش نیست، زیرِ آن است.

---

## ۰. گراف فراخوانی کامل، با نوع داده در هر یال

```
live_watchlist.main()
│
├─► fetch_live()                                   # لایه A
│     └─ backtest.loaders.nobitex.DataLoader.fetch(codes, start, end, interval="1D")
│           └─ _fetch_one(session, symbol, resolution, from_ts, to_ts)
│                 └─ HTTP GET × pages ─► Dict[str, DataFrame(index=DatetimeIndex, cols=OHLCV)]
│
├─► indicator_state(df)                            # لایه B + G
│     ├─ rolling(10).mean(), rolling(30).mean()    → Series[float64]
│     ├─ wilder_rsi(close, 14)                     → Series[float64]
│     └─ atr_pct(df, 14)                           → float
│
└─► backtest(symbol, engine_file, tag)             # لایه H
      └─ backtest.runner.main(run_dir: Path)
            ├─ BacktestConfigSchema(**config)                      # اعتبارسنجی pydantic
            ├─ _load_module_from_file(code/signal_engine.py)       # AST scrub + import
            ├─ fetch_data_map(config) ─► DataFetchResult           # دوباره لایه A
            └─ CryptoEngine.run_backtest(config, loader, se, run_dir, bars_per_year)
                  ├─ loader.fetch(...)                    → data_map
                  ├─ signal_engine.generate(data_map)     → signal_map   # لایه C
                  ├─ _align(data_map, signal_map, codes)  → dates, close_df, close_val_df, target_pos, ret_df   # لایه D
                  ├─ evaluation_start_index(config,dates) → int (warm-up prefix)
                  ├─ _execute_bars(...)                   → trades[], equity_snapshots[]   # لایه E
                  ├─ calc_metrics(...)                    → Dict[str, float]               # لایه F
                  └─ _write_artifacts(...)                → CSV/JSON روی دیسک
```

نوع‌های عبوری بین لایه‌ها فقط سه‌تا هستند و همه‌جا ثابت می‌مانند:
`Dict[str, DataFrame]` (داده‌ی بازار) · `Dict[str, Series]` (سیگنال) · `DataFrame` (ماتریس وزن).

---

## ۱. نقشه‌ی ماژول‌ها

| ماژول | مسئولیت | ورودی | خروجی | خالص؟ | حالت داخلی |
|---|---|---|---|---|---|
| `loaders/nobitex.py` | I/O شبکه + پارس UDF | نماد، بازه، تایم‌فریم | `Dict[str, DataFrame]` | خیر (شبکه) | `requests.Session` |
| `loaders/registry.py` | نگاشت `source` → کلاس لودر | رشته | کلاس | بله | `LOADER_REGISTRY` سراسری |
| `signal_engines/*.py` | تولید سیگنال خام | `data_map` | `Dict[str, Series]` | بله | ندارد (بی‌حالت) |
| `engines/base.py::_align` | سیگنال → ماتریس وزن | `data_map`, `signal_map` | ۵ تایی numpy/pandas | بله | ندارد |
| `engines/base.py::BaseEngine` | شبیه‌سازی اجرا | ماتریس وزن + قیمت | `trades`, `equity_snapshots` | خیر | `capital`, `positions`, … |
| `engines/crypto.py::CryptoEngine` | قواعد بازار کریپتو | همان | همان | خیر | مارجین ایزوله، فاندینگ |
| `metrics.py` | آمار عملکرد | `equity_curve`, `trades` | `Dict[str, float]` | بله | ندارد |
| `live_watchlist.py` | اسکن وضعیت زنده | `data_map` + متریک‌ها | جدول واچ‌لیست | بله (محاسبات) | ندارد |
| `runner.py::main` | ارکستراسیون یک ران | `run_dir` | فایل‌های artifact | خیر | فایل‌سیستم |

قرارداد بی‌حالتی موتورهای سیگنال، الزام `runner._validate_signal_engine_class` است: `SignalEngine.__init__` نباید هیچ پارامتر بدون مقدار پیش‌فرض داشته باشد (تا runner بتواند `SignalEngine()` صدا بزند) و `generate` باید callable باشد.

---

## ۲. لایه A — دریافت داده (`loaders/nobitex.py`)

### A.1 نرمال‌سازی نماد

```
map_symbol(s) = s.strip().upper().replace("-","").replace("/","")
```
یعنی `btc-irt`, `BTC/IRT`, `BTCIRT` هر سه به `BTCIRT` می‌رسند. O(len(s)).

### A.2 نگاشت تایم‌فریم → resolution

جدول ثابت `_INTERVAL_MAP` (dict lookup، O(1)):

```
1m→"1"  5m→"5"  15m→"15"  30m→"30"
1h/1H→"60"  3h→"180"  4h→"240"  6h→"360"  12h→"720"
1d/1D→"D"
```

اگر کلید نبود، تابع `{}` برمی‌گرداند (نه استثنا) تا زنجیره‌ی fallback ادامه یابد. **هفتگی وجود ندارد** — `1W` عمداً رد می‌شود تا داده‌ی روزانه بی‌سروصدا جای هفتگی ننشیند.

### A.3 محاسبه‌ی پنجره‌ی epoch

```
start_ts = int(Timestamp(start_date).timestamp())
end_ts   = int((Timestamp(end_date) + Timedelta(days=1)).timestamp())
```
یک روز به انتها اضافه می‌شود تا کندل‌های خودِ روز پایان از فیلتر نیفتند؛ فیلتر نهایی نیم‌باز است: `[start_dt, end_dt)`.

### A.4 الگوریتم صفحه‌بندی

```
deadline ← monotonic() + FETCH_BUDGET_S        # پیش‌فرض ۹۰ ثانیه
frames ← []
page ← 1
تکرار حداکثر _MAX_PAGES (=40) بار:
    check_budget(deadline)                      # اگر بودجه تمام شد → استثنا
    data ← retry_with_budget(GET .../udf/history
                             ?symbol&resolution&from=start_ts&to=end_ts&page=page)
        # کدهای 429/500/502/503/504 → HTTPError → retry داخل بودجه
    اگر data["s"] == "no_data"  → break
    اگر data["s"] != "ok"       → RequestException
    times ← data["t"];  اگر خالی → break
    frames.append(DataFrame از t/o/h/l/c/v)
    اگر len(times) < 500  یا  times[0] <= start_ts → break     # صفحه‌ی ناقص = پایان
    page ← page + 1
    sleep(0.5)                                  # سقف نرخ: ۶۰ درخواست در دقیقه
```

نکته‌ی معنایی مهم: `page` به سمت **قدیمی‌تر** حرکت می‌کند؛ صفحه‌ی ۱ جدیدترین بازه است. شرط `times[0] <= start_ts` یعنی به ابتدای بازه‌ی درخواستی رسیده‌ایم.

سقف داده: `40 × 500 = 20000` کندل. برای `1D` این ۵۴ سال است (عملاً بی‌نهایت)، برای `1m` فقط ۱۳.۹ روز.

### A.5 مونتاژ فریم نهایی

```
df ← concat(frames).set_index("trade_date").sort_index()
df ← df[~df.index.duplicated(keep="last")]      # هم‌پوشانی صفحات
df ← df[(df.index >= start_dt) & (df.index < end_dt)]
df ← df[["open","high","low","close","volume"]].dropna(subset=OHLC)
df ← validate_ohlc(df)                          # ردیف‌های با low>high و… حذف/اصلاح
return df.astype("float64")
```

`volume` اگر در پاسخ نبود با صفر پر می‌شود (`fillna(0)`), چون فقدان حجم نباید ردیف قیمتی سالم را حذف کند.

مُهر زمانی: تهران (UTC+03:30). کندل روزانه در نیمه‌شب تهران باز می‌شود و کندل ساعتی روی دقیقه‌ی ۳۰ می‌افتد — این در ایندکس منعکس است و در تبدیل به UTC-naive حفظ می‌شود.

پیچیدگی: `O(P·B)` برای پارس (P صفحه، B کندل در صفحه) + `O(n log n)` برای `sort_index`.

---

## ۳. لایه B — اندیکاتورها (بازگشتی‌های دقیق)

### B.1 میانگین متحرک ساده

```
SMA_N[t] = (1/N) · Σ_{k=0}^{N-1} close[t-k]     برای t ≥ N-1
SMA_N[t] = NaN                                   برای t < N-1
```
پیاده‌سازی: `close.rolling(N, min_periods=N).mean()`. تصریح `min_periods=N` عمدی است — بدون آن pandas از کمتر از N نمونه هم میانگین می‌سازد و یک MA30 «نیم‌پخته» تولید می‌کند که با MA30 واقعی اشتباه گرفته می‌شود.

پیچیدگی: O(n) (pandas از الگوریتم پنجره‌ی لغزان تجمعی استفاده می‌کند، نه O(n·N)).

### B.2 RSI وایلدر

```
δ[t]     = close[t] − close[t−1]                 δ[0] = NaN
gain[t]  = max(δ[t], 0)
loss[t]  = max(−δ[t], 0)

# هموارسازی نمایی وایلدر با α = 1/N :
G[t] = (1−α)·G[t−1] + α·gain[t]
L[t] = (1−α)·L[t−1] + α·loss[t]

RS[t]  = G[t] / L[t]
RSI[t] = 100 − 100/(1 + RS[t])
```

پیاده‌سازی: `.ewm(alpha=1/period, adjust=False).mean()`.

سه ریزه‌کاری عددی که تجربی تأیید شد:

1. **بذر (seeding).** pandas مقادیر NaN ابتدایی را رد می‌کند و `G` را روی **اولین مشاهده‌ی معتبر** بذر می‌گذارد: `G[t₁] = gain[t₁]`. وایلدر کلاسیک به‌جایش میانگین ساده‌ی N مقدار اول را بذر می‌کند. اختلاف با نرخ `(1−α)^k` میرا می‌شود و بعد از ≈۵N کندل زیر یک‌هزارم واحد RSI است؛ روی پنجره‌ی ۴۳۰ کندلی ما کاملاً بی‌اثر است، ولی برای پنجره‌ی کوتاه باید بدانید.
2. **تقسیم بر صفر.** `L[t] = 0` (روند صعودی بی‌وقفه) با `loss.replace(0, NaN)` به NaN تبدیل و سپس نتیجه با `fillna(100.0)` به RSI=100 می‌رسد — یعنی حالت حدی درست، بدون `inf`.
3. **ردیف اول.** خروجی برای `t=0` همیشه NaN است (چون `δ[0]=NaN`)، و این NaN به بیرون درز نمی‌کند چون فقط `iloc[-1]` مصرف می‌شود.

### B.3 ATR

```
TR[t]  = max( high[t] − low[t],
              |high[t] − close[t−1]|,
              |low[t]  − close[t−1]| )
ATR[t] = (1−α)·ATR[t−1] + α·TR[t]        با α = 1/14
ATR%   = 100 · ATR[last] / close[last]
```
پیاده‌سازی با `pd.concat([...], axis=1).max(axis=1)` (بردارینه، O(n)) و همان `ewm`.

---

## ۴. لایه C — موتورهای سیگنال

### C.1 نسخه‌ی دیباگ‌شده‌ی لانگ-اونلی

```python
n = max(len(data_map), 1)
fast_ma = close.rolling(10, min_periods=10).mean()
slow_ma = close.rolling(30, min_periods=30).mean()
ready   = fast_ma.notna() & slow_ma.notna()          # ماسک بولی
sig     = ((fast_ma > slow_ma) & ready).astype(float) / n
out     = sig.where(ready, 0.0)
```

چهار عملیات برداری، همه O(n)، بدون حلقه‌ی پایتونی.

چرا `ready` صریح است و به `NaN > NaN → False` تکیه نمی‌کنیم: هر دو مسیر عدد یکسان می‌دهند، ولی اولی «اندیکاتور آماده نیست» را از «سیگنال نزولی» جدا نگه می‌دارد. اهمیتش وقتی معلوم می‌شود که کسی بعداً موتور را long/short کند — آن‌وقت مسیر ضمنی، دوره‌ی warm-up را به یک پوزیشن **شورت** ترجمه می‌کند.

### C.2 نسخه‌ی متقارن long/short

```python
direction = (fast_ma > slow_ma).astype(float) * 2.0 - 1.0     # {0,1} → {−1,+1}
out       = (direction / n).where(ready, 0.0)
```
تبدیل `2x−1` یک ضرب و یک تفریق برداری است؛ `where(ready, 0.0)` اینجا **الزامی** است، وگرنه ۳۰ کندل اولِ هر نماد به شورت کامل تبدیل می‌شد.

### C.3 قرارداد بارگذاری در runner

`_load_module_from_file` قبل از اجرا، AST فایل را بازرسی می‌کند و این‌ها را رد می‌کند: import دوری خودش، importهای ناامن، دکوراتورها، و **statement سطح-بالای اجرایی**. یعنی کد ماژول باید فقط تعریف باشد؛ منطق باید داخل متد بدنه باشد (که هنگام ساخت نمونه اجرا می‌شود).

---

## ۵. لایه D — همترازسازی و تبدیل سیگنال به وزن (`_align`)

این تابع قلب صحت آماری کل سیستم است. گام‌به‌گام:

### D.1 ساخت ایندکس زمانی مشترک

```
merged = np.unique(np.concatenate([idx.asi8 for idx in indexes]))
```
`asi8` نمایش int64 نانوثانیه‌ای است؛ اجتماع روی اعداد صحیح انجام می‌شود نه روی Timestamp. `np.unique` مرتب‌سازی هم می‌کند → O(m log m) با m = مجموع طول ایندکس‌ها.

منطقه‌ی زمانی: اگر همه‌ی نمادها tz یکسان و غیر-None داشتند، نتیجه به همان tz برمی‌گردد؛ در غیر این صورت naive می‌ماند.

### D.2 ماتریس قیمت با دو سیاست ffill

```
close_arr[row_idx, j] = series.values          # جای‌گذاری مستقیم با searchsorted
row_idx = np.searchsorted(dates_i8, series.index.values.view("i8"))
```
`searchsorted` روی آرایه‌ی مرتب int64 یعنی O(n log m) به‌جای join سنگین pandas.

سپس **دو** ماتریس ساخته می‌شود:

```
close_arr     = ffill(limit=ffill_limit)     # نمای معاملاتی / تصمیم‌گیری
close_val_arr = ffill()                      # نمای ارزش‌گذاری، بدون سقف
```
`ffill_limit = 10` اگر بیش از یک بازار در سبد باشد، وگرنه `5`. فلسفه: توقف نماد بیش از ۵ کندل نباید به‌صورت «قیمت زنده» وارد تصمیم شود، ولی برای ارزش‌گذاری پوزیشن باز باید آخرین قیمت معامله‌شده را داشته باشیم.

نمادهایی که تمام ستون‌شان NaN است (بدون هم‌پوشانی با بازه) حذف و لاگ می‌شوند؛ اگر همه حذف شدند → `ValueError`.

### D.3 تبدیل سیگنال به وزن — دقیقاً چهار مرحله

برای هر نماد j روی **تقویم معاملاتی خودِ آن نماد** (نه شبکه‌ی مشترک):

```
(1)  sig ← signal_map[c].reindex(own_idx).values.astype(float64, copy=True)
(2)  np.nan_to_num(sig, copy=False, nan=0.0)          # NaN → 0
(3)  np.clip(sig, -1.0, 1.0, out=sig)                 # کلمپ به [−1,+1]
(4)  shifted[0] = 0.0 ;  shifted[1:] = sig[:-1]       # شیفت یک کندل
```

مرحله‌ی (4) تنها سدّ نگاه‌به‌آینده در کل سیستم است: سیگنالی که از close کندل t ساخته شده، در ردیف t+1 می‌نشیند و در لایه‌ی اجرا روی **open کندل t+1** پر می‌شود.

`copy=True` در (1) عمدی است: با copy-on-write پانداس، آرایه‌ی float64 موجود ممکن است view فقط-خواندنی برگرداند و `nan_to_num(copy=False)` روی آن استثنا می‌دهد.

سپس روی شبکه‌ی مشترک `ffill(limit=ffill_limit)` و `nan_to_num`.

### D.4 نرمال‌سازی نهایی

```
scale[t]    = max(1.0, Σ_j |pos[t,j]|)
weight[t,j] = pos[t,j] / scale[t]
```

این `max(1, ·)` دقیقاً همان جایی است که باگ D1 ما را ساخت: اگر فقط یک نماد سیگنال `1.0` بدهد، `scale = max(1, 1) = 1` و وزنش **۱.۰ یعنی ۱۰۰٪ کل سرمایه** می‌ماند. نرمال‌سازی فقط از فراتر رفتن مجموع از ۱۰۰٪ جلوگیری می‌کند، نه از تمرکز.

با سایزینگ `1/N` مجموع همیشه `≤ 1` است، پس `scale ≡ 1` و وزن‌ها دست‌نخورده از فیلتر رد می‌شوند.

### D.5 برش warm-up

```
warmup_end = evaluation_start_index(config, dates)
dates, close_df, close_val_df, target_pos, ret_df ← همه [warmup_end:]
```
`evaluation_start_index` یا `warmup_bars` (عدد) یا `evaluation_start_date` (تاریخ، با `np.searchsorted(..., side="left")`) را می‌خواند و **اعلام هم‌زمان هر دو را رد می‌کند** (ValueError) چون می‌توانند با هم ناسازگار باشند. اگر پنجره‌ی باقی‌مانده کمتر از ۲ کندل شود هم ValueError.

نکته: سیگنال‌ها **قبل از** برش و روی کل داده‌ی بارگذاری‌شده ساخته می‌شوند؛ پس اولین کندلِ ارزیابی‌شده اندیکاتور کاملاً گرم دارد. این دقیقاً مکانیزم اصلاح D2 ماست.

---

## ۶. لایه E — موتور اجرا (`_execute_bars`)

### E.1 متغیرهای حالت

```
self.capital            : float                  # نقد آزاد
self.positions          : Dict[str, Position]    # فقط پوزیشن‌های باز
self.trades             : List[TradeRecord]
self.equity_snapshots   : List[EquitySnapshot]
self.plan_rejections    : Counter[(symbol, reason)]
self._bar_idx           : int                    # برای holding_bars
self._close_arr         : np.ndarray             # کش برای searchها
```

### E.2 ترتیب دقیق عملیات در هر کندل

حروف a تا e مطابق کامنت‌های خود سورس:

```
برای i, ts در enumerate(dates):
    self._bar_idx ← i
    stop_run ← before_rebalance_bar(ts, ...)        # کریپتو: فاندینگ + چک لیکویید
    execute_targets ← (execution_dates is None) or (ts in execution_dates)

    # ── a. ارزش‌گذاری دفتر با قیمت‌های قابل‌مشاهده در لحظه‌ی اجرا
    equity ← _calc_open_equity(data_map, close_df, ts)
    #   عمداً open است نه close: استفاده از close همان کندل یعنی
    #   اجازه دادن به عددی که هنوز رخ نداده تا اندازه‌ی سفارش را تعیین کند
    target_weights ← { c: target_pos[i, col[c]] }   # None اگر stop_run

    اگر position_adjustment == "rebalance":
        _execute_target_rebalance(...)              # تغییر اندازه‌ی پوزیشن‌های موجود
        target_weights ← {}                         # مسیر hold غیرفعال
    وگرنه:
        _record_dropped_target_adjustments(...)     # فقط لاگ: «resize نادیده گرفته شد»

    # ── b. اول آزادسازی سرمایه، بعد باز کردن
    برای c در codes:
        اگر پوزیشن باز دارد و جهت هدف صفر یا مخالف است:
            _rebalance(c, 0.0, ...)                 # بستن کامل
    #   چرا جدا: یک پاس مخلوطِ بستن/بازکردن، نتیجه را به ترتیب
    #   پیمایش نمادها وابسته می‌کرد

    # ── c. قیمت‌گذاری همه‌ی سفارش‌های بازکننده، سپس commit اتمی
    open_targets ← [(c, w, frame) برای نمادهای بدون پوزیشن با جهت غیرصفر]
    planned ← _plans(1.0)
    اگر Σ order.cost > capital + 1e-9:
        # جست‌وجوی دودویی روی ضریب مقیاس مشترک، ۵۰ تکرار
        low, high ← 0.0, 1.0
        ۵۰ بار:
            mid ← (low+high)/2
            candidate ← _plans(mid)
            اگر Σ candidate.cost ≤ capital + 1e-9:  low, planned ← mid, candidate
            وگرنه:                                   high ← mid
    برای order در planned: _execute_open_order(order, ts)

    # ── d. هوک‌های پس از اجرا
    stop_run ← after_rebalance_bar(ts, ...)         # کریپتو: فاندینگ + لیکوییدیشن

    # ── e. ثبت snapshot
    snap_equity ← _calc_equity(close_df, ts)        # اینجا close مجاز است
    equity_snapshots.append(EquitySnapshot(ts, capital, unrealized, snap_equity, len(positions)))
```

مقیاس مشترک در گام (c) عمدی است: کلیپ کردن ترتیبیِ نقدینگی، نماد اولِ لیست را در اولویت می‌گذاشت؛ ضریب مشترک نسبت‌های سبد را حفظ می‌کند.

### E.3 قیمت‌گذاری یک سفارش بازکننده (`_plan_open_order`)

```
direction ← +1 اگر w > 1e-9 ، −1 اگر w < −1e-9 ، وگرنه 0
اگر direction == 0            → reject("no_target_weight")
اگر symbol در positions       → reject("already_held")        # در حالت hold
اگر frame is None             → reject("no_data")
اگر ts در ایندکس نیست         → reject("no_bar")
اگر not can_execute(...)      → reject("execution_blocked")
open_price ← execution_open(bar) = bar.get("open", bar.get("close", 0))
اگر open_price == 0           → reject("invalid_price")
price     ← open_price · (1 + direction · slippage_rate)
leverage  ← _leverage_for_symbol(symbol)
notional  ← |w| · equity · leverage
raw_size  ← notional / |price|
size      ← round(max(raw_size,0), 6)              # قاعده‌ی لات کریپتو
اگر size ≤ 0                  → reject("zero_size")
margin    ← size · |price| / leverage
comm      ← size · price · rate      rate = taker اگر is_open وگرنه maker
return _OpenOrder(...);   cost ≡ margin + comm
```

`plan_rejections` یک `Counter` روی `(symbol, reason)` است و در متریک‌ها به `unfilled_plan_rejections` تبدیل می‌شود — ولی فقط دلایل «می‌خواستم و نشد» شمرده می‌شوند (`no_data`, `no_bar`, `execution_blocked`, `invalid_price`, `zero_size`)، نه `no_target_weight` و `already_held`.

### E.4 معادلات حسابداری نقد

```
باز کردن:      capital ← capital − margin − commission
افزایش:        capital ← capital − Δmargin − commission
کاهش جزئی:     capital ← capital + released_margin + realized_pnl − exit_commission
بستن کامل:     capital ← capital + margin + pnl − exit_commission

pnl        = direction · size · (exit_price − entry_price)
unrealized = direction · size · (mark_price − entry_price)
equity     = capital + Σ margin_i + Σ unrealized_i
```

### E.5 مکانیزم دقیق کرشی که در حالت خام دیدیم

این را روی داده‌ی واقعی بازتولید کردیم؛ زنجیره‌ی علّی دقیقاً این است:

```
۱) نماد A سیگنال 1.0 می‌دهد، تنها سیگنال زنده است
   → scale = max(1, 1.0) = 1  →  وزن ۱.۰  →  notional = ۱۰۰٪ equity
   → margin ≈ کل سرمایه،  capital ← ≈ 0

۲) چند کندل بعد نماد B هم لانگ می‌شود
   → هدف هرکدام 0.5 ؛ ولی position_adjustment پیش‌فرض "hold" است
   → موتور A را کوچک نمی‌کند، فقط لاگ می‌زند:
     "dropped a resize: A asked for weight 0.5 (was 1.0)"
   → capital همچنان ≈ 0

۳) B وارد open_targets می‌شود. Σcost > capital → جست‌وجوی دودویی
   → با capital ≈ 0، حتی mid → 0 هم هزینه‌ی مثبت می‌سازد
     (round_size کف 1e-6 واحد دارد و کارمزد هم صفر نمی‌شود)
   → هیچ candidate ای شرط را پاس نمی‌کند

۴) و اینجا نقص واقعی است: در حلقه، `planned` فقط داخل شاخه‌ی
   موفق بازنویسی می‌شود. اگر هیچ mid ای جواب ندهد، `planned`
   همان _plans(1.0)ِ نشدنی باقی می‌ماند.

۵) _execute_open_order(order):  if order.cost > capital + 1e-7:
       raise RuntimeError("planned order for B exceeds available capital")
   → کل ران می‌میرد، هیچ artifact ای نوشته نمی‌شود
```

دو نتیجه‌گیری جدا: (الف) باگ **ما** سایزینگ `1.0` به‌جای `1/N` بود؛ (ب) یک نقص **بالادستی** هم هست — وقتی هیچ مقیاسی جا نمی‌شود، رفتار درست `planned = []` (رد کردن بازکردن‌های نشدنی، مطابق همان سیاست `plan_rejections`) است نه پرتاب استثنا و کشتن ران. با `1/N` هرگز به این مسیر نمی‌رسیم چون `Σ|w| ≤ 1`.

### E.6 هوک‌های کریپتو در هر کندل

```
on_bar(symbol, bar, ts):
    fee ← calc_crypto_funding_fee(...)        # هر ۸ ساعت: 00/08/16 UTC
    capital ← capital − fee
    اگر check_crypto_liquidation(symbol, bar, positions):
        liq_price ← apply_slippage(_liquidation_mark(bar, pos), −pos.direction)
        _close_position(symbol, liq_price, ts, "liquidation")
```
قیمت پرشدن لیکوییدیشن همان mark نامساعدی است که خود چک از آن استفاده کرده — تا wick هرگز به قیمت بهتری از صرافی خارج نشود. در بک‌تست‌های ما `leverage=1` بود، پس این مسیر عملاً فعال نشد.

---

## ۷. لایه F — متریک‌ها (`calc_metrics`)

```
n    = len(equity_curve)
bpy  = bars_per_year  (یا effective_bars_per_year اگر None)
r[t] = equity.pct_change().fillna(0)

total_return  = equity[-1]/initial_cash − 1
growth        = 1 + total_return
annual_return = −1.0                      اگر growth ≤ 0        # ورشکستگی کامل
              = growth^(bpy/max(n,1)) − 1  در غیر این صورت
              = +inf                       اگر OverflowError

vol     = std(r, ddof=1)   اگر n>1 و همه‌ی r متناهی، وگرنه 0
sharpe  = mean(r)/(vol + 1e-10) · √bpy     ؛ اگر غیرمتناهی → 0

peak[t] = max(cummax(equity)[t], initial_cash)     # ← کف روی سرمایه‌ی اولیه
dd[t]   = (equity[t] − peak[t]) / peak[t]
max_dd  = min(dd)

calmar  = annual_return / |max_dd|         اگر |max_dd| > 1e-10 وگرنه 0
sortino = mean(r)/(std(r[r<0], ddof=1) + 1e-10) · √bpy
turnover[t] = 0.5 · Σ_j |w[t,j] − w[t−1,j]|
```

سه محافظ که ارزش دانستن دارند:

- `+1e-10` در مخرج‌ها فقط ضد تقسیم-بر-صفر است؛ چون صورت هم آن‌جا کوچک است، جواب حدی معقول می‌ماند.
- کلمپ `peak` روی `initial_cash` یعنی ضرر همان کندل اول هم به‌عنوان drawdown دیده می‌شود؛ بدون آن، peak اولیه برابر equity کندل اول می‌شد و افت اولیه پنهان می‌ماند.
- `bar_returns` (که برای بازده هر نماد استفاده می‌شود، نه equity) بازده را فقط وقتی تعریف می‌کند که قیمت قبلی **متناهی و اکیداً مثبت** باشد؛ در غیر این صورت `0.0` با یک warning. این برای ابزارهایی مثل برق روزانه‌ی اروپا با قیمت منفی است، نه کریپتو — ولی همان مسیر برای ما هم اجرا می‌شود.

جدول سالانه‌سازی برای نوبیتکس/والکس: `trading_days = 365`، و `bars_per_day` از `{1m:1440, 5m:288, 15m:96, 30m:48, 1H:24, 4H:6, 1D:1}`؛ حاصل‌ضرب می‌شود `bpy`.

---

## ۸. لایه G — اسکنر واچ‌لیست

### G.1 تشخیص «چند کندل از آخرین تغییر جهت»

```python
valid    = long_state[fast_ma.notna() & slow_ma.notna()]
flipped  = valid != valid.shift(1)
flip_idx = np.where(flipped.to_numpy())[0]
bars_since = int(len(valid) - 1 - flip_idx[-1])
```

جزئیات ظریفی که تجربی تأیید شد: `valid.shift(1)` سری بولی را به dtype=object با `NaN` در ردیف صفر تبدیل می‌کند، و در pandas مقایسه‌ی `True != NaN` نتیجه‌اش `True` است. پس **ایندکس صفر همیشه به‌عنوان flip شمرده می‌شود** و `flip_idx` هرگز خالی نیست. دو پیامد:

- شاخه‌ی `else len(valid)` در کد **کد مرده** است (هرگز اجرا نمی‌شود).
- برای سری‌ای که هیچ‌وقت تغییر جهت نداده، جواب `n−1` می‌شود که معنای درستی دارد: «در تمام تاریخچه در همین حالت بوده». یعنی این quirk تصادفاً نتیجه‌ی درست می‌دهد؛ ولی تکیه‌ی ناخواسته بر آن شکننده است و باید صریح شود.

### G.2 انتخاب کارنامه‌ی حاکم

```
governing = long_short_metrics   اگر direction == "SHORT"
          = long_only_metrics    اگر direction == "LONG"
```
منطق: بک‌تست لانگ-اونلی هرگز سمت شورت را نگرفته، پس درباره‌ی آن **هیچ حرفی ندارد**. یک سیگنال شورت زنده فقط با کارنامه‌ی نسخه‌ی متقارن قابل ارزیابی است.

### G.3 سقف اهرم و فاصله تا لیکوییدیشن

```
dd        = |governing.max_drawdown|
raw_lev   = DD_BUDGET / dd            با DD_BUDGET = 0.50
breached  = (raw_lev < 1.0)           # حتی بدون اهرم هم بودجه را می‌شکند
max_lev   = round(min(5.0, max(raw_lev, 1.0)), 1)
liq_atrs  = (100 / max_lev) / atr14_pct
```

`liq_atrs` یک تقریب سرانگشتی است: در مارجین ایزوله لیکوییدیشن نزدیک حرکت نامساعد `1/L` است، و تقسیم بر ATR روزانه می‌گوید «چند حرکت روزانه‌ی متعارف تا لیکویید فاصله داریم». کارمزد، بهره‌ی وام و نرخ نگه‌داری در آن نیست.

کلمپ به `max(raw_lev, 1.0)` عمدی است: عدد زیر ۱ «اهرم» نیست، یعنی بودجه‌ی ریسک حتی پوزیشن نقدی را هم رد می‌کند — و آن حالت با پرچم `breached` جدا گزارش می‌شود نه با چاپ «0.7x».

### G.4 دروازه‌ی حکم

```
gov_sharpe ≥ 0.5   → "watch {direction}"
0 < gov_sharpe < 0.5 → "weak"
gov_sharpe ≤ 0     → "no edge"
None               → "no data"
```
مرتب‌سازی نهایی نزولی روی `ls_sharpe` با کلید جایگزین `−9` برای `None`.

---

## ۹. لایه H — ارکستراسیون

### H.1 قرارداد `run_dir`

```
<run_dir>/
├── config.json                 # ورودی، اعتبارسنجی با BacktestConfigSchema
├── code/signal_engine.py       # ورودی، کلاس SignalEngine
├── run_card.md / run_card.json # خروجی، شامل config_hash و strategy_hash
└── artifacts/
    ├── metrics.csv             # ۳۵ ستون
    ├── equity.csv              # منحنی equity کندل‌به‌کندل
    ├── trades.csv, fills.jsonl
    ├── positions.csv, target_positions.csv
    ├── ohlcv_<SYMBOL>.csv      # داده‌ی خام همان‌طور که موتور دید
    └── risk_xray.json/md, rebalance_notes.json/md
```

`safe_run_dir` مسیر را به ریشه‌های مجاز محدود می‌کند (`~/.vibe-trading/runs`, `<cwd>/runs`, … به‌علاوه‌ی `VIBE_TRADING_ALLOWED_RUN_ROOTS`) — تا `python -m backtest.runner /any/path` نتواند کد دلخواه import کند.

دو هش بازتولیدپذیری در run_card: `config_hash` و `strategy_hash` (SHA-256 روی محتوای کانفیگ و فایل استراتژی).

### H.2 محیط اجرا

سندباکس این نشست به `apiv2.nobitex.ir` دسترسی ندارد (سیاست egress سازمانی، ۴۰۳ روی CONNECT). پس مسیر داده‌ی واقعی، یک workflow دستی روی GitHub Actions است:

```
workflow_dispatch → ubuntu-latest → pip install vibe-trading-ai
  → python run_on_github.py        (چهار استراتژی، تک‌نماد)
  → python run_five_symbols.py     (raw در برابر debugged)
  → python live_watchlist.py       (اسکن ۱۵ نماد)
  → upload-artifact (retention: ۱ روز)
```
نکته‌ی مکانیکی گیت‌هاب: برای dispatch شدن از طریق API، فایل workflow باید روی برنچ **پیش‌فرض** وجود داشته باشد، ولی نسخه‌ای که اجرا می‌شود از `ref` درخواستی خوانده می‌شود. برای همین فایل یک‌بار روی `main` نشست و بعد از آن ویرایش‌ها فقط روی برنچ کاری انجام شد.

---

## ۱۰. فهرست ناوردایی‌ها و حالت‌های مرزی

| # | ناوردایی / حالت مرزی | جایی که تضمین می‌شود |
|---|---|---|
| 1 | هیچ سیگنالی نمی‌تواند اطلاعات کندل جاری را ببیند | `shift(1)` در `_align` گام D.3(4) |
| 2 | `Σ_j |w[t,j]| ≤ 1` | نرمال‌سازی D.4 |
| 3 | اندازه‌ی پوزیشن همیشه مثبت؛ جهت جداگانه حمل می‌شود | `_calc_raw_size` با `abs(price)` |
| 4 | مارجین با قیمت منفی هم مثبت می‌ماند | `size·abs(price)/leverage` |
| 5 | تقسیم بر صفر در RSI → RSI=100 نه inf | `replace(0,NaN)` + `fillna(100)` |
| 6 | بازده وقتی قیمت قبلی ≤ 0 است تعریف نشده → 0.0 با warning | `bar_returns` |
| 7 | نمونه‌ی تک‌مشاهده‌ای Sharpe را NaN نمی‌کند | گارد `len(r) > 1` قبل از `std(ddof=1)` |
| 8 | افت کندل اول در drawdown دیده می‌شود | `cummax(...).clip(lower=initial_cash)` |
| 9 | توقف طولانی نماد وارد تصمیم نمی‌شود ولی ارزش‌گذاری را خراب نمی‌کند | دو ماتریس `close_arr` / `close_val_arr` |
| 10 | تایم‌فریم پشتیبانی‌نشده داده‌ی اشتباه‌لیبل تولید نمی‌کند | بازگشت `{}` از لودر، نه fallback بی‌صدا |
| 11 | صفحه‌بندی تکراری‌ها را دوباره نمی‌شمارد | `~index.duplicated(keep="last")` |
| 12 | اعلام هم‌زمان `warmup_bars` و `evaluation_start_date` رد می‌شود | `evaluation_start_index` |
| 13 | یک نماد خراب کل batch را نمی‌کشد | `try/except` دور هر نماد در `fetch` |
| 14 | ‏(نقض‌شده) سبد نشدنی باید رد شود نه استثنا | **ندارد** — بخش E.5 |

---

## ۱۱. جدول پیچیدگی

با n = تعداد کندل، k = تعداد نماد، m = مجموع طول ایندکس‌ها، P = تعداد صفحه:

| عملیات | زمان | حافظه |
|---|---|---|
| دریافت یک نماد | O(P·B) + تأخیر شبکه | O(n) |
| SMA / RSI / ATR | O(n) هرکدام | O(n) |
| ساخت ایندکس مشترک | O(m log m) | O(m) |
| نگاشت `searchsorted` | O(n log m) per symbol | O(n·k) |
| ffill برداری | O(n·k) | O(n·k) |
| حلقه‌ی اجرای کندل‌ها | O(n·k) میانگین | O(n + trades) |
| جست‌وجوی دودویی نقدینگی | O(50·k) در بدترین کندل | O(k) |
| `calc_metrics` | O(n + T) با T=تعداد معامله | O(n) |
| اسکن واچ‌لیست (۱۵ نماد، ۲ حالت) | ۳۰ بک‌تست ≈ ۴۰ ثانیه‌ی واقعی | O(n·k) |

گلوگاه واقعی شبکه است نه محاسبه: در run #3، ۴۰ ثانیه از ۱۲۶ ثانیه‌ی کل job صرف اسکن شد که بیشترش انتظار HTTP و `sleep(0.5)` بین صفحات بود.

---

## ۱۲. محدودیت‌های شناخته‌شده

1. **کارمزدها فرض‌اند.** `0.25%` هر سمت + `0.1%` اسلیپیج، فرض محافظه‌کارانه برای دفتر سفارش تومانی است، نه جدول رسمی نوبیتکس.
2. **عمق دفتر سفارش مدل نشده.** موتور فرض می‌کند کل سفارش در قیمت open ± اسلیپیج ثابت پر می‌شود. برای نمادهای کم‌حجم تومانی این خوش‌بینانه است.
3. **بک‌تست اسپات با `leverage=1`.** ستون اهرم در واچ‌لیست یک محاسبه‌ی بودجه‌ی ریسک روی خروجی همان بک‌تست بدون اهرم است، نه شبیه‌سازی معامله‌ی اهرمی با بهره و فاندینگ.
4. **بذر RSI با وایلدر کلاسیک یکی نیست** (بخش B.2) — روی پنجره‌های کوتاه‌تر از ≈۵N کندل قابل‌توجه می‌شود.
5. **کد مرده در `bars_since_flip`** (بخش G.1) — درست کار می‌کند ولی به‌طور ناخواسته به رفتار مقایسه‌ی `bool != NaN` وابسته است.
6. **`_plans` بالادستی در حالت نشدنی استثنا می‌دهد** (بخش E.5) — با سایزینگ `1/N` دور زده شده، ولی خودِ نقص سر جایش است.

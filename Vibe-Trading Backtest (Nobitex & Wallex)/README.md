# بک‌تست معاملاتی با Vibe-Trading (با پشتیبانی نوبیتکس و والکس)

این پوشه راهنمای نصب و استفاده از پروژه متن‌باز [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) است؛ یک ایجنت معاملاتی مبتنی بر LLM که علاوه بر بک‌تست روی بازارهای جهانی (سهام آمریکا/چین/هند/کره/...، فارکس، فیوچرز)، از دو صرافی ایرانی **نوبیتکس (Nobitex)** و **والکس (Wallex)** هم به‌عنوان منبع داده (Data Source) برای جفت‌ارزهای تومانی پشتیبانی می‌کند.

> توجه: Vibe-Trading یک پکیج پایتون آماده روی PyPI است (`vibe-trading-ai`)؛ اینجا خودِ کد آن بازنویسی نشده، بلکه نحوه‌ی نصب، پیکربندی و اجرای دقیق آن — با تمرکز روی نوبیتکس/والکس — مستند شده تا مثل بقیه‌ی پروژه‌های این ریپو قابل اجرا و تکرار باشد.

## این ابزار چه‌کاری انجام می‌دهد؟

- یک ایجنت هوش مصنوعی (مبتنی بر Claude/GPT/DeepSeek/... یا مدل‌های لوکال با Ollama) که با زبان طبیعی درخواست شما را می‌گیرد (مثلاً «یک استراتژی میانگین متحرک روی BTCIRT بک‌تست کن») و خودش داده می‌گیرد، بک‌تست می‌زند و گزارش (شارپ، افت سرمایه، منحنی equity و ...) برمی‌گرداند.
- بیش از ۲۷ منبع داده‌ی بازار، با فال‌بک خودکار برای اکثر بازارها. **نوبیتکس و والکس** چون فقط جفت‌ارز تومانی (نه دلاری) می‌دهند، عمداً در فال‌بک خودکار قرار نگرفته‌اند و باید صریحاً به‌عنوان `source` انتخاب شوند (تا داده‌ی تومانی با یک سری دلاری قاطی نشود).
- هر دو منبع، **عمومی و بدون نیاز به API Key** هستند (فقط داده‌ی تاریخی/کندل می‌خوانند؛ امکان سفارش‌گذاری زنده روی این دو صرافی وجود ندارد).

## پیش‌نیازها

- Python 3.11 به بالا
- یک API Key از یک ارائه‌دهنده‌ی LLM (Anthropic، OpenAI، DeepSeek، OpenRouter، Gemini، Groq و ...) — یا اجرای کاملاً لوکال و رایگان با [Ollama](https://ollama.com) (بدون نیاز به کلید)
- (اختیاری) Docker، اگر می‌خواهید بدون نصب لوکال اجرا کنید

## نصب

### روش سریع (pip)

```bash
pip install vibe-trading-ai
vibe-trading init              # تنظیم تعاملی فایل .env (انتخاب provider و مدل LLM)
```

### روش Docker (بدون نیاز به نصب پایتون)

```bash
git clone https://github.com/HKUDS/Vibe-Trading.git
cd Vibe-Trading
cp agent/.env.example agent/.env
# فایل agent/.env را باز کنید و بلاک provider مورد نظر (مثلاً Anthropic یا DeepSeek) را از حالت کامنت خارج کرده و کلید API را وارد کنید
docker compose up --build
```
سپس در مرورگر `http://localhost:8899` را باز کنید.

### روش نصب لوکال از سورس (برای توسعه)

```bash
git clone https://github.com/HKUDS/Vibe-Trading.git
cd Vibe-Trading
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp agent/.env.example agent/.env   # ویرایش و تنظیم کلید LLM
vibe-trading                       # اجرای رابط تعاملی (TUI)
```

## تنظیم کلید LLM

فایل `agent/.env` را باز کنید و یکی از بلاک‌های provider را از حالت کامنت خارج کنید، برای مثال برای Anthropic:

```dotenv
LANGCHAIN_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LANGCHAIN_MODEL_NAME=claude-sonnet-5
```

اگر نمی‌خواهید برای مدل هزینه کنید، `LANGCHAIN_PROVIDER=ollama` را انتخاب کرده و یک مدل لوکال (با `ollama pull`) نصب کنید — نیازی به کلید نیست.

مهم: برای اینکه ایجنت واقعاً از ابزارهای بک‌تست/دیتا استفاده کند (نه اینکه از حافظه‌ی خودش جواب بسازد)، از مدل‌های قوی در «Tool Calling» استفاده کنید (مثل `claude-sonnet-5`، `deepseek-v4-pro`، `gpt-5.5`)؛ از مدل‌های سبک/nano برای این کار استفاده نکنید.

## اجرای اولین بک‌تست روی نوبیتکس/والکس

نوبیتکس و والکس **explicit-only** هستند؛ یعنی باید نام منبع را صراحتاً در پرامپت یا در `config.json` مشخص کنید.

### از طریق گفتگو با ایجنت (ساده‌ترین راه)

```bash
vibe-trading run -p "با استفاده از منبع نوبیتکس (nobitex)، یک استراتژی کراس میانگین متحرک ۲۰/۵۰ روی BTCIRT در یک سال گذشته بک‌تست کن و شارپ و بیشترین افت سرمایه را نشان بده"
```

```bash
vibe-trading run -p "Use the wallex data source to backtest an RSI(14) mean-reversion strategy on USDT-TMN over the last 6 months, 1h candles"
```

### از طریق فایل `config.json` (کنترل دقیق‌تر)

نمونه‌ها در پوشه‌ی [`examples/`](./examples) قرار دارند:

- [`examples/config_nobitex_btc.json`](./examples/config_nobitex_btc.json) — بک‌تست BTCIRT روی نوبیتکس
- [`examples/config_wallex_usdt.json`](./examples/config_wallex_usdt.json) — بک‌تست USDT-TMN روی والکس

اجرا:

```bash
vibe-trading run -p "Run the backtest defined in config.json"
```
(یا مسیر فایل کانفیگ را در پرامپت مشخص کنید — ایجنت آن را می‌خواند و اجرا می‌کند.)

## جزئیات فنی منابع داده

### نوبیتکس (Nobitex)

| مورد | مقدار |
|---|---|
| Endpoint | `GET https://apiv2.nobitex.ir/market/udf/history` |
| احراز هویت | ندارد (Public) |
| فرمت نماد | جفت‌ارز به تومان/ریال، مثل `BTCIRT`، `USDTIRT` |
| تایم‌فریم‌های پشتیبانی‌شده | `1m, 5m, 15m, 30m, 1h, 3h, 4h, 6h, 12h, 1d` |
| محدودیت نرخ | ۶۰ درخواست در دقیقه |
| هر درخواست | حداکثر ۵۰۰ کندل (با صفحه‌بندی/pagination خودکار) |
| منطقه زمانی | تهران (UTC+03:30) |
| متغیرهای محیطی اختیاری | `NOBITEX_TIMEOUT_S` (پیش‌فرض ۲۰)، `NOBITEX_FETCH_BUDGET_S` (پیش‌فرض ۹۰)، `NOBITEX_PROBE_TIMEOUT_S` (پیش‌فرض ۸) |

### والکس (Wallex)

| مورد | مقدار |
|---|---|
| Endpoint | `GET https://api.wallex.ir/v1/udf/history` |
| احراز هویت | ندارد (Public) |
| فرمت نماد | چند فرمت پذیرفته می‌شود و به‌صورت خودکار نرمال‌سازی می‌گردد: `USDT-TMN`, `USDTTMN`, `usdttmn` |
| تایم‌فریم‌های واقعاً پشتیبانی‌شده | فقط `1m`، `1h`، `1d` (بقیه‌ی بازه‌ها نتیجه‌ی خالی برمی‌گردانند تا داده‌ی اشتباه لیبل نخورد) |
| محدودیت نرخ | حدود ۶۰۰ درخواست در هر دوره‌ی rate-limit |
| پنجره‌ی هر درخواست | ۱ دقیقه‌ای: تا ۲۰ روز · ۱ ساعته: تا ۲ سال · روزانه: تا ۴۰ سال |
| متغیرهای محیطی اختیاری | `WALLEX_TIMEOUT_S` (پیش‌فرض ۲۰)، `WALLEX_FETCH_BUDGET_S` (پیش‌فرض ۹۰)، `WALLEX_PROBE_TIMEOUT_S` (پیش‌فرض ۸) |

## چند دستور مفید دیگر CLI

```bash
vibe-trading                        # رابط تعاملی (TUI)
vibe-trading serve --port 8899      # اجرای وب‌سرور (رابط کاربری تحت وب)
vibe-trading --pine <run_id>        # خروجی گرفتن استراتژی به فرمت Pine Script برای TradingView
vibe-trading alpha list             # مرور ۴۶۲ فاکتور آماده (Alpha Zoo) برای تحقیق کمّی
vibe-trading provider doctor        # عیب‌یابی اتصال به provider مدل زبانی
```

## نکات مهم

- نوبیتکس و والکس فقط **داده‌ی تاریخی برای بک‌تست** می‌دهند؛ معامله‌ی زنده (Live Trading) روی این دو صرافی در Vibe-Trading پیاده‌سازی نشده است.
- چون این دو منبع «توماني» هستند و در زنجیره‌ی فال‌بک خودکار کریپتو (`okx` → `ccxt` → `binance` → ...) قرار نمی‌گیرند، همیشه باید صریحاً انتخاب شوند تا داده‌ی دلاری به‌اشتباه جای داده‌ی تومانی ننشیند.
- کل تنظیمات و تاریخچه‌ی اجراها در `~/.vibe-trading/` ذخیره می‌شود (قابل جابه‌جایی با متغیر محیطی `VIBE_TRADING_HOME`).

## اجرای واقعیِ موتور روی نوبیتکس (نمونه‌ی گزارش پرفورمنس)

پکیج واقعی (`vibe-trading-ai==0.1.15`) نصب و روی داده‌ی BTCIRT در ۴ حالت استراتژی (Buy&Hold، دو نوع MA Crossover، RSI Mean-Reversion) اجرا شد تا خروجی واقعی موتور دیده شود. **مهم:** به‌دلیل سیاست شبکه‌ی این محیط sandbox، اتصال زنده به `apiv2.nobitex.ir` مسدود است؛ برای اجرای واقعی، فقط لایه‌ی HTTP لودر با داده‌ی synthetic (نه قیمت واقعی بازار) mock شد و بقیه‌ی کد (لودر/موتور/متریک) کاملاً بدون تغییر اجرا شده. جزئیات کامل افشا، جدول مقایسه‌ی ۴ حالت، و دستور اجرای همین آزمایش با داده‌ی واقعی نوبیتکس (روی ماشینی با اینترنت آزاد) در [`local_run_demo/RESULTS.md`](./local_run_demo/RESULTS.md).

## الگوریتم داخلی و فرمول‌ها

برای جزئیات فنی موتور بک‌تست — نمودار جریان داده بین ماژول‌ها، ورودی/خروجی دقیق هر تابع، مدل‌های داده و همه‌ی فرمول‌های ریاضی (تبدیل سیگنال به وزن پوزیشن، اسلیپیج، کارمزد، مارجین، PnL، Sharpe/Sortino/Calmar/Max-Drawdown/Turnover/Information-Ratio و سالانه‌سازی مخصوص بازار ۲۴/۷ کریپتو) — به سند جداگانه‌ی [`ALGORITHM.md`](./ALGORITHM.md) مراجعه کنید؛ این سند مستقیماً از خواندن سورس‌کد واقعی موتور (`engines/base.py`, `engines/crypto.py`, `metrics.py`, `loaders/nobitex.py`, `loaders/wallex.py`) استخراج شده است.

## منابع

- ریپوی اصلی: https://github.com/HKUDS/Vibe-Trading
- مستندات کامل نصب/CLI/متغیرهای محیطی: بخش README همان ریپو

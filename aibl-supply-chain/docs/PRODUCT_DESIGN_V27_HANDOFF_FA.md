# GSI V27 — Product Design Handoff

## مرجع‌ها

- Figma: https://www.figma.com/design/v3FIHcKem4vqZoZwcDWdZ2
- HTML demo: `../examples/GSI_V27_UI_SAMPLE.html`
- Runtime tokens: `gsi/design/tokens.py`
- CSS contract: `gsi/design/css.py`
- Machine-readable handoff: `python -m gsi.design.handoff --json`

## معماری تجربه

چهار Audience اصلی تعریف شده‌اند: کارشناس، مدیر میانی، مدیر ارشد و تحلیل‌گر. Progressive Disclosure اصل مرکزی است؛ عمق اطلاعات با نیاز نقش تغییر می‌کند ولی Truth Model یکی است.

## صفحه کلیدی Case Detail

Case Detail نقطه اتصال Timeline، Deadline، Money Flow، Inventory/Reconciliation، Evidence، Rule Basis و Case Recommendation است. ترخیص فیزیکی و ارائه/تطبیق سند بانکی دو Event مستقل‌اند.

## موجودی

سه سبد نزد سازنده، در راه و گمرک از سورس کارشناسان می‌آیند. Oracle نقش کنترل/تجمیع موجودی IKCO/SAPCO و نیاز روزانه دارد. Blank/null به صفر تبدیل نمی‌شود.

## Case Recommendation

Recommendation خروجی Human-in-the-loop است: پیشنهاد → دلیل/Evidence/Rule Basis → Review/Edit → Draft Email. ارسال خودکار پیش‌فرض خاموش است. Signal بدون Evidence به Fraud Finding تبدیل نمی‌شود.

## Responsive

- Desktop 1440: Sidebar ثابت، جدول و Timeline کامل.
- Tablet 768: Sidebar به Drawer، کارت‌ها دو ستونه و Timeline قابل Scroll.
- Mobile 390: Action Queue اولویت اول، Table به Card List و CTA اصلی نزدیک thumb zone.

## Accessibility

رنگ تنها حامل معنا نیست، Focus مستقل از Hover است، targetهای اصلی حداقل 44px طراحی شده‌اند و Error باید راه اصلاح را نیز توضیح دهد. تست واقعی NVDA/VoiceOver در UAT سازمانی هنوز لازم است.

## مرزبندی تحویل

Figma/HTML مشخصات Product UI هستند؛ اتصال Production و صحت داده سازمانی باید در UAT روی Snapshot واقعی تأیید شود.

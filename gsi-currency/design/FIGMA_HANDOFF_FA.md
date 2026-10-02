# Design Handoff نهایی GSI

مرجع طراحی زنده: `T9Ps72EYpriHdov9fmNFQu` / `GSI Foundations / Persian refinement 1.1` / node `3:2`.

`pm_ui/tokens.py` و `gsi/design/tokens.py` باید مصرف‌کننده Foundations باشند، نه منبع مستقل تصمیم. در ۲۰۲۶-۰۹-۲۵ رنگ‌های Surface/Navy/Teal/Gold، spacing، radius و type ramp با فایل زنده تطبیق داده شدند.

فونت طراحی IRANSansWeb است؛ متن فارسی letter-spacing=0 و RTL است. شناسه لاتین باید LTR/`unicode-bidi: plaintext` بماند. از دور سوم، برنامه اول راوی را به کار می‌برد و اگر نبود ایران‌سنس؛ فایل Figma هنوز IRANSansWeb دارد. فایل‌های مجوزدار سازمان در `assets/fonts` هستند (راهنما: `assets/fonts/README_FA.md`).

ساختار محصول: «وضعیت و اقدام»، «مسیر فرآیند»، «تحویل بین واحدها». هر سه View باید Scope و Reference Time مشترک داشته باشند و منبع/ردیف شاهد در Detail قابل دسترسی بماند. Missing هرگز صفر نیست.

HTML مرورگر و Outlook دو renderer متفاوت‌اند: Browser می‌تواند SVG داشته باشد؛ Email عمداً به Table ساده کاهش می‌یابد. هر دو از Facts یکسان تغذیه می‌شوند.

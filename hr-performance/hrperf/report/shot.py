# -*- coding: utf-8 -*-
"""HTML → PNG، با هر مرورگری که این دستگاه دارد.

## چرا این فایل وجود دارد

پوستر برای چاپ و برای فرستادن در پیام‌رسان، **تصویر** می‌خواهد نه HTML.
ولی هیچ کتابخانهٔ پایتونی نمی‌تواند این صفحه را درست رندر کند: فونت
ایران‌سنس، راست‌به‌چپ، ``container query``، ``mix-blend-mode`` و
``feTurbulence`` همه موتور مرورگر می‌خواهند. پس به‌جای یک رندرِ تقریبی،
از خودِ مرورگرِ همان دستگاه استفاده می‌کنیم.

سه راه، به ترتیب اولویت — اولی که جواب داد، برنده است:

1. **Playwright** اگر نصب باشد. دقیق‌ترین، چون ``deviceScaleFactor`` و
   انتظار برای بارگذاری فونت را کنترل می‌کند.
2. **کروم/کرومیوم در حالت headless** با ``--screenshot``. روی مک و
   ویندوز تقریباً همیشه هست.
3. **wkhtmltoimage** اگر بود.

## اگر هیچ‌کدام نبود

خطا نمی‌دهیم و تصویرِ نصفه هم نمی‌سازیم: ``None`` برمی‌گردد و فراخوان
پیام روشن می‌دهد. HTML همیشه ساخته می‌شود؛ PNG یک خروجیِ اضافه است، نه
شرطِ تحویل.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

#: جایی که مرورگر روی هر سه سیستم‌عامل می‌نشیند
_CANDIDATES: List[str] = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
_ON_PATH = ["google-chrome", "google-chrome-stable", "chromium",
            "chromium-browser", "microsoft-edge", "chrome"]


def browser() -> Optional[str]:
    """مسیر مرورگرِ موجود، یا ``None``."""
    env = os.environ.get("HRPERF_CHROME") or os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for name in _ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    for p in _CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _via_playwright(src: Path, out: Path, width: int, scale: int) -> bool:
    try:
        from playwright.sync_api import sync_playwright        # type: ignore
    except Exception:
        return False
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": width, "height": 1200},
                              device_scale_factor=scale)
            page.goto(src.resolve().as_uri())
            page.wait_for_timeout(700)          # فونت و بافت جا بیفتند
            page.screenshot(path=str(out), full_page=True)
            b.close()
        return out.exists() and out.stat().st_size > 0
    except Exception:
        return False


#: اسکریپتی که قدِ واقعی صفحه را روی خودِ ریشه می‌نویسد.
#: ``--screenshot`` کروم فقط به اندازهٔ **پنجره** عکس می‌گیرد، نه کلِ
#: صفحه. پس اول قد را می‌پرسیم، بعد پنجره را همان‌قدر باز می‌کنیم.
_PROBE = ("<script>addEventListener('load',function(){"
          "document.documentElement.setAttribute('data-h',"
          "String(document.body.scrollHeight));});</script>")


def _chrome_flags(tmp: str, scale: int) -> List[str]:
    flags = ["--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--user-data-dir={tmp}", f"--force-device-scale-factor={scale}",
             "--virtual-time-budget=5000"]
    # روی لینوکسِ کانتینری کاربر معمولاً root است و sandbox کروم بالا
    # نمی‌آید. فقط در همان حالت خاموشش می‌کنیم، نه همیشه.
    if sys.platform.startswith("linux") and hasattr(os, "geteuid") \
            and os.geteuid() == 0:
        flags.append("--no-sandbox")
    return flags


def _page_height(exe: str, src: Path, width: int) -> Optional[int]:
    import re
    probe = src.with_name(src.stem + ".__probe__.html")
    try:
        probe.write_text(src.read_text(encoding="utf-8") + _PROBE,
                         encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [exe] + _chrome_flags(tmp, 1)
                + [f"--window-size={width},1200", "--dump-dom",
                   probe.resolve().as_uri()],
                check=False, timeout=180, capture_output=True, text=True)
        m = re.search(r'data-h="(\d+)"', r.stdout or "")
        return int(m.group(1)) if m else None
    except Exception:
        return None
    finally:
        probe.unlink(missing_ok=True)


def _via_chrome(src: Path, out: Path, width: int, scale: int) -> bool:
    exe = browser()
    if not exe:
        return False
    height = _page_height(exe, src, width) or 1200
    height = max(600, min(height + 8, 30000))   # سقف، تا حافظه نترکد
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ([exe] + _chrome_flags(tmp, scale)
               + [f"--window-size={width},{height}",
                  "--screenshot=" + str(out), src.resolve().as_uri()])
        try:
            subprocess.run(cmd, check=False, timeout=300,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            return False
    return out.exists() and out.stat().st_size > 0


def _via_wkhtml(src: Path, out: Path, width: int, scale: int) -> bool:
    exe = shutil.which("wkhtmltoimage")
    if not exe:
        return False
    try:
        subprocess.run([exe, "--width", str(width), "--zoom", str(scale),
                        "--enable-local-file-access",
                        str(src.resolve()), str(out)],
                       check=False, timeout=180,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return False
    return out.exists() and out.stat().st_size > 0


def render(src: Path, out: Optional[Path] = None, *, width: int = 900,
           scale: int = 2) -> Optional[Path]:
    """``src`` (HTML) را به PNG تبدیل کن. مسیر خروجی، یا ``None``.

    ``scale=2`` یعنی تصویر دو برابرِ عرضِ منطقی است — برای چاپ و برای
    نمایشگرِ چگال. ``scale=3`` هم کار می‌کند ولی حجم را سه‌برابر می‌کند.
    """
    src = Path(src)
    out = Path(out) if out else src.with_suffix(".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    for fn in (_via_playwright, _via_chrome, _via_wkhtml):
        if fn(src, out, width, scale):
            return out
    return None


def why_not() -> str:
    """پیامِ صادقانه وقتی هیچ موتوری نبود."""
    return ("PNG ساخته نشد: نه Playwright نصب است، نه کروم/کرومیوم پیدا شد. "
            "یکی از این دو کافی است — یا مسیر مرورگر را در متغیر محیطی "
            "HRPERF_CHROME بگذارید. خودِ HTML ساخته شد و سالم است.")

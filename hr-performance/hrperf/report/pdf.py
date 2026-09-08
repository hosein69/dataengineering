# -*- coding: utf-8 -*-
"""تبدیل HTML گزارش به PDF (مشترک با پلتفرم AIBL).

چرا موتور مرورگر و نه کتابخانه PDF: فارسی **شکل‌دهی حرفی و راست‌به‌چپ**
دارد. کتابخانه‌های PDF عمومی (reportlab/fpdf) بدون لایه shaping، حروف را
جدا و برعکس می‌چینند. موتور مرورگر همان چیزی را چاپ می‌کند که در صفحه
دیده می‌شود.

اگر Playwright/Chromium نصب نباشد، **خطا پرتاب نمی‌شود**: همان HTML آماده
چاپ برگردانده می‌شود و پیام می‌گوید با Ctrl+P → Save as PDF ذخیره شود.
"""
from __future__ import annotations

__contract__ = 1

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class PdfUnavailable(RuntimeError):
    """موتور رندر برای PDF در دسترس نیست."""


@dataclass(frozen=True)
class PdfResult:
    path: Optional[Path]
    ok: bool
    message: str


def _find_chromium() -> Optional[str]:
    env = os.environ.get("AIBL_CHROMIUM", "").strip()
    if env and Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if root and Path(root).exists():
        for c in Path(root).glob("chromium*/chrome-linux/chrome"):
            return str(c)
        for c in Path(root).glob("chromium*/chrome-win/chrome.exe"):
            return str(c)
    return None


def html_to_pdf(html: str, out_path: str | Path,
                landscape: bool = True) -> PdfResult:
    """HTML را با موتور مرورگر به PDF تبدیل می‌کند.

    ابتدا Playwright، سپس Chromium خط فرمان (``--print-to-pdf``).
    اگر هیچ‌کدام نبود، ``ok=False`` برمی‌گردد و فراخوان باید HTML را
    به کاربر بدهد.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="aibl_pdf_")) / "report.html"
    tmp.write_text(html, encoding="utf-8")

    # ── مسیر ۱: Playwright ──
    try:
        from playwright.sync_api import sync_playwright
        exe = _find_chromium()
        with sync_playwright() as p:
            launch = {"args": ["--no-sandbox", "--disable-dev-shm-usage"]}
            if exe:
                launch["executable_path"] = exe
            b = p.chromium.launch(**launch)
            pg = b.new_page()
            pg.goto(tmp.as_uri(), wait_until="networkidle", timeout=90000)
            pg.wait_for_timeout(700)          # مهلت اجرای JS و رندر جدول
            pg.pdf(path=str(out), format="A3" if landscape else "A4",
                   landscape=landscape, print_background=True,
                   margin={"top": "12mm", "bottom": "12mm",
                           "left": "10mm", "right": "10mm"})
            b.close()
        return PdfResult(out, True, f"PDF ساخته شد: {out.name}")
    except Exception as ex:
        last = f"Playwright در دسترس نبود ({type(ex).__name__})"

    # ── مسیر ۲: Chromium خط فرمان ──
    exe = _find_chromium()
    if exe:
        import subprocess
        try:
            subprocess.run(
                [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
                 f"--print-to-pdf={out}", "--print-to-pdf-no-header",
                 tmp.as_uri()],
                check=True, capture_output=True, timeout=180)
            if out.exists():
                return PdfResult(out, True, f"PDF ساخته شد: {out.name}")
        except Exception as ex:
            last = f"{last}؛ Chromium خط فرمان هم نشد ({type(ex).__name__})"

    return PdfResult(None, False,
                     "موتور رندر PDF پیدا نشد. فایل HTML آماده چاپ ساخته شده — "
                     "آن را در مرورگر باز کنید و Ctrl+P → Save as PDF بزنید.\n"
                     f"جزئیات: {last}")

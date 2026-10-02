# -*- coding: utf-8 -*-
"""فونت سازمان: اول راوی، اگر نبود ایران‌سنس؛ پیدا کردن فایل‌ها و ساختن ``@font-face``.

راوی و ایران‌سنس هر دو تجاری‌اند (fontiran.com). فایل‌ها از نسخه دارای مجوز
سازمان می‌آیند و مالک پروژه آن‌ها را در ``assets/fonts`` گذاشته است. دو راه برای
دیده شدن فونت هست:

* **جاسازی**: فایل‌هایی که سازمان عمداً در ``assets/fonts`` یا ``GSI_FONT_DIR``
  (یا کنار ``GSI_FONT_PATH``) می‌گذارد، به‌صورت base64 داخل Studio و HTML ارسالی
  می‌نشینند تا گیرنده بدون نصب فونت همان صفحه را ببیند. فونت نصب‌شده سیستم هرگز
  جاسازی نمی‌شود (مجوز رومیزی معمولاً جاسازی در فایل ارسالی را پوشش نمی‌دهد).
  ``GSI_EMBED_FONTS=0`` جاسازی در HTML ارسالی را هم خاموش می‌کند.
* **نصب روی رایانه**: پشته فونت توکن‌ها (``FONT_STACK``) خانواده‌های نصب‌شده را
  با نام پیدا می‌کند. نمودارهای ایمیل هم فایل نصب‌شده را می‌خوانند.

اولویت (``FAMILIES``): راوی، سپس ایران‌سنس. هر خانواده با نام خودش جاسازی می‌شود
و پشته فونت راوی را اول می‌آورد؛ پس ایران‌سنس فقط جایی دیده می‌شود که راوی نیست
(نبودن فایل راوی، یا نویسه‌ای که در راوی نیست).

ارقام: پیش‌فرض ارقام لاتین است، چون کد بارنامه، ثبت سفارش و مبلغ باید همان‌طور که
در سیستم‌های منبع است خوانده شوند. اگر برای یک وزن فقط نسخه FaNum (ارقام فارسی)
هست (مثل RaviFaNum-Regular)، همان فایل فقط برای غیر رقم به کار می‌رود
(``unicode-range``) و ارقام لاتین از خانواده بعدی پشته می‌آید، یعنی ایران‌سنس.
ارقام وزن دیگرِ همان خانواده امتحان شد و کنار گذاشته شد: رقم نیم‌ضخیم وسط متن معمولی
و وسط کدی مثل HDM1511WXRQ9407 پررنگ دیده می‌شد. ``GSI_FONT_FANUM=1`` ارقام فارسی
را ترجیح می‌دهد.

ترتیب جستجو (اولین فایل مناسب برای هر خانواده و وزن برنده است):

1. ``GSI_FONT_DIR``: یک یا چند پوشه، جداشده با جداکننده مسیر سیستم؛
2. پوشه فایل ``GSI_FONT_PATH`` (همان متغیری که نمودارهای ایمیل می‌خوانند)؛
3. ``assets/fonts``، ``app/static/fonts`` و ``process-mining-ui-kit/static/fonts``
   در ریشه بسته؛
4. فقط برای نمودار و پیام وضعیت: فونت‌های نصب‌شده سیستم (``Windows\\Fonts``،
   فونت‌های کاربر ویندوز، ``~/.fonts`` و …). با ``GSI_FONT_SCAN_SYSTEM=0`` خاموش می‌شود.

نام‌های پذیرفته (پسوند ``.woff2/.woff/.ttf/.otf``؛ وزن از نام فایل خوانده می‌شود):

* راوی: ``Ravi-Bold.woff2``، ``Ravi-SemiBold.ttf``، ``RaviFaNum-Regular.woff`` و …
  (فونت «Ravie» ویندوز راوی نیست و کنار گذاشته می‌شود)؛
* ایران‌سنس: هر نامی که با ``IRANSans`` شروع شود، مثل ``IRANSansWeb-Bold.woff2``،
  ``IRANSans_Medium.ttf``، ``IRANSansX-Regular.woff2`` یا ``IRANSansWeb(FaNum).woff``.
  نسخه وب بر نسخه رومیزی مقدم است.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple


@dataclass(frozen=True)
class Family:
    key: str                                   #: شناسه خانواده در نتیجه کشف
    css: str                                   #: نام خانواده در ``@font-face``؛ در ``tokens.FONT_STACK`` هست
    label: str                                 #: نام فارسی برای پیام وضعیت
    pattern: Pattern[str]                      #: الگوی ابتدای نام فایل (حروف کوچک)
    variants: Tuple[Tuple[str, str], ...] = ()


#: به ترتیب اولویت: اول راوی، اگر نبود ایران‌سنس (خواسته مالک پروژه).
FAMILIES: Tuple[Family, ...] = (
    Family("ravi", "Ravi", "راوی",
           re.compile(r"ravi(?=$|[^a-z]|fanum|fd|vf|thin|ultra|extra|light|regular|normal|medium|demi|semi|bold"
                      r"|black|heavy)")),
    Family("iransans", "IRANSansWeb", "ایران‌سنس", re.compile(r"iransans"),
           (("web", "web"), ("x", "x"), ("mobile", "mobile"))),
)
_BY_KEY = {f.key: f for f in FAMILIES}
#: نام خانواده ایران‌سنس جاسازی‌شده (سازگاری با نسخه‌های قبل).
FAMILY = _BY_KEY["iransans"].css
#: وزن‌هایی که جاسازی می‌شوند؛ هر کدام به نزدیک‌ترین وزن موجود همان خانواده می‌رسد.
#: ExtraBlack (۹۵۰) جاسازی نمی‌شود: مرورگر برای وزن ۸۰۰ و ۹۰۰ طراحی (عنوان‌ها، تب‌ها و
#: عددهای شاخص) اول وزن سنگین‌تر موجود را برمی‌دارد و همه آن‌ها ExtraBlack می‌شدند.
#: بدون آن، ۸۰۰ و ۹۰۰ به Bold (۷۰۰) می‌رسند.
EMBED_WEIGHTS = (400, 500, 600, 700)
#: همه نویسه‌ها جز ارقام لاتین؛ برای فایل FaNum وقتی ارقام لاتین خواسته شده است.
NO_ASCII_DIGITS = "U+0-2F,U+3A-10FFFF"

_ROOT = Path(__file__).resolve().parents[2]
_EXT = {".woff2": ("woff2", "font/woff2", 0), ".woff": ("woff", "font/woff", 1),
        ".ttf": ("truetype", "font/ttf", 2), ".otf": ("opentype", "font/otf", 3)}
#: ترتیب اهمیت نسخه‌ها؛ نسخه وب برای صفحه‌نمایش ساخته شده است.
_VARIANT_RANK = {"web": 0, "x": 1, "desktop": 2, "mobile": 3}
#: کلیدواژه وزن به ترتیب بررسی؛ «ultralight» باید پیش از «light» بیاید.
_WEIGHT_WORDS = (("extrablack", 950), ("ultralight", 200), ("extralight", 200), ("thin", 100),
                 ("extrabold", 800), ("ultrabold", 800), ("demibold", 600), ("semibold", 600),
                 ("black", 900), ("heavy", 900), ("medium", 500), ("light", 300), ("bold", 700),
                 ("regular", 400), ("normal", 400))


@dataclass(frozen=True)
class FontFile:
    path: Path
    weight: int
    variant: str
    fanum: bool
    fmt: str
    mime: str
    family: str = "iransans"

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


def _prefer_fanum() -> bool:
    return os.environ.get("GSI_FONT_FANUM", "").strip() in ("1", "true", "yes")


def _family_of(name: str) -> Optional[Family]:
    low = name.lower()
    return next((f for f in FAMILIES if f.pattern.match(low)), None)


def classify(path: Path) -> Optional[FontFile]:
    """خانواده، وزن، نسخه و قالب را از نام فایل می‌خواند؛ فونت دیگر ← ``None``."""
    ext = path.suffix.lower()
    fam = _family_of(path.stem)
    if ext not in _EXT or fam is None:
        return None
    stem = re.sub(r"[^a-z0-9]", "", path.stem.lower())
    rest = stem[len(fam.key):]
    variant = "desktop"
    for key, name in fam.variants:
        if rest.startswith(key):
            variant, rest = name, rest[len(key):]
            break
    fanum = "fanum" in rest or rest.startswith("fd")
    rest = rest.replace("fanum", "")
    weight = 400
    for word, w in _WEIGHT_WORDS:
        if word in rest:
            weight = w
            break
    fmt, mime, _ = _EXT[ext]
    return FontFile(path, weight, variant, fanum, fmt, mime, fam.key)


def _env_dirs() -> List[Path]:
    out: List[Path] = []
    for part in (os.environ.get("GSI_FONT_DIR") or "").split(os.pathsep):
        if part.strip():
            out.append(Path(part.strip()).expanduser())
    fp = (os.environ.get("GSI_FONT_PATH") or "").strip()
    if fp:
        out.append(Path(fp).expanduser().parent)
    return out


def package_dirs() -> List[Path]:
    return [_ROOT / "assets" / "fonts", _ROOT / "app" / "static" / "fonts",
            _ROOT / "process-mining-ui-kit" / "static" / "fonts"]


def system_dirs() -> List[Path]:
    home = Path.home()
    out = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"]
    if os.environ.get("LOCALAPPDATA"):
        out.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "Windows" / "Fonts")
    out += [home / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts",
            home / "Library" / "Fonts", Path("/Library/Fonts"),
            home / ".fonts", home / ".local" / "share" / "fonts",
            Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]
    return out


def search_dirs(include_system: bool = True) -> List[Tuple[Path, str]]:
    """(پوشه، منبع) به ترتیب اولویت؛ منبع برای پیام وضعیت است. ``include_system=False``
    فقط پوشه‌هایی را می‌دهد که سازمان عمداً برای جاسازی پر کرده است."""
    dirs = [(d, "env") for d in _env_dirs()] + [(d, "package") for d in package_dirs()]
    if include_system and os.environ.get("GSI_FONT_SCAN_SYSTEM", "1").strip() not in ("0", "false", "no"):
        dirs += [(d, "system") for d in system_dirs()]
    seen, out = set(), []
    for d, src in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append((d, src))
    return out


def _iter_files(d: Path) -> Iterable[Path]:
    try:
        if not d.is_dir():
            return
        for root, _dirs, files in os.walk(d):
            for f in files:
                if _family_of(Path(f).stem) is not None:
                    yield Path(root) / f
    except OSError:
        return


def _rank(f: FontFile, prefer_fanum: bool) -> tuple:
    return (_VARIANT_RANK.get(f.variant, 9), 0 if f.fanum == prefer_fanum else 1, _EXT[f.path.suffix.lower()][2])


Found = Dict[str, Dict[int, Tuple[FontFile, str]]]


def discover(dirs: Optional[Iterable[Tuple[Path, str]]] = None,
             fmts: Optional[Tuple[str, ...]] = None, include_system: bool = True) -> Found:
    """بهترین فایل هر وزن در هر خانواده: ``{خانواده: {وزن: (فایل، منبع)}}``؛ ترتیب
    خانواده‌ها همان اولویت ``FAMILIES`` است و پوشه‌های اولویت بالاتر برنده‌اند.

    ``fmts`` قالب‌ها را محدود می‌کند؛ مثلاً matplotlib فقط truetype/opentype می‌خواند."""
    prefer_fanum = _prefer_fanum()
    best: Dict[Tuple[str, int], Tuple[FontFile, str, int]] = {}
    for order, (d, src) in enumerate(dirs if dirs is not None else search_dirs(include_system)):
        for p in _iter_files(d):
            f = classify(p)
            if f is None or f.size == 0 or (fmts and f.fmt not in fmts):
                continue
            cur = best.get((f.family, f.weight))
            if cur is None or (order, _rank(f, prefer_fanum)) < (cur[2], _rank(cur[0], prefer_fanum)):
                best[(f.family, f.weight)] = (f, src, order)
    out: Found = {}
    for fam in FAMILIES:
        ws = {w: (f, src) for (k, w), (f, src, _o) in sorted(best.items()) if k == fam.key}
        if ws:
            out[fam.key] = ws
    return out


@lru_cache(maxsize=2)
def cached_discover(include_system: bool = False) -> Found:
    """کشف یک‌باره در هر فرایند؛ پس از افزودن فایل فونت، :func:`refresh` یا راه‌اندازی دوباره.
    پیش‌فرض فقط منابع جاسازی (``GSI_FONT_DIR``، ``GSI_FONT_PATH``، ``assets/fonts``)."""
    return discover(include_system=include_system)


def _pick(found: Dict[int, Tuple[FontFile, str]], weights: Iterable[int]) -> Dict[int, FontFile]:
    """برای هر وزن خواسته‌شده همان وزن، وگرنه نزدیک‌ترین وزن موجود (در یک خانواده)."""
    out: Dict[int, FontFile] = {}
    avail = sorted(found)
    for w in weights if avail else ():
        k = w if w in found else min(avail, key=lambda a: (abs(a - w), a))
        out[k] = found[k][0]
    return out


@lru_cache(maxsize=16)
def _encoded(path: str, mtime: float) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def refresh() -> None:
    """کش کشف و کدگذاری را خالی می‌کند (آزمون‌ها و پس از افزودن فایل فونت)."""
    cached_discover.cache_clear()
    _encoded.cache_clear()


def _face(family: str, weight: int, f: FontFile, unicode_range: str = "") -> str:
    try:
        data = _encoded(str(f.path), f.path.stat().st_mtime)
    except OSError:
        return ""
    rng = f";unicode-range:{unicode_range}" if unicode_range else ""
    return (f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
            f"font-display:swap;src:url(data:{f.mime};base64,{data}) format('{f.fmt}'){rng}}}")


def font_face_css(found: Optional[Found] = None, weights: Iterable[int] = EMBED_WEIGHTS) -> str:
    """قواعد ``@font-face`` با داده base64، خانواده به خانواده به ترتیب اولویت؛ اگر فایلی
    پیدا نشود رشته خالی.

    رشته خالی یعنی «هیچ تغییری»: پشته فونت توکن‌ها همچنان به فونت نصب‌شده و بعد
    Tahoma برمی‌گردد.
    """
    found = cached_discover(False) if found is None else found
    weights = tuple(weights)
    prefer_fanum = _prefer_fanum()
    rules: List[str] = []
    for fam in FAMILIES:
        ff = found.get(fam.key)
        if not ff:
            continue
        for w, f in sorted(_pick(ff, weights).items()):
            # FaNum فقط برای غیر رقم؛ ارقام لاتین از خانواده بعدی پشته (ایران‌سنس)
            rules.append(_face(fam.css, w, f, NO_ASCII_DIGITS if f.fanum and not prefer_fanum else ""))
    return "\n".join(r for r in rules if r)


def embed_in_html() -> bool:
    """جاسازی در HTML ارسالی؛ پیش‌فرض روشن، با ``GSI_EMBED_FONTS=0`` خاموش."""
    return os.environ.get("GSI_EMBED_FONTS", "1").strip() not in ("0", "false", "no")


def html_font_css() -> str:
    """``@font-face`` برای HTML مستقل؛ خالی اگر فونتی نیست یا جاسازی خاموش است."""
    return font_face_css() if embed_in_html() else ""


def chart_font_path() -> Optional[Path]:
    """فایل TTF/OTF برای نمودارهای matplotlib (woff را نمی‌خواند): خانواده اول، نزدیک‌ترین
    وزن به معمولی. فونت نصب‌شده سیستم هم پذیرفته است: نمودار تصویر PNG است و خود فایل
    فونت جایی نمی‌رود."""
    found = discover(fmts=("truetype", "opentype"), include_system=True)
    prefer_fanum = _prefer_fanum()
    for fam in FAMILIES:
        ff = found.get(fam.key)
        if ff:
            _w, (f, _src) = min(ff.items(), key=lambda kv: (kv[1][0].fanum != prefer_fanum, abs(kv[0] - 400), kv[0]))
            return f.path
    return None


def _names(keys: Iterable[str]) -> str:
    return " و ".join(_BY_KEY[k].label for k in keys)


def status() -> Dict[str, object]:
    """وضعیت برای نمایش در Studio و مستندات."""
    web = cached_discover(False)
    where = {"env": "GSI_FONT_DIR", "package": "assets/fonts", "system": "فونت‌های نصب‌شده سیستم"}
    if web:
        files, srcs = [], set()
        for key, ff in web.items():
            for w, f in sorted(_pick(ff, EMBED_WEIGHTS).items()):
                files.append(f"{f.path.name} ({w})")
                srcs.add(ff[w][1])
        src = "، ".join(where.get(x, x) for x in sorted(srcs))
        names = _names(web)
        first = _BY_KEY[next(iter(web))]
        order = "؛ اولویت با راوی است و ایران‌سنس فقط جای خالی آن را پر می‌کند" if len(web) > 1 else ""
        return {"ok": True, "embedded": True, "family": first.css,
                "families": [_BY_KEY[k].css for k in web], "files": files,
                "source": src, "embedded_in_html": embed_in_html(),
                "message": f"{names} از {src} بارگذاری شد و در Studio و HTML ارسالی جاسازی می‌شود{order}.",
                "short": f"{names} از {src} جاسازی شد."}
    installed = cached_discover(True)
    if installed:
        names = _names(installed)
        return {"ok": True, "embedded": False, "family": _BY_KEY[next(iter(installed))].css,
                "families": [_BY_KEY[k].css for k in installed],
                "files": [f"{f.path.name} ({w})" for ff in installed.values() for w, (f, _s) in sorted(ff.items())],
                "source": where["system"], "embedded_in_html": False,
                "message": f"{names} روی این رایانه نصب است و Studio و نمودارها از آن استفاده می‌کنند. "
                           "برای اینکه گیرنده HTML بدون نصب فونت هم همین فونت را ببیند، فایل‌های وب دارای "
                           "مجوز (woff2) را در assets/fonts بگذارید.",
                "short": f"{names} نصب‌شده این رایانه استفاده می‌شود."}
    return {"ok": False, "embedded": False, "family": _BY_KEY["ravi"].css, "families": [], "files": [],
            "source": "", "embedded_in_html": False,
            "message": "فایل فونت راوی یا ایران‌سنس پیدا نشد. فایل‌های دارای مجوز سازمان "
                       "(مثل Ravi-Bold.woff2 و RaviFaNum-Regular.woff یا IRANSansWeb.woff2) را در "
                       "پوشه assets/fonts بگذارید یا مسیرشان را در GSI_FONT_DIR تعریف کنید.",
            "short": "فونت راوی یا ایران‌سنس پیدا نشد؛ فایل‌های دارای مجوز را در پوشه assets/fonts بگذارید."}

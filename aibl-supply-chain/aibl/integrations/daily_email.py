# -*- coding: utf-8 -*-
"""AIBL Executive Daily Email Pack — Outlook integration."""
from __future__ import annotations
import html, os, re
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import pandas as pd
from ..config.settings import SETTINGS
from ..dataio.logging_setup import log
from ..report import design_system as ds

THEME, NAVY = "#0F6E6E", "#102D4D"
RED, ORANGE, YELLOW, GREEN, GREY = "#C0392B", "#F39C12", "#F1C40F", "#27AE60", "#95A5A6"
BG, BORDER, TEXT = "#F2F5F5", "#D8E4E1", "#243447"
EMAIL_FONT = "'IRANSans',Tahoma,Arial,sans-serif"
# ── فهرست گیرندگان: پیکربندی محرمانه، هرگز داخل سورس ──────────────────────
# نشانی‌های واقعی کارکنان داده شخصی‌اند و در مخزن نگه‌داری نمی‌شوند.
# ترتیب حل:
#   ۱) متغیر محیطی AIBL_EMAIL_TO  (جدا با «,» یا «;»)
#   ۲) فایلی که AIBL_RECIPIENTS_FILE به آن اشاره می‌کند
#   ۳) recipients.yaml کنار پیکربندی (AIBL_HOME یا پوشه جاری)
#   ۴) **سورس HR** — ستون Email همان فایل پرسنلی (AIBL_EMAIL_FROM_HR=1)
#
# گزینه ۴ بهترین حالت است: فهرست هرگز در مخزن یا فایل جانبی کپی نمی‌شود،
# همیشه با آخرین وضعیت پرسنلی هم‌گام است، و کسی که غیرفعال شده خودکار
# از فهرست بیرون می‌رود.
# اگر هیچ‌کدام نبود، فهرست خالی است: ساخت گزارش کار می‌کند ولی ارسال
# با خطای صریح متوقف می‌شود — به‌جای آنکه بی‌صدا به فهرستی قدیمی برود.
RECIPIENTS_ENV = "AIBL_EMAIL_TO"
RECIPIENTS_FILE_ENV = "AIBL_RECIPIENTS_FILE"
RECIPIENTS_BASENAME = "recipients.yaml"


class NoRecipients(RuntimeError):
    """هیچ گیرنده‌ای پیکربندی نشده است."""


def _split(raw: str) -> list:
    return [x.strip() for x in re.split(r"[,;\s]+", raw or "") if x.strip() and "@" in x]


def _from_file(path: Path) -> list:
    """هر خط یک نشانی، یا YAML با کلید ``recipients``. «#» توضیح است."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    try:
        import yaml
        data = yaml.safe_load(text)
        if isinstance(data, dict) and data.get("recipients"):
            return [str(x).strip() for x in data["recipients"] if "@" in str(x)]
        if isinstance(data, list):
            return [str(x).strip() for x in data if "@" in str(x)]
    except Exception:
        pass
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip().lstrip("- ").strip()
        if "@" in line:
            out.append(line)
    return out


# ── انتخاب گیرنده از سورس HR ──────────────────────────────────────────────
HR_ENABLE_ENV = "AIBL_EMAIL_FROM_HR"
HR_POSTS_ENV = "AIBL_EMAIL_HR_POSTS"          # شرح پست، جدا با «,»
HR_MANAGEMENTS_ENV = "AIBL_EMAIL_HR_MANAGEMENTS"
HR_OFFICES_ENV = "AIBL_EMAIL_HR_OFFICES"
HR_MAX_ENV = "AIBL_EMAIL_HR_MAX"

#: پیش‌فرض: فقط سطوح مدیریتی. گزارش روزانه مدیریتی است و ارسال آن به کل
#: پرسنل نه مفید است نه محتاطانه.
DEFAULT_HR_POSTS = ("مدیر", "رئیس", "معاون")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def _csv_env(name: str, default=()) -> tuple:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return tuple(default)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


def hr_recipients(hr_frame: Optional["pd.DataFrame"] = None) -> list:
    """گیرندگان را از ستون Email سورس HR برمی‌دارد.

    فیلترها، به ترتیب:
      • فقط پرسنل **فعال** (کسی که غیرفعال شده خودکار حذف می‌شود)
      • نشانی معتبر از نظر شکل
      • انطباق با شرح پست / مدیریت / اداره، اگر تعیین شده باشد

    نشانی‌ها هرگز لاگ یا ذخیره نمی‌شوند؛ فقط **تعداد** گزارش می‌گردد.
    """
    df = hr_frame
    if df is None:
        try:
            from ..adapters import discover, REGISTRY
            discover()
            cls = REGISTRY.get("hr")
            if cls is None:
                return []
            df = (cls().load() or {}).get("main")
        except Exception as ex:
            log.warning(f"⚠️ سورس HR برای گیرندگان ایمیل خوانده نشد: {ex}")
            return []
    if df is None or getattr(df, "empty", True):
        return []

    def col(suffix: str):
        name = f"HR_{suffix}"
        return df[name] if name in df.columns else None

    email = col("EMAIL")
    if email is None:
        log.warning("⚠️ ستون Email در سورس HR نیست؛ گیرنده‌ای استخراج نشد.")
        return []
    mail = email.fillna("").astype(str).str.strip()

    keep = mail.map(lambda x: bool(_EMAIL_RE.match(x)))

    status = col("STATUS")
    if status is not None:
        st = status.fillna("").astype(str)
        keep &= st.str.contains("فعال", na=False) & ~st.str.contains("غیرفعال", na=False)

    for env, suffix in ((HR_POSTS_ENV, "POST"), (HR_MANAGEMENTS_ENV, "DEPT"),
                        (HR_OFFICES_ENV, "OFFICE")):
        wanted = _csv_env(env, DEFAULT_HR_POSTS if env == HR_POSTS_ENV else ())
        if not wanted:
            continue
        c = col(suffix)
        if c is None:
            continue
        text = c.fillna("").astype(str)
        keep &= text.apply(lambda v: any(w in v for w in wanted))

    out = sorted({m.lower() for m in mail[keep] if m})
    cap = os.environ.get(HR_MAX_ENV, "").strip()
    if cap.isdigit():
        out = out[:int(cap)]
    log.info(f"👥 {len(out)} گیرنده از سورس HR انتخاب شد "
             f"(از {len(df)} پرسنل؛ نشانی‌ها لاگ نمی‌شوند).")
    return out


def recipients_path() -> Optional[Path]:
    explicit = os.environ.get(RECIPIENTS_FILE_ENV, "").strip()
    if explicit:
        return Path(explicit)
    home = os.environ.get("AIBL_HOME") or os.path.join(os.path.expanduser("~"), ".aibl")
    for cand in (Path(home) / RECIPIENTS_BASENAME, Path.cwd() / RECIPIENTS_BASENAME):
        if cand.exists():
            return cand
    return None


def _recipients() -> list:
    raw = os.environ.get(RECIPIENTS_ENV, "")
    if raw.strip():
        return _split(raw)
    path = recipients_path()
    if path:
        found = _from_file(path)
        if found:
            return found
    # سورس HR — تازه‌ترین و کم‌خطاترین منبع، چون کپی جانبی نمی‌سازد.
    if os.environ.get(HR_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on"):
        return hr_recipients()
    return []


def configured_recipients() -> list:
    """Public, read-only recipient resolver used by Studio composer."""
    return list(_recipients())

def _addresses(value, fallback=None) -> list:
    if value is None:
        return list(fallback or [])
    if isinstance(value, str):
        return _split(value)
    out=[]
    for x in value:
        out.extend(_split(str(x)))
    return sorted(dict.fromkeys(out))


def daily_paths(day: Optional[date]=None) -> Dict[str,Path]:
    d=day or SETTINGS.today
    folder=Path(SETTINGS.daily_report_root)/d.strftime("%Y-%m-%d")
    folder.mkdir(parents=True,exist_ok=True)
    assets=folder/"email_assets"; assets.mkdir(parents=True,exist_ok=True)
    return {"folder":folder,"excel":Path(SETTINGS.daily_report_path(d)),"assets":assets,
            "html":folder/f"{d:%Y-%m-%d}_AIBL_Executive_Email.html",
            "report_html":folder/f"{d:%Y-%m-%d}_AIBL_Interactive_Report.html"}

def _require_matplotlib():
    """پیام روشن به‌جای ModuleNotFoundError خام.

    نمودارهای ایمیل با matplotlib کشیده می‌شوند و تا نسخه ۲۶٫۲٫۲ این
    وابستگی در requirements.txt نبود؛ «python -m aibl email» روی نصب تازه
    با traceback خام می‌افتاد.
    """
    try:
        import matplotlib  # noqa: F401
    except ImportError as ex:
        raise ImportError(
            "بسته ایمیل مدیریتی به matplotlib نیاز دارد:\n"
            "    python -m pip install matplotlib") from ex


def email_font_status() -> dict[str, Any]:
    """Report whether chart rendering can use a real IRANSans font.

    The font itself is intentionally external to the package. This function is
    used by Studio so fallback is visible before an email is generated.
    """
    family=os.environ.get("AIBL_FONT_NAME","IRANSans").strip() or "IRANSans"
    font_path=os.environ.get("AIBL_FONT_PATH","").strip()
    try:
        from matplotlib import font_manager
        if font_path and Path(font_path).exists():
            actual=font_manager.FontProperties(fname=font_path).get_name()
            return {"ok": True, "family": actual, "source": str(Path(font_path).resolve())}
        for name in (family,"IRANSans","IRANSansX","IRANSans Light"):
            try:
                found=font_manager.findfont(name,fallback_to_default=False)
                if found:
                    return {"ok": True, "family": name, "source": found}
            except Exception:
                continue
    except Exception as ex:
        return {"ok": False, "family": family, "source": "", "error": str(ex)}
    return {"ok": False, "family": family, "source": "",
            "error": "IRANSans روی این سیستم پیدا نشد؛ AIBL_FONT_PATH را تنظیم کنید."}


def _font_setup():
    """Configure IRANSans for email chart images when available.

    Font files are never bundled with AIBL.  On managed machines set
    ``AIBL_FONT_PATH`` to the locally licensed/installed font file, or install
    IRANSans system-wide.  ``AIBL_FONT_NAME`` can override the family name.

    خانواده فونت به‌صورت **زنجیره** تنظیم می‌شود، نه یک نام. دلیلش یک حالت
    واقعی است: بعضی فونت‌های فارسی فقط حروف عربی/فارسی دارند و نویسه‌های
    لاتین ندارند. با یک نام تنها، عنوانی مثل «همبستگی r = ۰٫۳۱» یا
    «۸۰/۲۰» بخش لاتین‌اش به‌شکل مربع خالی چاپ می‌شد — نموداری که به‌ظاهر
    سالم است ولی عددش خوانده نمی‌شود. با زنجیره، matplotlib برای هر نویسه
    گمشده به فونت بعدی می‌رود.
    """
    _require_matplotlib()
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_path=os.environ.get("AIBL_FONT_PATH","").strip()
    status=email_font_status()
    try:
        if font_path and Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
        if not status.get("ok"):
            raise RuntimeError(status.get("error") or "IRANSans not found")
        family=str(status.get("family") or "IRANSans")
        # زنجیره باید **فهرست نام فونت واقعی** باشد، نه نام عام «sans-serif».
        # اندازه‌گیری روی matplotlib 3.11: با
        #     font.family="sans-serif"; font.sans-serif=[X,"DejaVu Sans"]
        # جایگزینی نویسه‌به‌نویسه انجام نمی‌شود و ۱۲۳ هشدار Glyph missing
        # صادر می‌شود؛ با
        #     font.family=[X,"DejaVu Sans"]
        # صفر هشدار. نام عام فقط یک فونت را انتخاب می‌کند و همان‌جا می‌ماند.
        plt.rcParams["font.family"] = [family, "DejaVu Sans"]
    except Exception:
        family="DejaVu Sans"
        plt.rcParams["font.family"] = [family]
        log.warning("⚠️ فونت IRANSans برای نمودار ایمیل پیدا نشد؛ AIBL_FONT_PATH را تنظیم کنید.")
    plt.rcParams["axes.unicode_minus"] = False
    return family

def _fa(value: Any) -> str:
    """Shape Persian text for matplotlib when optional shaping packages exist."""
    text=str(value if value is not None else "")
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text

def _save_chart(fig,path:Path)->Path:
    fig.savefig(path,dpi=160,bbox_inches="tight",facecolor="white")
    import matplotlib.pyplot as plt; plt.close(fig); return path

def _band_fill(label: Any) -> Optional[str]:
    """رنگ سطح یک طبقه وضعیت، یا ``None`` برای برچسبی که وضعیت نیست."""
    st = ds.STATUS_BY_LABEL.get(str(label).strip())
    return st.fill if st else None


def _trend_data() -> Dict[str, Any]:
    """تاریخچه KPI برای نمودار روند و نشان تغییر.

    نبودن تاریخچه خطا نیست: روز نخست استقرار هیچ گذشته‌ای وجود ندارد و
    نمودارهای روند بی‌صدا ساخته نمی‌شوند.
    """
    try:
        from ..report.storytelling import load_history
        return load_history()
    except Exception:
        return {"dates": [], "series": {}, "deltas": {}, "points": 0}


def available_email_charts() -> Dict[str, str]:
    from ..studio_core.chart_catalog import CHART_TITLES
    return dict(CHART_TITLES)

def _first_col(df: pd.DataFrame, names) -> Optional[str]:
    return next((c for c in names if c in df.columns), None)

def make_email_charts(df: pd.DataFrame, assets: Path,
                      selected: Optional[Iterable[str]] = None,
                      extras: Optional[Dict[str, Any]] = None) -> list[Path]:
    """Build selected charts from the shared Studio chart catalog.

    Process charts never render as an empty box: when Event/Transition Log is
    insufficient, ``bottlenecks`` falls back to current-stage distribution and
    explicitly labels itself as a starting-point view.
    """
    _require_matplotlib()
    import matplotlib.pyplot as plt
    _font_setup()
    from ..studio_core.chart_catalog import CHART_TITLES, DEFAULT_EMAIL_CHARTS
    from ..studio_core.grain import safe_agg

    wanted=[x for x in (list(selected) if selected is not None else DEFAULT_EMAIL_CHARTS) if x in CHART_TITLES]
    out=[]; assets.mkdir(parents=True,exist_ok=True)
    def save(fig,key):
        path=assets/f"{len(out)+1:02d}_{key}.png"; out.append(_save_chart(fig,path))
    def style(ax,title,xlabel="",ylabel="",subtitle=""):
        """ظاهر مشترک همه نمودارهای ایمیل.

        قاب بالا/راست حذف می‌شود و خطوط راهنما کم‌رنگ می‌مانند: در یک PNG
        کوچک داخل کلاینت ایمیل، هر خط اضافه نسبت سیگنال به نویز را پایین
        می‌آورد بدون آنکه چیزی به خواننده بگوید.
        """
        ax.set_title(_fa(title),fontsize=13,fontweight="bold",pad=14 if subtitle else 10,
                     color=ds.TEXT)
        if subtitle:
            ax.text(.5,1.02,_fa(subtitle),transform=ax.transAxes,ha="center",va="bottom",
                    fontsize=9,color=ds.TEXT_MUTED)
        if xlabel: ax.set_xlabel(_fa(xlabel),fontsize=9,color=ds.TEXT_SECONDARY)
        if ylabel: ax.set_ylabel(_fa(ylabel),fontsize=9,color=ds.TEXT_SECONDARY)
        for side in ("top","right"): ax.spines[side].set_visible(False)
        for side in ("left","bottom"): ax.spines[side].set_color(ds.BORDER_STRONG)
        ax.tick_params(colors=ds.TEXT_MUTED,labelsize=8.5)
        ax.grid(alpha=.16,linewidth=.7,color=ds.BORDER_STRONG)
        ax.set_axisbelow(True)
    def bar(key,labels,values,color=THEME,horizontal=True,title=None,edge=None,subtitle=""):
        pairs=[(str(k),float(v)) for k,v in zip(labels,values) if pd.notna(v)]
        if not pairs:return
        pairs=pairs[:12]
        fig,ax=plt.subplots(figsize=(9, max(3.6, .38*len(pairs)+1.4)))
        labs=[_fa(x[0]) for x in pairs]; vals=[x[1] for x in pairs]
        # مرز تیره، نه سفید: سطح زرد/نارنجی روی پس‌زمینه روشن لبه ندارد و
        # بدون مرز، میله عملاً در کارت ایمیل گم می‌شود (WCAG 1.4.11).
        ec=edge or ds.BRAND_DEEP
        if horizontal:
            bars=ax.barh(labs,vals,color=color,edgecolor=ec,linewidth=.7)
            ax.grid(axis="y",alpha=0)
            for b,v in zip(bars,vals): ax.text(v,b.get_y()+b.get_height()/2,f" {v:,.1f}",va="center",fontsize=8,color=ds.TEXT_SECONDARY)
        else:
            bars=ax.bar(labs,vals,color=color,edgecolor=ec,linewidth=.7)
            ax.grid(axis="x",alpha=0)
            ax.tick_params(axis='x',labelrotation=25)
            for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,v,f"{v:,.1f}",ha="center",va="bottom",fontsize=8,color=ds.TEXT_SECONDARY)
        style(ax,title or CHART_TITLES[key],subtitle=subtitle); fig.tight_layout(); save(fig,key)
    def donut(key,labels,values,colors=None):
        pairs=[(str(k),float(v)) for k,v in zip(labels,values) if float(v)>0]
        if not pairs:return
        fig,ax=plt.subplots(figsize=(8.8,4.4)); labs=[_fa(x[0]) for x in pairs]; vals=[x[1] for x in pairs]
        cs=colors or [_band_fill(x[0]) or ds.CATEGORICAL[i%len(ds.CATEGORICAL)] for i,x in enumerate(pairs)]
        w,_t,_a=ax.pie(vals,labels=labs,autopct=lambda p:f"{p:.0f}%",startangle=90,colors=cs,
                       wedgeprops=dict(width=.42,edgecolor="white",linewidth=2),
                       textprops=dict(fontsize=9,color=ds.TEXT_SECONDARY))
        ax.text(0,0,f"{int(sum(vals)):,}",ha="center",va="center",fontsize=17,fontweight="bold",color=ds.BRAND_DEEP)
        ax.set_title(_fa(CHART_TITLES[key]),fontsize=13,fontweight="bold",color=ds.TEXT); fig.tight_layout(); save(fig,key)
    def trend(key,metric):
        """روند KPI از snapshot تاریخی — نه از برش جاری.

        بدون این نمودار، هیچ عددی در ایمیل به «بهتر شدیم یا بدتر؟» جواب
        نمی‌دهد و مدیر ناچار است گزارش دیروز را باز کند تا مقایسه کند.
        """
        tr=_trend_data(); ser=(tr.get("series") or {}).get(metric)
        pts=[(d,v) for d,v in zip(tr.get("dates") or [],ser or []) if v is not None]
        if len(pts)<2: return
        fig,ax=plt.subplots(figsize=(9,3.6))
        xs=list(range(len(pts))); ys=[p[1] for p in pts]
        ax.plot(xs,ys,color=ds.BRAND_DEEP,linewidth=2.2,marker="o",markersize=3.5,
                markerfacecolor=ds.BRAND_DEEP,markeredgecolor="white")
        ax.fill_between(xs,ys,min(ys)-(max(ys)-min(ys) or 1)*.12,color=ds.BRAND,alpha=.12)
        ax.scatter([xs[-1]],[ys[-1]],s=68,color=ds.BRAND_DEEP,edgecolor="white",zorder=5,linewidth=1.6)
        step=max(1,len(pts)//7)
        ax.set_xticks(xs[::step]); ax.set_xticklabels([p[0][5:] for p in pts[::step]],fontsize=8)
        d=(tr.get("deltas") or {}).get(metric); sub=""
        if d:
            # داخل PNG فقط واژه فارسی، نه نویسه‌های مثلثی: فونت‌های فارسی
            # اغلب ▲/▼ ندارند و به‌جای جهت، مربع خالی چاپ می‌شود. نشان
            # مثلثی فقط در HTML می‌آید که فونت مرورگر آن را دارد.
            direction="افزایش" if d["change"]>0 else ("کاهش" if d["change"]<0 else "بدون تغییر")
            word="بهبود" if d.get("improving") else ("بدتر شدن" if d.get("improving") is False else "")
            pct=f" ({abs(d['pct']):.0f} درصد)" if d.get("pct") else ""
            sub=f"{direction} {abs(d['change']):,.1f}{pct} نسبت به اجرای قبلی" + (f" — {word}" if word else "")
        style(ax,CHART_TITLES[key],ylabel=metric,subtitle=sub)
        ax.grid(axis="x",alpha=0); fig.tight_layout(); save(fig,key)
    def scatter(key,xcol,ycol,xlabel,ylabel):
        """پراکنش با خط رگرسیون و ضریب همبستگی.

        ابری از نقطه بدون خط روند و بدون r تصمیمی را عوض نمی‌کند؛ عدد
        همبستگی همان چیزی است که می‌گوید آیا الگو واقعی است یا توهم چشم.
        """
        if not {xcol,ycol}.issubset(df.columns): return
        x=pd.to_numeric(df[xcol],errors="coerce"); y=pd.to_numeric(df[ycol],errors="coerce")
        m=x.notna()&y.notna()
        if int(m.sum())<3: return
        xv,yv=x[m].to_numpy(),y[m].to_numpy()
        fig,ax=plt.subplots(figsize=(9,4.6))
        band=df.loc[m,"بحرانی (کوتاه)"].astype(str) if "بحرانی (کوتاه)" in df.columns else None
        cols=[_band_fill(b) or ds.BRAND for b in band] if band is not None else ds.BRAND
        ax.scatter(xv,yv,c=cols,alpha=.62,s=26,edgecolor="white",linewidth=.4)
        mx,my=float(pd.Series(xv).median()),float(pd.Series(yv).median())
        ax.axvline(mx,color=ds.TEXT_MUTED,linestyle="--",linewidth=.9,alpha=.7)
        ax.axhline(my,color=ds.TEXT_MUTED,linestyle="--",linewidth=.9,alpha=.7)
        sub=""
        if len(xv)>2 and float(((xv-xv.mean())**2).sum())>0:
            slope=float(((xv-xv.mean())*(yv-yv.mean())).sum()/((xv-xv.mean())**2).sum())
            inter=float(yv.mean()-slope*xv.mean())
            den=float((((xv-xv.mean())**2).sum()*((yv-yv.mean())**2).sum())**.5)
            r=float(((xv-xv.mean())*(yv-yv.mean())).sum()/den) if den else 0.0
            lo,hi=float(xv.min()),float(xv.max())
            ax.plot([lo,hi],[slope*lo+inter,slope*hi+inter],color=ds.BRAND_DEEP,linewidth=1.8)
            strength=("رابطه‌ای دیده نمی‌شود" if abs(r)<.2 else "رابطه ضعیف" if abs(r)<.5
                      else "رابطه متوسط" if abs(r)<.75 else "رابطه قوی")
            sub=f"همبستگی r = {r:.2f} — {strength}؛ خط‌چین‌ها میانه هر محور است"
        style(ax,CHART_TITLES[key],xlabel=xlabel,ylabel=ylabel,subtitle=sub)
        fig.tight_layout(); save(fig,key)
    def pareto(key,pairs):
        """میله نزولی + منحنی تجمعی؛ می‌گوید تمرکز روی چند پرونده است."""
        pairs=sorted([(str(k),float(v)) for k,v in pairs if pd.notna(v) and float(v)>0],
                     key=lambda t:-t[1])
        if len(pairs)<2: return
        total=sum(v for _k,v in pairs); pairs=pairs[:12]
        fig,ax=plt.subplots(figsize=(9,4.4))
        labs=[_fa(k[:16]) for k,_v in pairs]; vals=[v for _k,v in pairs]
        ax.bar(labs,vals,color=ds.BRAND,edgecolor=ds.BRAND_DEEP,linewidth=.7)
        ax.tick_params(axis="x",labelrotation=32); ax.grid(axis="x",alpha=0)
        cum,ys=0.0,[]
        for _k,v in pairs:
            cum+=v; ys.append(cum/total*100)
        ax2=ax.twinx(); ax2.plot(labs,ys,color=ds.BRAND_DEEP,linewidth=2,marker="o",markersize=3.5)
        ax2.axhline(80,color=ds.STATUS["serious"].ink,linestyle="--",linewidth=1.1)
        ax2.set_ylim(0,105); ax2.set_ylabel(_fa("سهم تجمعی (٪)"),fontsize=9,color=ds.TEXT_SECONDARY)
        ax2.tick_params(colors=ds.TEXT_MUTED,labelsize=8.5)
        for side in ("top",): ax2.spines[side].set_visible(False)
        reach=next((i+1 for i,v in enumerate(ys) if v>=80),0)
        sub=(f"۸۰٪ از کل روی {reach} دسته نخست متمرکز است" if reach
             else "تمرکز کمتر از قاعده ۸۰/۲۰ است؛ اثر روی دسته‌های زیادی پخش شده")
        style(ax,CHART_TITLES[key],subtitle=sub); fig.tight_layout(); save(fig,key)
    def counts(cols,top=12):
        c=_first_col(df,cols)
        if not c:return pd.Series(dtype=float)
        return df[c].fillna("").astype(str).replace("","نامشخص").value_counts().head(top)

    for key in wanted:
        if key=="criticality":
            c=_first_col(df,["بحرانی (کوتاه)","کد طبقه بحرانی"])
            if c:
                vc=df[c].fillna("").astype(str).replace("","نامشخص").value_counts(); donut(key,vc.index,vc.values)
        elif key=="low_resistance" and {"KEY_MATERIAL","مقاومت (روز)"}.issubset(df.columns):
            x=df[["KEY_MATERIAL","مقاومت (روز)"]].copy();x["مقاومت (روز)"]=pd.to_numeric(x["مقاومت (روز)"],errors="coerce");x=x.dropna().drop_duplicates("KEY_MATERIAL").sort_values("مقاومت (روز)").head(10)
            bar(key,x["KEY_MATERIAL"],x["مقاومت (روز)"],color=RED)
        elif key=="stock_vs_total" and {"KEY_MATERIAL","مقاومت انبار (روز)","مقاومت (روز)"}.issubset(df.columns):
            x=df[["KEY_MATERIAL","مقاومت انبار (روز)","مقاومت (روز)"]].copy();
            for c in x.columns[1:]:x[c]=pd.to_numeric(x[c],errors="coerce")
            x=x.dropna(subset=["مقاومت (روز)"]).drop_duplicates("KEY_MATERIAL").sort_values("مقاومت (روز)").head(10)
            if not x.empty:
                fig,ax=plt.subplots(figsize=(9,4.8));pos=list(range(len(x)));w=.38
                ax.bar([i-w/2 for i in pos],x["مقاومت انبار (روز)"].fillna(0),width=w,label=_fa("مقاومت انبار"))
                ax.bar([i+w/2 for i in pos],x["مقاومت (روز)"].fillna(0),width=w,label=_fa("مقاومت کل"))
                ax.set_xticks(pos);ax.set_xticklabels(x["KEY_MATERIAL"].astype(str),rotation=35,ha="right");style(ax,CHART_TITLES[key],ylabel="روز");ax.legend(frameon=False);fig.tight_layout();save(fig,key)
        elif key=="sediment_vs_resistance":
            scatter(key,"روزهای رسوب","مقاومت (روز)","روزهای رسوب","مقاومت (روز)")
        elif key=="risk_mix":
            vc=counts(["طبقه ریسک"]); donut(key,vc.index,vc.values)
        elif key=="commitment" and "مانده تعهد" in df.columns:
            bal=pd.to_numeric(df["مانده تعهد"],errors="coerce").fillna(0);delay=pd.to_numeric(df.get("روزهای تأخیر",0),errors="coerce").fillna(0)
            masks=[delay>0,(delay<=0)&(bal>0),bal<=0];labs=["معوق","در مهلت","تسویه‌شده"];vals=[safe_agg(df.loc[m].copy(),"مانده تعهد","sum") for m in masks]
            bar(key,labs,vals,color=ORANGE,horizontal=False)
        elif key=="overdue_bucket" and "روزهای تأخیر" in df.columns:
            d=pd.to_numeric(df["روزهای تأخیر"],errors="coerce").fillna(0);labs=["بدون تأخیر","۱ تا ۷ روز","۸ تا ۳۰ روز","۳۱ تا ۶۰ روز","بیش از ۶۰ روز"];vals=[int((d<=0).sum()),int(((d>0)&(d<=7)).sum()),int(((d>7)&(d<=30)).sum()),int(((d>30)&(d<=60)).sum()),int((d>60).sum())];bar(key,labs,vals,color=ORANGE)
        elif key=="org_workload":
            vc=counts(["ORG_DEPT","ORG_VICE"]);bar(key,vc.index,vc.values,color=THEME)
        elif key=="expert_workload":
            vc=counts(["CANONICAL_EXPERT"]);bar(key,vc.index,vc.values,color=NAVY)
        elif key=="transport_mix":
            vc=counts(["TRANSPORT_MODE","CL_TRANSPORT_MODE_CODE","MOGH_TRANSPORT_MODE_CODE"]);donut(key,vc.index,vc.values)
        elif key=="stage_distribution":
            vc=counts(["STAGE_FA","ORDER_STAGE_FA","LIFECYCLE_STAGE"]);bar(key,vc.index,vc.values,color=THEME)
        elif key=="bottlenecks":
            x=(extras or {}).get("bottlenecks") if extras else None
            if isinstance(x,pd.DataFrame) and not x.empty and {"از فعالیت","به فعالیت"}.issubset(x.columns):
                val=next((c for c in x.columns if "میانگین" in str(c)),None)
                if val:
                    xx=x.head(10);bar(key,[f"{a} ← {b}" for a,b in zip(xx["از فعالیت"],xx["به فعالیت"])],pd.to_numeric(xx[val],errors="coerce").fillna(0),color=ORANGE)
                    continue
            vc=counts(["STAGE_FA","ORDER_STAGE_FA","LIFECYCLE_STAGE"]);bar(key,vc.index,vc.values,color=ORANGE,title=CHART_TITLES[key]+" — جایگزین: مرحله فعلی")
        elif key=="top_orders":
            vc=counts(["CANONICAL_ORDER","KEY_ORDER"]);bar(key,vc.index,vc.values,color=THEME)
        elif key=="top_bl":
            vc=counts(["CANONICAL_BL","KEY_BL"]);bar(key,vc.index,vc.values,color=NAVY)
        elif key=="supplier_mix":
            vc=counts(["SUPPLIER","VENDOR_CODE","MFR_VENDOR_CODE"]);bar(key,vc.index,vc.values,color=THEME)
        elif key=="trend_critical": trend(key,"متریال بحرانی")
        elif key=="trend_commitment": trend(key,"مانده تعهد معوق")
        elif key=="trend_resistance": trend(key,"میانگین مقاومت")
        elif key=="delay_vs_commitment":
            scatter(key,"روزهای تأخیر","مانده تعهد","روزهای تأخیر","مانده تعهد")
        elif key=="pareto_delay" and "روزهای تأخیر" in df.columns:
            kc=_first_col(df,["CANONICAL_ORDER","KEY_REG","CANONICAL_BL"])
            if kc:
                x=df[[kc,"روزهای تأخیر"]].copy()
                x["روزهای تأخیر"]=pd.to_numeric(x["روزهای تأخیر"],errors="coerce")
                # بیشینه بر هر پرونده، نه جمع: تأخیر یک ویژگی پرونده است و
                # جمع‌زدن آن روی ردیف‌های تکراری عدد را چند برابر می‌کند.
                x=x.dropna(); x=x[x["روزهای تأخیر"]>0].groupby(kc)["روزهای تأخیر"].max()
                pareto(key,list(x.items()))
    return out

def executive_kpis(df:pd.DataFrame)->list[dict[str,Any]]:
    def unique(mask,key): return int(df.loc[mask,key].replace("",pd.NA).nunique()) if key in df.columns else 0
    crit_mat=int(df.loc[df["کد طبقه بحرانی"].isin(["STOCKOUT","CRITICAL"]),"KEY_MATERIAL"].replace("",pd.NA).nunique()) if {"کد طبقه بحرانی","KEY_MATERIAL"}.issubset(df.columns) else 0
    crit_bl=unique(df["BL_CRITICAL"].astype(bool),"CANONICAL_BL") if "BL_CRITICAL" in df.columns else 0
    crit_ord=unique(df["ORDER_CRITICAL"].astype(bool),"CANONICAL_ORDER") if "ORDER_CRITICAL" in df.columns else 0
    low=pd.to_numeric(df.get("مقاومت (روز)"),errors="coerce").min()
    overdue=int((pd.to_numeric(df["روزهای تأخیر"],errors="coerce").fillna(0)>0).sum()) if "روزهای تأخیر" in df.columns else 0
    cov_measured = ("COMMERCIAL_COVERAGE_STATE" in df.columns
                    and (df["COMMERCIAL_COVERAGE_STATE"] == "measured").any())
    missing_commercial = unique(df["ORDER_MISSING_COMMERCIAL_EXPERT"].astype(bool), "CANONICAL_ORDER") if "ORDER_MISSING_COMMERCIAL_EXPERT" in df.columns else 0
    return [{"label":"متریال بحرانی","value":crit_mat,"tone":"red","note":"توقف خط + بحرانی"},{"label":"بارنامه بحرانی","value":crit_bl,"tone":"red","note":"علت تا متریال مشخص است"},{"label":"سفارش بحرانی","value":crit_ord,"tone":"amber","note":"علت تا متریال مشخص است"},{"label":"کمترین مقاومت","value":"—" if pd.isna(low) else f"{low:.1f} روز","tone":"red" if pd.notna(low) and low<10 else "green","note":"بحرانی‌ترین وضعیت"},{"label":"تعهدات معوق","value":overdue,"tone":"amber" if overdue else "green","note":"نیازمند پیگیری"},{"label":"سفارش خارج از Commercial Expert Data","value":missing_commercial if cov_measured else "سنجیده نشد","tone":("red" if missing_commercial else "green") if cov_measured else "amber","note":"بدون انتساب کارشناس خرید" if cov_measured else "سورس خرید بارگذاری نشد"}]

def _health_banner(folder)->str:
    """اگر داده امروز ناقص بود، خواننده باید **قبل از اعداد** بداند.

    بدون این بنر، «۰ سفارش خارج از Commercial Expert Data» و «فایل
    بارگذاری نشد» در ایمیل یک شکل دارند.
    """
    from .. import health as _h
    data=_h.load(str(folder))
    if not data: return ""
    verdict=data.get("verdict",""); blocking=data.get("blocking") or []
    if verdict==_h.OK and not blocking: return ""
    c=data.get("counts",{})
    bits=[f"وضعیت داده امروز: <b>{html.escape(str(verdict))}</b>"]
    if blocking: bits.append("سورس الزامیِ ناموجود: "+html.escape("، ".join(blocking)))
    bits.append(f"سورس سالم/ناقص/خراب: {c.get('سورس سالم',0)} / "
                f"{c.get('سورس ناقص',0)} / {c.get('سورس خراب/ردشده',0)}")
    return (f'<div style="background:{ORANGE}1a;border-right:4px solid {ORANGE};'
            f'padding:10px 14px;border-radius:8px;margin:0 0 14px;font-size:13px;'
            f'color:{TEXT}">⚠️ ' + " — ".join(bits) +
            ' <div style="font-size:12px;margin-top:4px">جزئیات سلامت، lineage و اجرای منبع در Studio و HTML قابل ردیابی است. KPIهای وابسته به سورس‌های ناقص را با احتیاط بخوانید.</div></div>')

#: رنگ متن KPI از پالت سنجیده‌شده می‌آید، نه از ثابت‌های قدیمی ماژول.
#: ``#F39C12`` روی کارت سفید کنتراست ۱٫۹ داشت — عملاً ناخوانا، و دقیقاً
#: روی همان عددی نشسته بود که باید دیده می‌شد.
#: خط بالای کارت هم از همان پله تیره می‌آید، نه از نارنجی اصلی. یک نوار
#: ۴ پیکسلی حامل معناست (کدام KPI هشدار است) و طبق WCAG 1.4.11 باید کف ۳
#: را بگذراند؛ ``#F39C12`` روی سفید ۱٫۹ داشت.
_TONE_INK = {"red": ds.STATUS["critical"].ink, "amber": ds.STATUS["serious"].ink,
             "green": ds.STATUS["good"].ink}


#: حداکثر کارت KPI در یک ردیف جدول ایمیل.
#: تا نسخه ۲۶٫۱۸ همه کارت‌ها در یک ``<tr>`` با ``width:20%`` می‌رفتند؛ با شش
#: KPI مجموع عرض ۱۲۰٪ می‌شد و Outlook کارت آخر را می‌فشرد تا برچسب بلندی
#: مثل «سفارش خارج از Commercial Expert Data» از کارت بیرون بزند.
KPI_PER_ROW = 3


def _kpi_cards(kpis:Iterable[dict[str,Any]])->str:
    items=list(kpis)
    if len(items) > KPI_PER_ROW:
        # چیدمان شبکه‌ای: هر ردیف حداکثر KPI_PER_ROW کارت، عرض همیشه ۱۰۰٪
        rows=[items[i:i+KPI_PER_ROW] for i in range(0,len(items),KPI_PER_ROW)]
        return "".join(_kpi_cards(r) for r in rows)
    width=f"{100//max(len(items),1)}%"
    cards=[]
    for k in items:
        ink=rule=_TONE_INK.get(k.get("tone"),ds.BRAND_INK)
        delta=str(k.get("delta") or "").strip()
        dhtml=(f'<div style="font-size:11px;font-weight:700;color:{ink};margin-top:3px">{html.escape(delta)}</div>'
               if delta else "")
        cards.append(
            f'<td style="width:{width};padding:7px;font-family:{EMAIL_FONT};vertical-align:top">'
            f'<div style="background:#fff;border:1px solid {BORDER};border-top:4px solid {rule};border-radius:12px;padding:13px;text-align:center;font-family:{EMAIL_FONT}">'
            f'<div style="font-size:12px;color:{ds.TEXT_SECONDARY};font-family:{EMAIL_FONT}">{html.escape(str(k["label"]))}</div>'
            f'<div style="font-size:25px;font-weight:800;color:{ink};margin:4px 0">{html.escape(str(k["value"]))}</div>'
            f'{dhtml}<div style="font-size:10px;color:{ds.TEXT_MUTED}">{html.escape(str(k.get("note","")))}</div></div></td>')
    return "<tr>"+"".join(cards)+"</tr>"


def _attach_deltas(kpis: list, trend: Dict[str, Any]) -> list:
    """نشان «نسبت به اجرای قبلی» را روی KPIهای متناظر می‌نشاند.

    یک عدد بدون مبنای مقایسه در ایمیل مدیریتی تقریباً بی‌مصرف است:
    «۵۴ متریال بحرانی» نه خوب است نه بد تا وقتی معلوم نشود دیروز چند بود.
    """
    deltas = (trend or {}).get("deltas") or {}
    by_label = {"متریال بحرانی": "متریال بحرانی", "تعهدات معوق": "مانده تعهد معوق"}
    for k in kpis:
        metric = by_label.get(str(k.get("label")))
        d = deltas.get(metric) if metric else None
        if not d:
            continue
        arrow = "▲" if d["change"] > 0 else ("▼" if d["change"] < 0 else "■")
        word = "بهبود" if d.get("improving") else ("بدتر" if d.get("improving") is False else "بدون تغییر")
        pct = f" ({abs(d['pct']):.0f}٪)" if d.get("pct") else ""
        k["delta"] = f"{arrow} {abs(d['change']):,.0f}{pct} {word}"
    return kpis


def _story_block(df: pd.DataFrame, extras: Optional[Dict[str, Any]],
                 trend: Dict[str, Any], day: date) -> tuple:
    """(HTML روایت، KPIهای دارای نشان تغییر).

    ساخت روایت هرگز نباید مانع ارسال ایمیل شود؛ هر شکستی به بلوک خالی
    تبدیل می‌شود و بقیه ایمیل دست‌نخورده می‌ماند.
    """
    kpis = executive_kpis(df)
    try:
        from ..report.storytelling import build_story
        st = build_story(df, extras or {}, trend, ref_date=f"{day:%Y-%m-%d}")
    except Exception as ex:
        log.debug("ساخت روایت ایمیل رد شد: %s", ex)
        return "", kpis
    kpis = _attach_deltas(kpis, trend)
    font = EMAIL_FONT
    scr = "".join(
        f'<td width="33%" style="padding:0 6px;vertical-align:top;font-family:{font}">'
        f'<div style="background:#fff;border:1px solid {BORDER};border-radius:10px;padding:12px;height:100%">'
        f'<div style="font-size:10px;font-weight:800;color:{ds.BRAND_INK};letter-spacing:.3px">{lab}</div>'
        f'<div style="font-size:12.5px;color:{ds.TEXT_SECONDARY};margin-top:5px;line-height:1.85">{html.escape(txt)}</div>'
        f'</div></td>'
        for lab, txt in (("وضعیت", st.situation), ("گره", st.complication), ("اقدام", st.resolution))
        if txt)
    findings = "".join(
        f'<tr><td style="padding:5px 0;font-family:{font}">'
        f'<div style="background:#fff;border:1px solid {BORDER};border-right:4px solid {f.color};border-radius:10px;padding:11px 13px">'
        f'<div style="font-size:11px;font-weight:800;color:{f.color}">{html.escape(f.headline)}</div>'
        f'<div style="font-size:13.5px;font-weight:700;color:{ds.TEXT};margin:3px 0">{html.escape(f.magnitude)}</div>'
        f'<div style="font-size:11px;color:{ds.TEXT_MUTED}">{html.escape(f.comparison)}</div>'
        f'<div style="font-size:12px;color:{ds.TEXT_SECONDARY};margin-top:6px;border-top:1px dashed {BORDER};padding-top:6px">'
        f'<span style="color:{f.color};font-weight:800">←</span> {html.escape(f.so_what)}</div>'
        f'</div></td></tr>'
        for f in st.findings[:4])
    block = (
        f'<div style="background:{ds.SURFACE_SUNKEN};border:1px solid {BORDER};border-top:4px solid {THEME};'
        f'border-radius:13px;padding:16px 17px;margin:0 0 18px;font-family:{font}">'
        f'<div style="font-size:10px;font-weight:800;color:{ds.BRAND_INK};letter-spacing:.5px">◈ مسیر تصمیم</div>'
        f'<div style="font-size:17px;font-weight:800;color:{ds.TEXT};margin:5px 0 12px;line-height:1.7">{html.escape(st.headline)}</div>'
        + (f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{font}"><tr>{scr}</tr></table>' if scr else "")
        + (f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;font-family:{font}">{findings}</table>' if findings else "")
        + '</div>')
    return block, kpis

def build_email_html(day: date, df: pd.DataFrame, charts: list[Path], report_file: Path,
                     *, header_title: str = "هوشمندی روزانه زنجیره تأمین خودرو",
                     intro_text: str = "",
                     header_subtitle: str = "تأمین قطعه · ارز · حمل بین‌الملل · گمرک · پشتیبانی تولید",
                     process_extras: Optional[Dict[str, Any]] = None,
                     show_story: bool = True,
                     footer_note: str = "") -> str:
    """Executive email body with user-editable header, intro and narrative.

    Outlook is conservative about CSS inheritance, therefore the IRANSans font
    stack is repeated on major tables/cells instead of relying on one body rule.

    ``show_story`` بلوک «مسیر تصمیم» را کنترل می‌کند: سرخط، ساختار
    وضعیت/گره/اقدام و حداکثر چهار یافته کمّی، هر کدام با اقدام مشخص.
    ``process_extras`` لاگ فرآیند را می‌دهد تا گلوگاه هم وارد روایت شود.
    """
    report_file=Path(report_file)
    font=EMAIL_FONT
    trend=_trend_data()
    story_html,kpis=(_story_block(df,process_extras,trend,day) if show_story
                     else ("",_attach_deltas(executive_kpis(df),trend)))
    img="".join(
        f'<tr><td style="padding:8px 0;font-family:{font}"><img src="cid:chart_{i}" width="100%" '
        f'style="display:block;border:1px solid {BORDER};border-radius:10px" alt="AIBL chart"></td></tr>'
        for i,_ in enumerate(charts,1))
    rows=[]
    if "BL_CRITICAL" in df.columns:
        g=df[df["BL_CRITICAL"].astype(bool)].drop_duplicates("CANONICAL_BL").head(6) if "CANONICAL_BL" in df.columns else df.iloc[0:0]
        for _,r in g.iterrows(): rows.append((r.get("CANONICAL_BL","—"),r.get("BL_CRITICAL_MATERIALS","—"),r.get("BL_CRITICAL_REASON","—")))
    table="".join(
        f'<tr style="font-family:{font}"><td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(a))}</td>'
        f'<td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(b))}</td>'
        f'<td style="padding:7px;border-bottom:1px solid {BORDER}">{html.escape(str(c))}</td></tr>' for a,b,c in rows)
    cause=(f'<div style="margin:18px 0 8px;font-size:16px;font-weight:800;color:{NAVY};font-family:{font}">نمونه بارنامه‌های بحرانی و علت</div>'
           f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px;font-family:{font}">'
           f'<tr style="background:{THEME};color:#fff"><th style="padding:8px">بارنامه</th><th style="padding:8px">متریال</th><th style="padding:8px">علت</th></tr>{table}</table>') if table else ""
    intro=(f'<div style="background:#f5faf8;border:1px solid {BORDER};border-radius:10px;padding:13px 15px;line-height:1.9;font-size:13px;font-family:{font};margin:0 0 16px">'
           f'{html.escape(intro_text).replace(chr(10),"<br>")}</div>') if str(intro_text or "").strip() else ""
    chain=(f'<div style="font-size:11px;color:#d9f1ed;margin-top:8px;font-family:{font}">'
           f'<b>زنجیره تأمین صنعت خودرو</b> &nbsp;·&nbsp; تأمین قطعه &nbsp;←&nbsp; ثبت سفارش و ارز &nbsp;←&nbsp; حمل بین‌الملل &nbsp;←&nbsp; گمرک و ترخیص &nbsp;←&nbsp; ورود قطعه &nbsp;←&nbsp; تولید خودرو</div>')
    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"></head>
<body style="margin:0;background:{BG};font-family:{font};color:{TEXT}">
<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{font}"><tr><td align="center" style="padding:18px 8px;font-family:{font}">
<table width="820" cellpadding="0" cellspacing="0" style="max-width:820px;width:100%;background:#fff;border:1px solid {BORDER};border-radius:16px;overflow:hidden;font-family:{font}">
<tr><td style="padding:22px 28px;background:{NAVY};font-family:{font}"><div style="color:#d9f1ed;font-size:10px;letter-spacing:.5px">AIBL · AUTOMOTIVE SUPPLY CHAIN INTELLIGENCE</div>
<div style="color:#fff;font-size:24px;font-weight:800;margin-top:5px;font-family:{font}">{html.escape(header_title)}</div>
<div style="color:#d9f1ed;font-size:13px;margin-top:5px;font-family:{font}">{html.escape(header_subtitle)} · {day:%Y-%m-%d}</div>{chain}</td></tr>
<tr><td style="padding:20px 24px;font-family:{font}">{intro}{_health_banner(report_file.parent)}{story_html}
<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{font}">{_kpi_cards(kpis)}</table>
<div style="margin:20px 0 12px;font-size:18px;font-weight:800;color:{NAVY};font-family:{font}">نمودارهای انتخاب‌شده برای تصمیم امروز</div>
<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{font}">{img}</table>
<div style="margin:18px 0 10px;font-size:17px;font-weight:800;color:{NAVY};font-family:{font}">چرا فایل HTML را باز کنیم؟</div>
<div style="background:#f5faf8;border:1px solid {BORDER};border-radius:10px;padding:14px;line-height:1.9;font-size:13px;font-family:{font}">در ایمیل فقط <b>سیگنال مدیریتی</b> را می‌بینید؛ جزئیات تصمیم در فایل <b>HTML تعاملی</b> است: فیلتر، نمودارهای منتخب، Process Explorer، متریال‌های بحرانی، مقاومت، تعهد ارزی و ردیابی پرونده. از داخل همان فایل می‌توانید تمام برش فعال را <b>Excel</b> بگیرید یا با «PDF / چاپ» به PDF ذخیره کنید.</div>
{cause}<div style="margin-top:20px;text-align:center;font-family:{font}"><span style="display:inline-block;background:{THEME};color:#fff;border-radius:9px;padding:11px 18px;font-weight:800">📎 {html.escape(report_file.name)}</span></div></td></tr>
<tr><td style="padding:14px 24px;background:#f7f9f9;color:{ds.TEXT_MUTED};font-size:11px;font-family:{font}">{html.escape(footer_note) if str(footer_note or '').strip() else 'این پیام توسط AIBL تولید شده است · منبع تحلیلی SQLite Warehouse است و فایل HTML snapshot قابل ردیابی همان اجراست.'}</td></tr>
</table></td></tr></table></body></html>"""

@contextmanager
def _outlook_session():
    """دسترسی به Outlook با COM مقداردهی‌شده در **همان نخ جاری**.

    خطای واقعی که در تولید رخ داد::

        (-2147221008, 'CoInitialize has not been called.', None, None)

    علت: Streamlit هر تعامل کاربر را روی یک نخ ScriptRunner تازه اجرا
    می‌کند. ``win32com`` فقط روی نخی کار می‌کند که پیش‌تر ``CoInitialize``
    روی آن صدا شده باشد؛ نخ اصلی مفسر این کار را کرده بود، نخ Streamlit نه.
    پس همان کدی که از خط فرمان بی‌عیب اجرا می‌شد، از داخل Studio می‌افتاد.

    این مدیر زمینه COM را روی نخ جاری بالا می‌آورد و **در هر مسیر خروج**
    — چه موفق چه با استثنا — پایین می‌آورد. نبودن ``CoUninitialize`` در
    مسیر خطا همان چیزی است که در اجرای طولانی Studio به نشت اشاره COM و
    خطاهای بعدیِ به‌ظاهر بی‌ربط منجر می‌شود.

    ``CoInitialize`` اگر روی نخی که قبلاً مقداردهی شده دوباره صدا شود،
    ``S_FALSE`` برمی‌گرداند نه خطا — و در آن حالت هم باید یک
    ``CoUninitialize`` متناظر داشته باشد، پس شمارش همیشه متوازن می‌ماند.
    """
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError as ex:
        raise RuntimeError(
            "برای ارسال با Outlook، pywin32 و Classic Outlook روی ویندوز لازم است:\n"
            "    python -m pip install pywin32") from ex
    pythoncom.CoInitialize()
    try:
        yield win32
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception as ex:          # پایین آمدن COM نباید خطای اصلی را بپوشاند
            log.debug("CoUninitialize نادیده گرفته شد: %s", ex)


def _select_sender(outlook, mail, *, fatal: bool) -> None:
    """حساب فرستنده را از ``AIBL_EMAIL_SENDER`` انتخاب می‌کند.

    ``fatal`` تفاوت رفتار دو مسیر را نگه می‌دارد: در ایمیل روزانه، ناتوانی
    در پیمایش حساب‌ها فقط هشدار است (ارسال با حساب پیش‌فرض ادامه می‌یابد)،
    ولی در Studio که کاربر عمداً فرستنده را انتخاب کرده، ارسال از حساب
    اشتباه بدتر از نفرستادن است.
    در هر دو مسیر، **پیدا نشدن** حساب درخواست‌شده خطای صریح است.
    """
    sender = os.environ.get("AIBL_EMAIL_SENDER", "").strip().lower()
    if not sender:
        return
    matched = False
    try:
        for account in outlook.Session.Accounts:
            if str(getattr(account, "SmtpAddress", "")).strip().lower() == sender:
                mail.SendUsingAccount = account
                matched = True
                break
    except Exception as ex:
        if fatal:
            raise RuntimeError(f"انتخاب حساب فرستنده Outlook ناموفق بود: {ex}") from ex
        log.warning("انتخاب حساب فرستنده ناموفق بود: %s", ex)
    if not matched:
        raise RuntimeError(f"حساب Outlook با نشانی فرستنده «{sender}» پیدا نشد.")


def _add_inline(mail,path:Path,cid:str)->None:
    att=mail.Attachments.Add(str(path.resolve()),1,0,path.name); acc=att.PropertyAccessor
    acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F",cid)
    try: acc.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3716001F","inline")
    except Exception: pass

def create_daily_email(*,day:Optional[date]=None,send:bool=False,display:bool=True,
                       subject:Optional[str]=None)->Dict[str,Any]:
    """Build one self-contained HTML report and optionally attach it in Outlook."""
    from ..pipeline import Pipeline
    from ..studio_core.html_export import build_dynamic_html
    from ..studio_core.field_catalog import build_catalog, unique_labels
    d=day or SETTINGS.today
    res=Pipeline(today=d).run(build_report=False)
    paths=daily_paths(d)
    raw_charts = os.environ.get("AIBL_EMAIL_CHARTS", "").strip()
    selected_charts = [x.strip() for x in raw_charts.split(",") if x.strip()] if raw_charts else ["criticality","low_resistance","stage_distribution","commitment"]
    fields=[c for c in ["KEY_MATERIAL","CANONICAL_ORDER","CANONICAL_BL","KEY_REG","CANONICAL_EXPERT","ORG_DEPT","TRANSPORT_MODE","بحرانی (کوتاه)","مقاومت (روز)","مانده تعهد","BL_CRITICAL_REASON","ORDER_CRITICAL_REASON","CASE_KEY"] if c in res.main.columns]
    labels=unique_labels(build_catalog(res.main)) if not res.main.empty else {}
    report=build_dynamic_html(res.main,str(d),title="AIBL — هوشمندی زنجیره تأمین خودرو",max_rows=5000,
        selected_fields=fields,labels=labels,template_title="◈ گزارش تعاملی روزانه زنجیره تأمین",
        show_visuals=True,show_tables=True,show_process=True,charts=selected_charts,process_extras=res.extras,
        lineage={"warehouse_run_id": res.warehouse_run_id} if res.warehouse_run_id else None)
    paths["report_html"].write_text(report,encoding="utf-8")
    charts=make_email_charts(res.main,paths["assets"],selected=selected_charts,extras=res.extras)
    body=build_email_html(d,res.main,charts,paths["report_html"],process_extras=res.extras)
    paths["html"].write_text(body,encoding="utf-8")
    to=_recipients()
    result={"report_html":paths["report_html"],"html":paths["html"],"charts":charts,"recipients":to,"sent":False}
    if not(send or display): return result
    if not to:
        raise NoRecipients(
            "هیچ گیرنده‌ای پیکربندی نشده است. AIBL_EMAIL_TO / recipients.yaml / AIBL_EMAIL_FROM_HR را تنظیم کنید.")
    with _outlook_session() as win32:
        outlook=win32.Dispatch("Outlook.Application")
        mail=outlook.CreateItem(0); mail.BodyFormat=2
        mail.Subject=subject or f"AIBL Executive Daily Insight — {d:%Y-%m-%d}"; mail.To="; ".join(to)
        _select_sender(outlook, mail, fatal=False)
        for i,ch in enumerate(charts,1): _add_inline(mail,ch,f"chart_{i}")
        if paths["report_html"].exists(): mail.Attachments.Add(str(paths["report_html"].resolve()))
        mail.HTMLBody=body; mail.Save()
        if send: mail.Send(); result["sent"]=True
        elif display: mail.Display()
    try:
        from ..warehouse import warehouse_from_settings
        warehouse_from_settings().audit("DAILY_HTML_EMAIL",run_id=res.warehouse_run_id or None,actor="email",entity_type="report",entity_id=paths["report_html"].name,message=f"recipients={len(to)} sent={result['sent']}")
    except Exception: pass
    return result

def create_studio_email(*, day: Optional[date], df: pd.DataFrame, html_report: Path,
                        selected_charts=None, process_extras: Optional[Dict[str, Any]]=None,
                        send: bool=False, display: bool=True,
                        subject: Optional[str]=None, to=None, cc=None,
                        header_title: Optional[str]=None, intro_text: str="",
                        footer_note: str="") -> Dict[str,Any]:
    """Compose Studio email; only the interactive HTML artifact is attached.

    ``to`` and ``cc`` accept strings separated by comma/semicolon or iterables.
    Addresses are never written to logs; only recipient counts are audited.
    """
    report = Path(html_report)
    if report.suffix.lower() not in (".html", ".htm"):
        raise ValueError("Studio فقط فایل HTML را ارسال می‌کند؛ Excel/PDF باید از داخل HTML ساخته شود.")
    if not report.exists():
        raise FileNotFoundError("فایل HTML گزارش برای پیوست پیدا نشد.")
    d=day or date.today()
    to_list=_addresses(to, _recipients())
    cc_list=_addresses(cc, [])
    if not to_list:
        raise NoRecipients("گیرنده TO تعیین نشده است. از Studio یا AIBL_EMAIL_TO / recipients.yaml / HR انتخاب کنید.")
    assets=report.parent/"studio_email_assets";assets.mkdir(parents=True,exist_ok=True)
    charts=make_email_charts(df,assets,selected=selected_charts,extras=process_extras or {})
    body=build_email_html(d,df,charts,report,
                          header_title=header_title or "هوشمندی زنجیره تأمین خودرو",
                          intro_text=intro_text or "",
                          process_extras=process_extras or {},
                          footer_note=footer_note or "")
    with _outlook_session() as win32:
        outlook=win32.Dispatch("Outlook.Application"); mail=outlook.CreateItem(0); mail.BodyFormat=2
        mail.Subject=subject or f"AIBL — گزارش زنجیره تأمین خودرو — {d:%Y-%m-%d}"
        mail.To="; ".join(to_list)
        if cc_list: mail.CC="; ".join(cc_list)
        _select_sender(outlook, mail, fatal=True)
        for i,ch in enumerate(charts,1): _add_inline(mail,ch,f"chart_{i}")
        mail.Attachments.Add(str(report.resolve())); mail.HTMLBody=body; mail.Save()
        if send: mail.Send()
        elif display: mail.Display()
    return {"sent":bool(send),"recipients":len(to_list),"cc":len(cc_list),"charts":len(charts),"report":report}

def main(argv=None)->int:
    import argparse
    ap=argparse.ArgumentParser(description="AIBL Executive Daily Insight email"); ap.add_argument("--send",action="store_true"); ap.add_argument("--no-display",action="store_true")
    a=ap.parse_args(argv); r=create_daily_email(send=a.send,display=not a.no_display)
    print(f"Report HTML: {r['report_html']}"); print(f"Email HTML: {r['html']}"); print(f"Charts: {len(r['charts'])}"); print(f"Recipients: {len(r['recipients'])}"); print(f"Sent: {r['sent']}"); return 0
if __name__=="__main__": raise SystemExit(main())

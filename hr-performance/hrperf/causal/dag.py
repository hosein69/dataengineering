# -*- coding: utf-8 -*-
"""گراف علّی — اعلام صریح فرض‌ها، و استخراج مجموعه تعدیل.

## چرا DAG لازم است

همبستگی برای قضاوت عملکرد کافی نیست. مثال واقعی همین دامنه: کسی که
پرونده‌های سخت‌تر می‌گیرد، طبیعتاً خطای بیشتری دارد. همبستگی خام
می‌گوید «این فرد ضعیف است»؛ در حالی که **سختی پرونده** یک مخدوش‌کننده
است که هم روی تخصیص کار اثر دارد هم روی خطا. اگر برایش تعدیل نکنیم،
فرد را بابت شرایطی که انتخاب نکرده جریمه کرده‌ایم.

DAG اینجا **فرض** است، نه کشف. صریح نوشته می‌شود تا قابل نقد باشد؛ و
مجموعه تعدیل با معیار درِ پشتی (back-door) از همان DAG استخراج می‌گردد.

> ⚠️ صداقت روش‌شناختی: با داده مشاهده‌ای نمی‌توان علیت را **اثبات** کرد.
> آنچه اینجا تولید می‌شود «اثر تعدیل‌شده تحت فرض‌های این DAG» است، نه
> اثر علّی قطعی. سنجه حساسیت (E-value) هم گزارش می‌شود تا معلوم باشد یک
> مخدوش‌کننده اندازه‌گیری‌نشده چقدر باید قوی باشد تا نتیجه را برگرداند.
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set, Tuple


@dataclass
class DAG:
    """گراف جهت‌دار بدون دور. یال ``a → b`` یعنی a علتِ فرضیِ b است."""
    edges: List[Tuple[str, str]] = field(default_factory=list)

    # ── ساخت ──
    def add(self, cause: str, effect: str) -> "DAG":
        if (cause, effect) not in self.edges:
            self.edges.append((cause, effect))
        return self

    @property
    def nodes(self) -> List[str]:
        s: List[str] = []
        for a, b in self.edges:
            for x in (a, b):
                if x not in s:
                    s.append(x)
        return s

    def parents(self, node: str) -> Set[str]:
        return {a for a, b in self.edges if b == node}

    def children(self, node: str) -> Set[str]:
        return {b for a, b in self.edges if a == node}

    def ancestors(self, node: str) -> Set[str]:
        out, stack = set(), list(self.parents(node))
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(self.parents(n))
        return out

    def descendants(self, node: str) -> Set[str]:
        out, stack = set(), list(self.children(node))
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(self.children(n))
        return out

    def has_cycle(self) -> bool:
        color: Dict[str, int] = {}

        def visit(n: str) -> bool:
            if color.get(n) == 1:
                return True
            if color.get(n) == 2:
                return False
            color[n] = 1
            for c in self.children(n):
                if visit(c):
                    return True
            color[n] = 2
            return False

        return any(visit(n) for n in self.nodes)

    # ── معیار درِ پشتی ──
    def backdoor_set(self, treatment: str, outcome: str) -> Set[str]:
        """مجموعه تعدیل به روش «والدینِ درمان».

        والدین treatment همه مسیرهای درِ پشتی را می‌بندند و — چون هیچ‌کدام
        از نوادگان treatment نیستند — مسیر جلویی را باز نگه می‌دارند. این
        شرطِ کافیِ استانداردِ back-door است و برای DAGهای این اندازه امن و
        قابل دفاع است.
        """
        desc = self.descendants(treatment) | {treatment, outcome}
        return {p for p in self.parents(treatment) if p not in desc}

    def mediators(self, treatment: str, outcome: str) -> Set[str]:
        """گره‌هایی که روی مسیر treatment → … → outcome قرار دارند."""
        return (self.descendants(treatment) & self.ancestors(outcome)) - {treatment, outcome}


#: DAG پیش‌فرض دامنه — بر پایه رویه واقعی کار، و قابل ویرایش
#:
#: منطق: تخصیص کار (اداره/مدیریت/نوع کار) هم حجم و سختی را تعیین می‌کند،
#: هم مستقیماً روی کیفیت اثر دارد ⇒ مخدوش‌کننده. تجربه هم روی سرعت اثر
#: دارد هم روی کیفیت. حجم از راه سرعت روی کیفیت اثر می‌گذارد (میانجی).
DEFAULT_DAG = (
    DAG()
    .add("assignment", "workload")          # تخصیص کار → حجم
    .add("assignment", "difficulty")        # تخصیص کار → سختی پرونده
    .add("assignment", "reliability")       # اثر مستقیم واحد/حوزه
    .add("tenure", "conformance")           # تجربه → انطباق با مسیر مرجع
    .add("tenure", "responsiveness")        # تجربه → پاسخ‌گویی
    .add("workload", "responsiveness")      # حجم → کندی
    .add("difficulty", "reliability")
    .add("difficulty", "responsiveness")
    .add("responsiveness", "reliability")   # عجله یا کندی → نتیجه
    .add("conformance", "reliability")      # انحراف از مسیر → نتیجهٔ بد
    .add("data_quality", "conformance")     # داده ناقص → انحراف دیده‌نشده
    .add("conformance", "stewardship")
    .add("responsiveness", "stewardship")
)

#: نگاشت گره DAG به کلاستر مدل
NODE_TO_CLUSTER = {
    "reliability": "reliability", "conformance": "conformance",
    "responsiveness": "responsiveness", "stewardship": "stewardship",
    "data_quality": "data_quality", "collaboration": "collaboration",
    "workload": "workload",
}
NODE_FA = {
    "assignment": "تخصیص کار (اداره/مدیریت/نوع کار)",
    "workload": "حجم کار",
    "difficulty": "سختی پرونده",
    "tenure": "سابقه/تجربه",
    "reliability": "اتکاپذیری تحویل",
    "conformance": "انطباق فرآیند",
    "responsiveness": "پاسخ‌گویی در حوزه",
    "stewardship": "صیانت از تعهد و اسناد",
    "data_quality": "کیفیت داده",
    "collaboration": "همکاری",
}

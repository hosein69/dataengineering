# -*- coding: utf-8 -*-
"""گراف سازمانی — بار روی چه کسی متمرکز است، و کجا تک‌نقطه شکست داریم.

## چرا گراف، و نه فقط جدول

جدول می‌گوید هرکس چند پرونده دارد. گراف می‌گوید **کارِ چه کسی از مسیر چه
کسی می‌گذرد**. این دو یکی نیستند و تفاوتشان دقیقاً همان‌جایی است که
بی‌عدالتی پنهان می‌ماند:

کسی ممکن است پرونده کمی داشته باشد ولی روی مسیر ده جریان کاری باشد. بارِ
واقعی او در هیچ شمارشی دیده نمی‌شود، ولی اگر مرخصی برود ده جریان می‌خوابد.
او هم بیش‌بار است، هم در ارزیابی کم‌امتیاز — و این بدترین ترکیب ممکن است.

## سنجه‌ها

* **درجه وزنی** — مجموع باری که از این گره می‌گذرد. ساده و بی‌واسطه.
* **مرکزیت بینابینی** (Freeman, 1977؛ الگوریتم Brandes, 2001) — چند مسیر
  کوتاه بین بقیه از این گره عبور می‌کند. این همان «تک‌نقطه شکست» است.
* **اندازه مؤلفه** — آیا شبکه یکپارچه است یا چند جزیره جدا.

Brandes به‌جای الگوریتم ساده $O(n^3)$، در $O(nm)$ کار می‌کند و بدون هیچ
کتابخانه بیرونی پیاده شده تا وابستگی تازه‌ای به پکیج اضافه نشود.

## قاعده

گراف **هیچ امتیازی را عوض نمی‌کند**. خروجی‌اش زمینه است: وقتی می‌گوییم
«این فرد امتیاز پایینی گرفته»، گراف می‌تواند بگوید «ولی روی مسیر شش
جریان کاری است». تصمیم با انسان است، ولی با اطلاعات کامل‌تر.
"""
from __future__ import annotations

__contract__ = 1

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

#: زیر این تعداد گره، مرکزیت گزارش نمی‌شود — در شبکه چهارتایی هر عددی
#: صرفاً بازتاب شکل شبکه است، نه یافته.
MIN_NODES = 5


@dataclass
class Node:
    key: str
    label: str = ""
    group: str = ""
    load: float = 0.0
    degree: int = 0
    w_degree: float = 0.0
    betweenness: float = 0.0
    component: int = 0

    @property
    def bottleneck(self) -> bool:
        return self.betweenness > 0


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: Dict[Tuple[str, str], float] = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.nodes)

    def neighbours(self, key: str) -> List[str]:
        out = []
        for (a, b) in self.edges:
            if a == key:
                out.append(b)
            elif b == key:
                out.append(a)
        return out

    def adjacency(self) -> Dict[str, List[str]]:
        adj: Dict[str, List[str]] = {k: [] for k in self.nodes}
        for (a, b) in self.edges:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        return adj

    def table(self) -> pd.DataFrame:
        rows = [{
            "گره": v.label or v.key, "گروه": v.group,
            "بار": round(v.load, 2), "درجه": v.degree,
            "درجه وزنی": round(v.w_degree, 2),
            "مرکزیت بینابینی": round(v.betweenness, 4),
            "مؤلفه": v.component,
        } for v in self.nodes.values()]
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values(["مرکزیت بینابینی", "درجه وزنی"],
                                ascending=False, ignore_index=True)
        return df

    def top(self, k: int = 10) -> List[Node]:
        return sorted(self.nodes.values(),
                      key=lambda v: (v.betweenness, v.w_degree), reverse=True)[:k]


def build(df: pd.DataFrame, source: str, target: str,
          weight: Optional[str] = None, group: Optional[str] = None,
          labels: Optional[Dict[str, str]] = None) -> Graph:
    """گراف بدون‌جهت از دو ستون — هر ردیف یک یال.

    وزن یال، مجموع بار ردیف‌هایی است که آن دو سر را به هم وصل می‌کنند.
    """
    g = Graph()
    if source not in df.columns or target not in df.columns:
        return g
    labels = labels or {}
    w = (pd.to_numeric(df[weight], errors="coerce").fillna(0.0)
         if weight and weight in df.columns
         else pd.Series(1.0, index=df.index))
    grp = (df[group].fillna("").astype(str) if group and group in df.columns
           else pd.Series("", index=df.index))

    a_all = df[source].fillna("").astype(str).str.strip()
    b_all = df[target].fillna("").astype(str).str.strip()
    for i in df.index:
        a, b = a_all[i], b_all[i]
        if not a or not b or a == b:
            continue
        for key, gval in ((a, ""), (b, grp[i])):
            if key not in g.nodes:
                g.nodes[key] = Node(key=key, label=labels.get(key, key), group=gval)
        val = float(w[i])
        g.nodes[a].load += val
        g.nodes[b].load += val
        e = (a, b) if a < b else (b, a)
        g.edges[e] = g.edges.get(e, 0.0) + val
    _metrics(g)
    return g


def _metrics(g: Graph) -> None:
    for (a, b), wt in g.edges.items():
        for k in (a, b):
            g.nodes[k].degree += 1
            g.nodes[k].w_degree += wt
    _components(g)
    if g.n >= MIN_NODES:
        _brandes(g)


def _components(g: Graph) -> None:
    adj = g.adjacency()
    seen: Dict[str, int] = {}
    cid = 0
    for start in g.nodes:
        if start in seen:
            continue
        cid += 1
        q = deque([start])
        seen[start] = cid
        while q:
            cur = q.popleft()
            for nb in adj.get(cur, []):
                if nb not in seen:
                    seen[nb] = cid
                    q.append(nb)
    for k, v in seen.items():
        g.nodes[k].component = v


def _brandes(g: Graph) -> None:
    """مرکزیت بینابینی — الگوریتم Brandes (2001)، بدون وزن یال.

    یال بی‌وزن عمدی است: پرسش «چند مسیر از این گره می‌گذرد» است، نه
    «چقدر بار». بار را ``w_degree`` جداگانه می‌گوید.
    """
    adj = g.adjacency()
    bc = {k: 0.0 for k in g.nodes}
    for s in g.nodes:
        stack: List[str] = []
        preds: Dict[str, List[str]] = {k: [] for k in g.nodes}
        sigma = {k: 0.0 for k in g.nodes}
        dist = {k: -1 for k in g.nodes}
        sigma[s], dist[s] = 1.0, 0
        q = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in adj.get(v, []):
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    preds[w].append(v)
        delta = {k: 0.0 for k in g.nodes}
        while stack:
            w = stack.pop()
            for v in preds[w]:
                if sigma[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
            if w != s:
                bc[w] += delta[w]
    # گراف بدون‌جهت: هر جفت دو بار شمرده شده؛ و نرمال‌سازی به [۰,۱]
    scale = (g.n - 1) * (g.n - 2)
    for k, v in bc.items():
        g.nodes[k].betweenness = (v / scale) if scale > 0 else 0.0


@dataclass
class Hidden:
    """کسی که بارش در شمارش دیده نمی‌شود ولی روی مسیر کار دیگران است."""
    key: str
    label: str
    load: float
    betweenness: float
    load_rank: int
    between_rank: int

    @property
    def gap(self) -> int:
        """چقدر رتبه‌اش در «مسیر بودن» از رتبه‌اش در «بار» بالاتر است."""
        return self.load_rank - self.between_rank


def hidden_load(g: Graph, min_gap: int = 3) -> List[Hidden]:
    """گره‌هایی که مرکزیتشان خیلی بیشتر از بارِ شمرده‌شده‌شان است.

    این‌ها همان‌هایی‌اند که در ارزیابی معمول نامرئی می‌مانند: کار زیادی
    از دستشان می‌گذرد ولی چیز زیادی به نامشان ثبت نمی‌شود.
    """
    if g.n < MIN_NODES:
        return []
    by_load = sorted(g.nodes.values(), key=lambda v: v.w_degree, reverse=True)
    by_btw = sorted(g.nodes.values(), key=lambda v: v.betweenness, reverse=True)
    lr = {v.key: i + 1 for i, v in enumerate(by_load)}
    br = {v.key: i + 1 for i, v in enumerate(by_btw)}
    out = [Hidden(v.key, v.label or v.key, v.w_degree, v.betweenness,
                  lr[v.key], br[v.key])
           for v in g.nodes.values()
           if v.betweenness > 0 and lr[v.key] - br[v.key] >= min_gap]
    out.sort(key=lambda h: h.gap, reverse=True)
    return out

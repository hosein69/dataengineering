# -*- coding: utf-8 -*-
"""خط لوله عملکرد — از سورس تا امتیاز، اثر علّی و پایگاه داده.

ترتیب مراحل، و دلیل هرکدام:

    ۱۰ ingest      خواندن سورس‌ها به قالب بلند واحد
    ۲۰ identity    تطبیق هویت و جای‌گذاری سازمانی
    ۳۰ peers       تعیین گروه همتا (مقایسه فقط درون گروه)
    ۴۰ derive      شاخص‌های محاسبه‌شده (ورود غیرمستقیم به کلاستر)
    ۵۰ normalize   انقباض کالیبره‌شده + امتیاز مقاوم نسبت به مرجع
    ۶۰ aggregate   تجمیع دو سطحی: آیتم → کلاستر → عملکرد
    ۷۰ causal      اثر تعدیل‌شده و امتیاز منصفانه
    ۸۰ persist     نوشتن در پایگاه داده به‌عنوان یک run
"""
from __future__ import annotations

__contract__ = 1

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .causal import dag as dagmod
from .causal.effects import effect_table, fair_score
from .config.model import PerformanceModel, load_model
from .config.settings import SETTINGS
from .dataio import db as dbmod
from .dataio.sources import load_inputs, read_org_map
from .identity import peers as peermod
from .metrics.derive import apply_derived
from .score.aggregate import ScoreResult, aggregate
from .score.normalize import (build_reference, calibrate_k, evidence,
                              percentile_context, robust_score, shrink)
from .version import VERSION


class NoInputData(RuntimeError):
    """هیچ سورس قابل استفاده‌ای پیدا نشد."""

#: نام فارسی ستون‌های جدول عملکرد (خروجی‌ها همه فارسی‌اند)
LEADERBOARD_FA = {
    "person_key": "کد", "full_name": "نام", "management": "مدیریت",
    "department": "اداره", "job_family": "نوع کار", "role": "نقش",
    "peer_group": "گروه همتا",
}


@dataclass
class RunResult:
    people: pd.DataFrame
    long: pd.DataFrame
    metric_raw: pd.DataFrame
    metric_scores: pd.DataFrame
    sample_n: pd.DataFrame
    scores: ScoreResult
    effects: pd.DataFrame
    fair: pd.DataFrame
    peer_summary: pd.DataFrame
    calibration: pd.DataFrame
    model: PerformanceModel
    run_id: Optional[int] = None
    warnings: List[str] = field(default_factory=list)

    @property
    def leaderboard(self) -> pd.DataFrame:
        p = self.people.set_index("person_key")
        out = pd.DataFrame({
            "عملکرد": self.scores.performance.round(1),
            "امتیاز منصفانه": self.fair["fair"].round(1)
            if "fair" in self.fair.columns else np.nan,
            "پوشش": self.scores.coverage.round(2),
            "شواهد": self.scores.evidence.round(2),
            "اطمینان": self.scores.confidence.round(2),
        })
        for c in ("full_name", "management", "department", "job_family",
                  "role", "peer_group"):
            if c in p.columns:
                out[c] = p[c]
        out.index.name = "person_key"
        out = out.reset_index()
        out = out.rename(columns=LEADERBOARD_FA)
        # رتبه فقط درون گروه همتا معنا دارد
        if "peer_group" in out.columns:
            out["رتبه در گروه"] = (out.groupby("peer_group")["عملکرد"]
                                   .rank(ascending=False, method="min"))
            out["نفرات گروه"] = out.groupby("peer_group")["عملکرد"].transform("size")
        return out.sort_values("عملکرد", ascending=False)


def _pivot(long: pd.DataFrame, value_col: str,
           people: List[str], metrics: List[str]) -> pd.DataFrame:
    if long.empty:
        return pd.DataFrame(index=people, columns=metrics, dtype=float)
    p = (long.pivot_table(index="person_key", columns="metric_key",
                          values=value_col, aggfunc="mean")
         .reindex(index=people, columns=metrics))
    return p.astype(float)


class Pipeline:
    def __init__(self, model: Optional[PerformanceModel] = None,
                 input_dir: Optional[str] = None,
                 db_path: Optional[str] = None):
        self.model = model or load_model()
        self.input_dir = input_dir or SETTINGS.INPUT_DIR
        self.db_path = db_path or SETTINGS.DB_PATH

    # ── اجرا ──
    def run(self, long: Optional[pd.DataFrame] = None,
            people: Optional[pd.DataFrame] = None,
            persist: bool = True, ref_date: Optional[str] = None) -> RunResult:
        warnings: List[str] = []
        ref_date = ref_date or str(SETTINGS.today)

        # ۱۰ ingest
        if long is None:
            long = load_inputs(self.input_dir)
        if long.empty:
            warnings.append("هیچ رکورد شاخصی از سورس‌ها خوانده نشد.")

        # ۲۰ identity
        if people is None:
            people = self._people_from(long)
        people = people.copy()
        if people.empty or "person_key" not in people.columns:
            raise NoInputData(
                "هیچ فردی برای سنجش پیدا نشد.\n"
                f"  • فایل‌های خروجی واحدها را در «{self.input_dir}» بگذارید،\n"
                "  • یا برای دموی بدون شبکه: python -m hrperf.cli demo")
        people["person_key"] = people["person_key"].astype(str).str.strip()

        # ۳۰ peers
        peer = peermod.assign(people)
        people = people.merge(peer, on="person_key", how="left")
        peer_summary = peermod.summary(peer)
        if bool(peer.get("peer_is_fallback", pd.Series(dtype=bool)).any()):
            n = int(peer["peer_is_fallback"].sum())
            warnings.append(
                f"{n} نفر به‌دلیل کوچک بودن گروه، در سطح بالاتری مقایسه شدند.")

        keys = people["person_key"].tolist()
        mkeys = list(self.model.metrics)

        # ۴۰ derive
        long = apply_derived(long, self.model)

        raw = _pivot(long, "value", keys, mkeys)
        n_mat = _pivot(long, "sample_n", keys, mkeys)

        # ۵۰ normalize — انقباض درون گروه همتا
        scores = pd.DataFrame(index=keys, dtype=float)
        shrunk_all = pd.DataFrame(index=keys, dtype=float)
        pct = pd.DataFrame(index=keys, dtype=float)
        ev = pd.DataFrame(index=keys, dtype=float)
        calib: List[dict] = []
        group = people.set_index("person_key")["peer_group"]

        for m in self.model.metrics.values():
            x, n = raw.get(m.key), n_mat.get(m.key)
            if x is None or not x.notna().any():
                continue
            k = calibrate_k(x, n if n is not None else pd.Series(np.nan, index=x.index))
            sh = pd.Series(np.nan, index=x.index, dtype=float)
            sc = pd.Series(np.nan, index=x.index, dtype=float)
            pc = pd.Series(np.nan, index=x.index, dtype=float)
            for g, idx in group.groupby(group).groups.items():
                idx = [i for i in idx if i in x.index]
                if not idx:
                    continue
                xg = x.loc[idx]
                ng = (n.loc[idx] if n is not None
                      else pd.Series(np.nan, index=idx))
                prior = float(xg.mean(skipna=True)) if xg.notna().any() else np.nan
                sg = shrink(xg, ng, prior, k)
                sh.loc[idx] = sg
                sc.loc[idx] = robust_score(sg, m.direction, build_reference(sg, m.key))
                pc.loc[idx] = percentile_context(xg, m.direction)
            shrunk_all[m.key] = sh
            scores[m.key] = sc
            pct[m.key] = pc
            ev[m.key] = evidence(n if n is not None
                                 else pd.Series(np.nan, index=x.index), m.q_target)
            calib.append({"شاخص": m.label, "کلید": m.key, "k": round(k, 2),
                          "افراد دارای مقدار": int(x.notna().sum())})

        # ۶۰ aggregate
        result = aggregate(scores.reindex(index=keys), self.model,
                           ev.reindex(index=keys))

        # ۷۰ causal
        node_frame = self._causal_frame(result, raw, people)
        effects = effect_table(node_frame, dagmod.DEFAULT_DAG)
        drivers = [d for d in ("workload", "difficulty", "assignment", "tenure")
                   if d in node_frame.columns]
        fair = fair_score(node_frame.assign(performance=result.performance),
                          "performance", drivers)

        rr = RunResult(people, long, raw, scores, n_mat, result, effects, fair,
                       peer_summary, pd.DataFrame(calib), self.model,
                       warnings=warnings)

        # ۸۰ persist
        if persist:
            rr.run_id = self._persist(rr, ref_date)
        return rr

    # ── کمکی ──
    def _people_from(self, long: pd.DataFrame) -> pd.DataFrame:
        keys = sorted(long["person_key"].astype(str).unique()) if not long.empty else []
        return pd.DataFrame({"person_key": keys, "full_name": keys,
                             "management": "", "department": "",
                             "job_family": "", "role": ""})

    def _causal_frame(self, result: ScoreResult, raw: pd.DataFrame,
                      people: pd.DataFrame) -> pd.DataFrame:
        """گره‌های DAG را از خروجی مدل می‌سازد."""
        f = pd.DataFrame(index=result.performance.index)
        for node, cluster in dagmod.NODE_TO_CLUSTER.items():
            if cluster in result.cluster_scores.columns:
                f[node] = result.cluster_scores[cluster]
        if "expected_difficulty" in raw.columns:
            f["difficulty"] = raw["expected_difficulty"]
        # تخصیص کار: کد عددی گروه همتا (نماینده اداره/مدیریت/نوع کار)
        g = people.set_index("person_key").get("peer_group")
        if g is not None:
            f["assignment"] = pd.Categorical(g.reindex(f.index)).codes.astype(float)
        t = people.set_index("person_key").get("tenure_years")
        if t is not None:
            f["tenure"] = pd.to_numeric(t.reindex(f.index), errors="coerce")
        return f

    def _persist(self, rr: RunResult, ref_date: str) -> int:
        dbmod.init(self.db_path)
        run_id = dbmod.start_run(ref_date, self.model.model_version, VERSION,
                                 len(rr.people), path=self.db_path)
        dbmod.write_frame(rr.people, "people", run_id, self.db_path)

        long_rows = []
        for mk in rr.metric_scores.columns:
            long_rows.append(pd.DataFrame({
                "person_key": rr.metric_scores.index,
                "metric_key": mk,
                "raw_value": rr.metric_raw.get(mk),
                "sample_n": rr.sample_n.get(mk),
                "score": rr.metric_scores[mk],
            }))
        if long_rows:
            dbmod.write_frame(pd.concat(long_rows, ignore_index=True),
                              "metric_values", run_id, self.db_path)

        cs = rr.scores.cluster_scores.stack(future_stack=True).rename("score").reset_index()
        cs.columns = ["person_key", "cluster_key", "score"]
        dbmod.write_frame(cs, "cluster_scores", run_id, self.db_path)

        perf = pd.DataFrame({
            "person_key": rr.scores.performance.index,
            "score": rr.scores.performance.values,
            "fair_score": rr.fair["fair"].reindex(rr.scores.performance.index).values
            if "fair" in rr.fair.columns else np.nan,
            "expected": rr.fair["expected"].reindex(rr.scores.performance.index).values
            if "expected" in rr.fair.columns else np.nan,
            "coverage": rr.scores.coverage.values,
            "evidence": rr.scores.evidence.values,
            "confidence": rr.scores.confidence.values,
        })
        dbmod.write_frame(perf, "performance", run_id, self.db_path)

        w = []
        for k, c in self.model.clusters.items():
            w.append({"level": "cluster", "key": k, "cluster_key": k,
                      "weight": c.weight, "effective": c.weight})
        for k, m in self.model.metrics.items():
            w.append({"level": "metric", "key": k, "cluster_key": m.cluster,
                      "weight": m.weight,
                      "effective": self.model.effective_weight(k)})
        dbmod.write_frame(pd.DataFrame(w), "weights", run_id, self.db_path)

        if not rr.effects.empty:
            e = rr.effects.rename(columns={
                "کلید از": "treatment", "کلید به": "outcome",
                "همبستگی خام": "raw", "اثر تعدیل‌شده": "adjusted",
                "تعدیل برای": "adjust_set", "E-value": "e_value"})
            e["misleading"] = (rr.effects["هشدار"].astype(str) != "").astype(int)
            dbmod.write_frame(e, "causal_effects", run_id, self.db_path)

        dbmod.write_audit("warnings", rr.warnings, run_id, self.db_path)
        dbmod.write_audit("calibration",
                          rr.calibration.to_dict(orient="records"),
                          run_id, self.db_path)
        return run_id

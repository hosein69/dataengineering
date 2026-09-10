"""Purged and embargoed cross-validation.

With a 7-hour label horizon and hourly decisions, consecutive observations
share most of their outcome window. Plain k-fold cross-validation then places
observations in the test set whose labels were formed from price paths the
training set has already seen, which leaks the answer and inflates every metric.

Purging removes training observations whose label windows overlap the test set;
the embargo additionally drops a buffer immediately after the test set to
absorb serial correlation the purge alone does not reach.

Lopez de Prado (2018), *Advances in Financial Machine Learning*, ch. 7.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["PurgedKFold", "combinatorial_splits", "sample_uniqueness"]


@dataclass
class PurgedKFold:
    """K-fold splits with label-overlap purging and a post-test embargo.

    Args:
        n_splits: number of folds.
        label_horizon: how many observations forward each label reaches.
        embargo_frac: embargo length as a fraction of the sample.
    """

    n_splits: int = 5
    label_horizon: int = 7
    embargo_frac: float = 0.01

    def split(self, n_samples: int):
        indices = np.arange(n_samples)
        fold_bounds = np.array_split(indices, self.n_splits)
        embargo = int(n_samples * self.embargo_frac)
        for fold in fold_bounds:
            if fold.size == 0:
                continue
            test_start, test_end = int(fold[0]), int(fold[-1])
            # Purge: a training label starting at i reaches i + horizon, so any
            # i whose window touches the test block must go.
            purge_lo = test_start - self.label_horizon
            purge_hi = test_end + self.label_horizon + embargo
            train = indices[(indices < purge_lo) | (indices > purge_hi)]
            yield train, fold


def combinatorial_splits(n_samples: int, n_groups: int = 6, n_test_groups: int = 2, label_horizon: int = 7):
    """Combinatorial purged cross-validation (Lopez de Prado 2018, ch. 12).

    Instead of one train/test path, CPCV produces C(n_groups, n_test_groups)
    paths, which turns a single backtest number into a distribution and makes
    the variance of the estimate visible. That variance is usually the most
    informative statistic in the whole exercise.
    """
    from itertools import combinations

    groups = np.array_split(np.arange(n_samples), n_groups)
    for combo in combinations(range(n_groups), n_test_groups):
        test = np.concatenate([groups[i] for i in combo])
        mask = np.ones(n_samples, dtype=bool)
        for i in combo:
            lo, hi = int(groups[i][0]) - label_horizon, int(groups[i][-1]) + label_horizon
            mask[max(lo, 0) : hi + 1] = False
        yield np.flatnonzero(mask), test


def sample_uniqueness(label_end_index: np.ndarray, n_samples: int) -> np.ndarray:
    """Average uniqueness weight of each observation.

    An observation whose label window is shared with many others contributes
    less independent information and must be down-weighted, otherwise the
    effective sample size is overstated by roughly the label horizon --
    turning 1,000 genuinely independent observations into a claimed 7,000.
    """
    end = np.asarray(label_end_index, dtype=int)
    concurrency = np.zeros(n_samples)
    for i, e in enumerate(end):
        concurrency[i : min(e + 1, n_samples)] += 1.0
    concurrency = np.maximum(concurrency, 1.0)
    weights = np.zeros(end.size)
    for i, e in enumerate(end):
        span = slice(i, min(e + 1, n_samples))
        weights[i] = float(np.mean(1.0 / concurrency[span])) if span.stop > span.start else 1.0
    return weights

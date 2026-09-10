"""Correlation and information-flow graphs.

Two graph constructions are used, both standard in econophysics:

* The minimum spanning tree of the correlation distance
  d_ij = sqrt(2 (1 - rho_ij)), introduced by Mantegna (1999), "Hierarchical
  Structure in Financial Markets", *European Physical Journal B* 11. The MST
  keeps the n-1 strongest links and exposes the market's hierarchy.
* Centrality on that tree. Onnela et al. (2003) and Pozzi, Di Matteo & Aste
  (2013, *Scientific Reports* 3) show that peripheral assets carry more
  idiosyncratic risk and central ones behave as market proxies.

The engine uses centrality for one specific purpose: an asset sitting at the
centre of the correlation graph has almost no idiosyncratic content, so a
"unique" thesis about it is usually a disguised market call. Such signals get
their evidence discounted and their uncertainty raised.
"""
from __future__ import annotations

import math

import numpy as np

from .mathx import EPS

__all__ = ["correlation_distance", "minimum_spanning_tree", "degree_centrality", "eigenvector_centrality", "GraphContext", "build_graph_context"]


def correlation_distance(corr: np.ndarray) -> np.ndarray:
    """Mantegna's metric distance: d = sqrt(2 (1 - rho)), a true metric."""
    c = np.clip(np.asarray(corr, dtype=float), -1.0, 1.0)
    return np.sqrt(np.maximum(2.0 * (1.0 - c), 0.0))


def minimum_spanning_tree(dist: np.ndarray) -> list[tuple[int, int, float]]:
    """Prim's algorithm on a dense distance matrix. O(n^2), no dependencies."""
    d = np.asarray(dist, dtype=float)
    n = d.shape[0]
    if n < 2:
        return []
    in_tree = np.zeros(n, dtype=bool)
    in_tree[0] = True
    best = d[0].copy()
    parent = np.zeros(n, dtype=int)
    edges: list[tuple[int, int, float]] = []
    for _ in range(n - 1):
        best_masked = np.where(in_tree, np.inf, best)
        j = int(np.argmin(best_masked))
        if not np.isfinite(best_masked[j]):
            break
        edges.append((int(parent[j]), j, float(best[j])))
        in_tree[j] = True
        closer = d[j] < best
        parent[closer] = j
        best = np.where(closer, d[j], best)
    return edges


def degree_centrality(edges: list[tuple[int, int, float]], n: int) -> np.ndarray:
    deg = np.zeros(n)
    for a, b, _ in edges:
        deg[a] += 1
        deg[b] += 1
    return deg / max(n - 1, 1)


def eigenvector_centrality(adjacency: np.ndarray, iters: int = 200) -> np.ndarray:
    """Perron eigenvector by power iteration, normalized to max 1."""
    a = np.abs(np.asarray(adjacency, dtype=float))
    n = a.shape[0]
    if n == 0:
        return np.zeros(0)
    v = np.ones(n) / math.sqrt(n)
    for _ in range(iters):
        w = a @ v
        norm = np.linalg.norm(w)
        if norm <= EPS:
            return np.zeros(n)
        w = w / norm
        if np.allclose(w, v, atol=1e-12):
            break
        v = w
    v = np.abs(v)
    return v / max(v.max(), EPS)


class GraphContext:
    """Cross-sectional structure available to the engine at decision time."""

    def __init__(self, symbols: list[str], centrality: np.ndarray, effective_rank: float, signal_share: float):
        self.symbols = symbols
        self.centrality = centrality
        self.effective_rank = effective_rank
        self.signal_share = signal_share
        self._index = {s: i for i, s in enumerate(symbols)}

    def centrality_of(self, symbol: str) -> float:
        i = self._index.get(symbol)
        return float(self.centrality[i]) if i is not None else 0.5

    def uniqueness_of(self, symbol: str) -> float:
        """1 at the periphery of the correlation graph, 0 at its centre."""
        return float(np.clip(1.0 - self.centrality_of(symbol), 0.0, 1.0))


def build_graph_context(returns_by_symbol: dict[str, np.ndarray]) -> GraphContext:
    """Estimate, denoise and characterise the cross-sectional correlation graph."""
    from .linalg import effective_rank as _eff_rank
    from .linalg import ledoit_wolf_shrinkage, marchenko_pastur_denoise

    symbols = [s for s, v in returns_by_symbol.items() if np.asarray(v).size >= 16]
    if len(symbols) < 3:
        return GraphContext(symbols, np.full(len(symbols), 0.5), float(len(symbols)), 1.0)

    length = min(np.asarray(returns_by_symbol[s]).size for s in symbols)
    x = np.column_stack([np.asarray(returns_by_symbol[s], dtype=float)[-length:] for s in symbols])

    cov, _ = ledoit_wolf_shrinkage(x)
    d = np.sqrt(np.maximum(np.diag(cov), EPS))
    corr = np.clip(cov / np.outer(d, d), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    corr, signal_share = marchenko_pastur_denoise(corr, length)

    dist = correlation_distance(corr)
    edges = minimum_spanning_tree(dist)
    adj = np.zeros_like(corr)
    for a, b, _ in edges:
        adj[a, b] = adj[b, a] = abs(corr[a, b])
    cent = eigenvector_centrality(adj)
    return GraphContext(symbols, cent, _eff_rank(corr), signal_share)

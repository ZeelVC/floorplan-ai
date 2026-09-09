"""Deterministic depth/SfM helpers; dense arrays remain on disk artifacts."""
from __future__ import annotations
import numpy as np

def robust_scale(sparse_depth: np.ndarray, metric_depth: np.ndarray) -> tuple[float, float]:
    mask = np.isfinite(sparse_depth) & np.isfinite(metric_depth) & (sparse_depth > 0) & (metric_depth > 0)
    if mask.sum() < 3: raise ValueError("insufficient common depth evidence for scale")
    ratios = metric_depth[mask] / sparse_depth[mask]
    scale = float(np.median(ratios)); residual = float(np.median(np.abs(ratios - scale)))
    return scale, residual

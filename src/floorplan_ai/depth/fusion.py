"""Metric depth fusion and geometrically valid scale estimation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class RobustScaleResult:
    """Scale computed from corresponding sparse and metric camera depths."""

    scale: float
    residual: float
    uncertainty: float
    confidence: float
    sample_count: int


def unproject_depth(
    depth_map: np.ndarray,
    intrinsic_matrix: np.ndarray,
    confidence_mask: np.ndarray | None = None,
    *,
    stride: int = 1,
    maximum_points: int | None = None,
) -> np.ndarray:
    """Unproject valid depth samples into the camera coordinate frame.

    Sampling is a deterministic image grid; it never randomly subsamples evidence.
    """
    depth = np.asarray(depth_map, dtype=float)
    intrinsics = np.asarray(intrinsic_matrix, dtype=float)
    if depth.ndim != 2:
        raise ValueError("depth_map must be a two-dimensional array")
    if intrinsics.shape != (3, 3) or intrinsics[0, 0] <= 0 or intrinsics[1, 1] <= 0:
        raise ValueError("intrinsic_matrix must be a valid 3x3 camera matrix")
    if stride < 1:
        raise ValueError("stride must be positive")
    if confidence_mask is not None and np.asarray(confidence_mask).shape != depth.shape:
        raise ValueError("confidence_mask dimensions must match depth_map")

    rows = np.arange(0, depth.shape[0], stride)
    cols = np.arange(0, depth.shape[1], stride)
    vv, uu = np.meshgrid(rows, cols, indexing="ij")
    z = depth[vv, uu]
    valid = np.isfinite(z) & (z > 0)
    if confidence_mask is not None:
        valid &= np.asarray(confidence_mask)[vv, uu] > 0
    u, v, z = uu[valid], vv[valid], z[valid]
    if maximum_points is not None and maximum_points > 0 and z.size > maximum_points:
        step = int(np.ceil(z.size / maximum_points))
        u, v, z = u[::step], v[::step], z[::step]
    x = (u - intrinsics[0, 2]) * z / intrinsics[0, 0]
    y = (v - intrinsics[1, 2]) * z / intrinsics[1, 1]
    return np.column_stack((x, y, z))


def transform_points(points: np.ndarray, camera_to_frame: Iterable[Iterable[float]]) -> np.ndarray:
    """Transform camera-frame points with the canonical camera-to-frame pose."""
    xyz = np.asarray(points, dtype=float)
    matrix = np.asarray(tuple(tuple(row) for row in camera_to_frame), dtype=float)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or matrix.shape != (4, 4):
        raise ValueError("expected Nx3 points and a 4x4 camera_to_frame transform")
    return (matrix @ np.column_stack((xyz, np.ones(len(xyz)))).T).T[:, :3]


def robust_scale_estimate(sparse_depth: np.ndarray, metric_depth: np.ndarray) -> RobustScaleResult:
    """Estimate SfM-to-metric scale from depths at the *same image coordinates*."""
    sparse = np.asarray(sparse_depth, dtype=float).reshape(-1)
    metric = np.asarray(metric_depth, dtype=float).reshape(-1)
    if sparse.shape != metric.shape:
        raise ValueError("sparse_depth and metric_depth must contain matched observations")
    valid = np.isfinite(sparse) & np.isfinite(metric) & (sparse > 0) & (metric > 0)
    ratios = metric[valid] / sparse[valid]
    if ratios.size < 3:
        raise ValueError("insufficient common depth evidence for scale")
    median = float(np.median(ratios))
    mad = float(np.median(np.abs(ratios - median)))
    sigma = max(1.4826 * mad, 1e-9)
    inliers = np.abs(ratios - median) <= 3.5 * sigma
    if int(inliers.sum()) < 3:
        raise ValueError("insufficient inlier depth evidence for scale")
    values = ratios[inliers]
    scale = float(np.median(values))
    residual = float(np.median(np.abs(values - scale)))
    uncertainty = float(1.4826 * residual / np.sqrt(values.size))
    confidence = float(np.clip((values.size / ratios.size) * np.exp(-residual / max(scale, 1e-9)), 0.0, 1.0))
    return RobustScaleResult(scale, residual, uncertainty, confidence, int(values.size))


def robust_scale(sparse_depth: np.ndarray, metric_depth: np.ndarray) -> tuple[float, float]:
    """Backward-compatible pair of robust scale and median residual."""
    result = robust_scale_estimate(sparse_depth, metric_depth)
    return result.scale, result.residual

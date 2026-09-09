"""Plane observations extracted with Open3D's RANSAC implementation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaneConfig:
    distance_threshold: float = .05
    min_inliers: int = 30
    max_planes: int = 8
    horizontal_z_threshold: float = .85
    vertical_z_threshold: float = .20


@dataclass(frozen=True)
class ExtractedPlane:
    normal: tuple[float, float, float]
    offset: float
    boundary: tuple[tuple[float, float, float], ...]
    inlier_count: int
    inlier_ratio: float
    rmse: float
    orientation: str
    confidence: float


@dataclass(frozen=True)
class PlaneExtractionResult:
    planes: tuple[ExtractedPlane, ...]
    floor_index: int | None
    ceiling_index: int | None


def extract_planes(points, config: PlaneConfig = PlaneConfig()) -> PlaneExtractionResult:
    """Iteratively remove dominant planes using ``PointCloud.segment_plane``.

    Open3D is intentionally required here: there is no alternate NumPy RANSAC
    path, so reported M6 planes always have the same segmentation provenance.
    """
    import numpy as np
    try:
        import open3d as o3d
    except ImportError as exc:  # let callers produce a degraded, honest artifact
        raise RuntimeError("Open3D is required for plane segmentation") from exc

    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3 or len(arr) < config.min_inliers:
        return PlaneExtractionResult((), None, None)
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(arr)
    found: list[ExtractedPlane] = []
    total = len(arr)
    while len(found) < config.max_planes and len(cloud.points) >= config.min_inliers:
        coefficients, inliers = cloud.segment_plane(
            distance_threshold=config.distance_threshold,
            ransac_n=3,
            num_iterations=1000,
        )
        if len(inliers) < config.min_inliers:
            break
        normal = np.asarray(coefficients[:3], dtype=float)
        normal /= np.linalg.norm(normal)
        offset = float(coefficients[3])
        if normal[2] < 0:
            normal, offset = -normal, -offset
        inlier_points = np.asarray(cloud.select_by_index(inliers).points)
        residuals = np.abs(inlier_points @ normal + offset)
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        z_component = abs(normal[2])
        orientation = ("HORIZONTAL" if z_component >= config.horizontal_z_threshold else
                       "VERTICAL" if z_component <= config.vertical_z_threshold else "OTHER")
        ratio = len(inliers) / total
        confidence = float(max(0.0, min(1.0, ratio * (1 - rmse / config.distance_threshold))))
        bounds = (inlier_points.min(axis=0), inlier_points.max(axis=0))
        found.append(ExtractedPlane(tuple(map(float, normal)), offset,
                                   tuple(tuple(map(float, p)) for p in bounds), len(inliers),
                                   ratio, rmse, orientation, confidence))
        cloud = cloud.select_by_index(inliers, invert=True)

    horizontal = [i for i, plane in enumerate(found) if plane.orientation == "HORIZONTAL"]
    # With upward-facing normals, d=-z for z=constant: largest d is the floor.
    floor = max(horizontal, key=lambda i: found[i].offset) if horizontal else None
    ceiling = None
    if floor is not None:
        above = [i for i in horizontal if found[i].offset < found[floor].offset - config.distance_threshold]
        if above:
            ceiling = max(above, key=lambda i: found[i].inlier_count)
    return PlaneExtractionResult(tuple(found), floor, ceiling)

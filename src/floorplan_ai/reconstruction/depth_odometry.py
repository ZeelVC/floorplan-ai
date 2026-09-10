"""Depth-assisted visual odometry fallback for difficult photo captures.

This path is intentionally independent of COLMAP initialization. It uses a metric
per-image depth prediction plus 2D feature correspondences to estimate relative
camera motion with PnP, then emits the same backend-neutral reconstruction record.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np

from floorplan_ai.depth import MetricDepthEstimator, unproject_depth
from .models import (
    ReconstructionCamera,
    ReconstructionImage,
    ReconstructionPose,
    ReconstructionResult,
    ScaleState,
)


def _rotation_to_quaternion(rotation: np.ndarray) -> tuple[float, float, float, float]:
    r = np.asarray(rotation, dtype=float)
    trace = float(np.trace(r))
    if trace > 0.0:
        s = 2.0 * np.sqrt(trace + 1.0)
        q = np.array([
            0.25 * s,
            (r[2, 1] - r[1, 2]) / s,
            (r[0, 2] - r[2, 0]) / s,
            (r[1, 0] - r[0, 1]) / s,
        ])
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = 2.0 * np.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2])
        q = np.array([
            (r[2, 1] - r[1, 2]) / s,
            0.25 * s,
            (r[0, 1] + r[1, 0]) / s,
            (r[0, 2] + r[2, 0]) / s,
        ])
    elif r[1, 1] > r[2, 2]:
        s = 2.0 * np.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2])
        q = np.array([
            (r[0, 2] - r[2, 0]) / s,
            (r[0, 1] + r[1, 0]) / s,
            0.25 * s,
            (r[1, 2] + r[2, 1]) / s,
        ])
    else:
        s = 2.0 * np.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1])
        q = np.array([
            (r[1, 0] - r[0, 1]) / s,
            (r[0, 2] + r[2, 0]) / s,
            (r[1, 2] + r[2, 1]) / s,
            0.25 * s,
        ])
    q /= np.linalg.norm(q)
    if q[0] < 0:
        q *= -1.0
    return tuple(float(x) for x in q)


def _world_to_camera_pose(camera_to_world: np.ndarray) -> tuple[tuple[float, float, float, float], tuple[float, float, float]]:
    world_to_camera = np.linalg.inv(camera_to_world)
    return _rotation_to_quaternion(world_to_camera[:3, :3]), tuple(float(x) for x in world_to_camera[:3, 3])


def _load_depth(estimator: MetricDepthEstimator, image: Path, focal: float, cache: Path | None):
    stem = image.stem
    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        depth_path = cache / f"{stem}.depth.npy"
        conf_path = cache / f"{stem}.confidence.npy"
        if depth_path.is_file() and conf_path.is_file():
            return np.load(depth_path), np.load(conf_path)
    prediction = estimator.predict(image, focal_length_px=focal)
    depth = np.asarray(prediction.depth_map, dtype=np.float32)
    confidence = np.asarray(prediction.confidence_map, dtype=np.float32)
    if depth.ndim != 2 or confidence.shape != depth.shape or depth.size == 0:
        raise RuntimeError(f"depth_odometry: invalid metric depth for {image.name}")
    if cache is not None:
        np.save(cache / f"{stem}.depth.npy", depth)
        np.save(cache / f"{stem}.confidence.npy", confidence)
    return depth, confidence


def reconstruct_with_depth_odometry(
    inputs: Sequence[Path],
    estimator: MetricDepthEstimator,
    output_dir: Path,
    *,
    focal_length_px: float,
    min_confidence: float = 0.2,
    ratio_test: float = 0.75,
    pnp_reprojection_error_px: float = 5.0,
    minimum_pnp_inliers: int = 12,
) -> ReconstructionResult:
    """Build a metric photo trajectory using depth-assisted consecutive PnP."""
    if not inputs:
        return ReconstructionResult(success=False, backend_name="DEPTH_ODOMETRY", failure_reason="No input images supplied")
    try:
        import cv2
    except ImportError as exc:
        return ReconstructionResult(success=False, backend_name="DEPTH_ODOMETRY", failure_reason="OpenCV is required for depth odometry")

    root = output_dir / "depth_odometry"
    cache = root / "depth_cache"
    root.mkdir(parents=True, exist_ok=True)

    images = tuple(Path(p) for p in inputs)
    first = cv2.imread(str(images[0]), cv2.IMREAD_GRAYSCALE)
    if first is None:
        return ReconstructionResult(success=False, backend_name="DEPTH_ODOMETRY", failure_reason=f"Unable to read image: {images[0]}")
    height, width = first.shape[:2]
    f = float(focal_length_px) if focal_length_px > 0 else 1.2 * float(width)
    cx, cy = width / 2.0, height / 2.0
    k = np.array(((f, 0.0, cx), (0.0, f, cy), (0.0, 0.0, 1.0)), dtype=float)
    dist = np.zeros((4, 1), dtype=float)

    sift = cv2.SIFT_create()
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    gray_images = [first]
    keypoints = []
    descriptors = []
    depths = []
    confidences = []

    for image in images:
        gray = first if image == images[0] else cv2.imread(str(image), cv2.IMREAD_GRAYSCALE)
        if gray is None:
            return ReconstructionResult(success=False, backend_name="DEPTH_ODOMETRY", failure_reason=f"Unable to read image: {image}")
        if gray.shape != first.shape:
            gray = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)
        kp, des = sift.detectAndCompute(gray, None)
        depth, confidence = _load_depth(estimator, image, f, cache)
        if depth.shape != (height, width):
            depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_NEAREST)
            confidence = cv2.resize(confidence, (width, height), interpolation=cv2.INTER_NEAREST)
        gray_images.append(gray) if image != images[0] else None
        keypoints.append(kp or [])
        descriptors.append(des)
        depths.append(depth)
        confidences.append(confidence)

    poses_world = [np.eye(4, dtype=float)]
    edge_inliers: list[int] = []
    successful_edges = 0

    for index in range(1, len(images)):
        des_prev, des_cur = descriptors[index - 1], descriptors[index]
        if des_prev is None or des_cur is None or len(des_prev) < 8 or len(des_cur) < 8:
            poses_world.append(poses_world[-1].copy())
            edge_inliers.append(0)
            continue
        pairs = matcher.knnMatch(des_prev, des_cur, k=2)
        good = [m for m, n in pairs if m.distance < ratio_test * n.distance]
        object_points = []
        image_points = []
        depth_prev = depths[index - 1]
        confidence_prev = confidences[index - 1]
        for match in good:
            u, v = keypoints[index - 1][match.queryIdx].pt
            ui, vi = int(round(u)), int(round(v))
            if not (0 <= ui < width and 0 <= vi < height):
                continue
            z = float(depth_prev[vi, ui])
            conf = float(confidence_prev[vi, ui])
            if not np.isfinite(z) or z <= 0 or conf < min_confidence:
                continue
            x = (u - cx) * z / f
            y = (v - cy) * z / f
            object_points.append((x, y, z))
            image_points.append(keypoints[index][match.trainIdx].pt)
        if len(object_points) < max(6, minimum_pnp_inliers):
            poses_world.append(poses_world[-1].copy())
            edge_inliers.append(0)
            continue
        obj = np.asarray(object_points, dtype=np.float32)
        img = np.asarray(image_points, dtype=np.float32)
        ok, rvec, tvec, inliers = cv2.solvePnPRansac(
            obj,
            img,
            k,
            dist,
            iterationsCount=300,
            reprojectionError=float(pnp_reprojection_error_px),
            confidence=0.999,
            flags=cv2.SOLVEPNP_EPNP,
        )
        count = int(len(inliers)) if inliers is not None else 0
        if not ok or count < minimum_pnp_inliers:
            poses_world.append(poses_world[-1].copy())
            edge_inliers.append(count)
            continue
        rotation, _ = cv2.Rodrigues(rvec)
        current_from_previous = np.eye(4, dtype=float)
        current_from_previous[:3, :3] = rotation
        current_from_previous[:3, 3] = np.asarray(tvec, dtype=float).reshape(3)
        poses_world.append(poses_world[-1] @ np.linalg.inv(current_from_previous))
        edge_inliers.append(count)
        successful_edges += 1

    cameras = (ReconstructionCamera(camera_id=1, model="SIMPLE_RADIAL", width=width, height=height, params=(f, cx, cy, 0.0)),)
    poses = []
    output_images = []
    for idx, (image, pose_world) in enumerate(zip(images, poses_world), start=1):
        qvec, tvec = _world_to_camera_pose(pose_world)
        poses.append(ReconstructionPose(image_id=idx, image_name=image.name, camera_id=1, qvec=qvec, tvec=tvec))
        output_images.append(ReconstructionImage(image_id=idx, name=image.name, camera_id=1))

    diagnostics = {
        "depth_odometry": True,
        "depth_cache_dir": str(cache),
        "depth_focal_length_px": f,
        "localized_image_count": len(poses),
        "odometry_edge_count": max(0, len(images) - 1),
        "odometry_successful_edge_count": successful_edges,
        "odometry_inlier_counts": edge_inliers,
        "metric_scale_source": "metric_depth_model",
        "pose_convention": "colmap_world_to_camera",
    }
    return ReconstructionResult(
        success=True,
        backend_name="DEPTH_ODOMETRY",
        camera_models=cameras,
        poses=tuple(poses),
        images=tuple(output_images),
        points=(),
        diagnostics=diagnostics,
        scale_state=ScaleState.METRIC,
    )

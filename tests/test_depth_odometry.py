from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from floorplan_ai.depth.base import MetricDepthResult
from floorplan_ai.reconstruction.depth_odometry import reconstruct_with_depth_odometry


class FakeDepthEstimator:
    def predict(self, image_path: Path, focal_length_px: float | None = None) -> MetricDepthResult:
        with Image.open(image_path) as image:
            width, height = image.size
        depth = np.ones((height, width), dtype=np.float32) * 2.0
        confidence = np.ones_like(depth)
        return MetricDepthResult(
            depth_map=depth,
            focal_length_px=focal_length_px,
            confidence_map=confidence,
            model_name="fake",
            model_version="test",
            provenance={"runtime": "test"},
        )


def test_depth_odometry_single_image_produces_metric_pose_and_cache(tmp_path: Path):
    image = tmp_path / "one.jpeg"
    Image.new("RGB", (64, 48), (128, 128, 128)).save(image)

    result = reconstruct_with_depth_odometry(
        (image,),
        FakeDepthEstimator(),
        tmp_path / "output",
        focal_length_px=76.8,
    )

    assert result.success is True
    assert result.backend_name == "DEPTH_ODOMETRY"
    assert result.scale_state.value == "METRIC"
    assert len(result.camera_models) == 1
    assert len(result.poses) == 1
    assert result.diagnostics["depth_odometry"] is True
    assert (tmp_path / "output" / "depth_odometry" / "depth_cache" / "one.depth.npy").is_file()
    assert (tmp_path / "output" / "depth_odometry" / "depth_cache" / "one.confidence.npy").is_file()

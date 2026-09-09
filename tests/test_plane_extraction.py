"""Synthetic validation for the actual Open3D plane-segmentation backend."""
import importlib.util
import pytest

pytestmark = pytest.mark.skipif(not importlib.util.find_spec("open3d"), reason="Open3D is unavailable in this runtime")


def test_open3d_extracts_floor_ceiling_and_walls():
    import numpy as np
    from floorplan_ai.geometry.planes import PlaneConfig, extract_planes

    rng = np.random.default_rng(7)
    n = 250
    xy = rng.uniform((0, 0), (4, 5), (n, 2))
    xz = rng.uniform((0, 0), (4, 2.8), (n, 2))
    yz = rng.uniform((0, 0), (5, 2.8), (n, 2))
    points = np.vstack((
        np.c_[xy, np.zeros(n)], np.c_[xy, np.full(n, 2.8)],
        np.c_[np.zeros(n), xz], np.c_[yz[:, 0], np.full(n, 4), yz[:, 1]],
    )) + rng.normal(0, .006, (n * 4, 3))
    result = extract_planes(points, PlaneConfig(distance_threshold=.03, min_inliers=100, max_planes=6))

    assert result.floor_index is not None and result.ceiling_index is not None
    assert result.planes[result.floor_index].orientation == "HORIZONTAL"
    assert result.planes[result.ceiling_index].orientation == "HORIZONTAL"
    vertical = [plane for plane in result.planes if plane.orientation == "VERTICAL"]
    assert len(vertical) >= 2
    for plane in result.planes:
        assert plane.inlier_count >= 100
        assert 0 <= plane.confidence <= 1

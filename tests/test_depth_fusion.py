import numpy as np

from floorplan_ai.depth.fusion import robust_scale_estimate, transform_points, unproject_depth


def test_unproject_depth_uses_supplied_intrinsics_and_mask():
    depth = np.array([[1.0, 2.0], [3.0, np.nan]])
    intrinsics = np.array([[2.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 1.0]])
    mask = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    points = unproject_depth(depth, intrinsics, mask)
    np.testing.assert_allclose(points, [[0.0, 0.0, 1.0], [1.0, 0.0, 2.0]])


def test_depth_points_transform_to_canonical_frame():
    transformed = transform_points(np.array([[1.0, 2.0, 3.0]]), ((1, 0, 0, 4), (0, 1, 0, 5), (0, 0, 1, 6), (0, 0, 0, 1)))
    np.testing.assert_allclose(transformed, [[5.0, 7.0, 9.0]])


def test_robust_scale_rejects_outlier_correspondence():
    result = robust_scale_estimate(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), np.array([2.0, 4.0, 6.0, 8.0, 100.0]))
    assert result.scale == 2.0
    assert result.sample_count == 4
    assert result.confidence > 0.7

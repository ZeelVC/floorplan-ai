import numpy as np
import pytest

from floorplan_ai.canonical.schema import Wall
from floorplan_ai.depth.fusion import fuse_metric_clouds, scale_points, scale_pose_translation
from floorplan_ai.inference.openings import infer_openings


def test_scale_points_changes_metric_geometry():
    points = np.array([[1.0, -2.0, 0.5], [3.0, 4.0, 2.0]])
    np.testing.assert_allclose(scale_points(points, 2.0), points * 2.0)


def test_scale_pose_translation_preserves_rotation():
    pose = ((0.0, -1.0, 0.0, 1.0), (1.0, 0.0, 0.0, 2.0), (0.0, 0.0, 1.0, 3.0), (0.0, 0.0, 0.0, 1.0))
    scaled = np.asarray(scale_pose_translation(pose, 2.0))
    np.testing.assert_allclose(scaled[:3, :3], np.asarray(pose)[:3, :3])
    np.testing.assert_allclose(scaled[:3, 3], [2.0, 4.0, 6.0])


def test_fuse_metric_clouds_is_deterministic_and_removes_voxel_duplicates():
    sparse = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    dense = np.array([[0.001, 0.001, 0.001], [2.0, 0.0, 0.0]])
    first = fuse_metric_clouds(sparse, dense, distance_threshold=0.02)
    second = fuse_metric_clouds(sparse, dense, distance_threshold=0.02)
    np.testing.assert_allclose(first, second)
    assert len(first) == 3


def test_zero_length_wall_is_rejected_before_opening_inference():
    with pytest.raises(ValueError, match="wall length must be positive"):
        Wall(
            supporting_plane_id="00000000-0000-0000-0000-000000000001",
            start_point_2d=(0.0, 0.0),
            end_point_2d=(0.0, 0.0),
        )


def test_opening_inference_rejects_invalid_height_range():
    with pytest.raises(ValueError, match="ceiling_height must be above floor_height"):
        infer_openings([], [], floor_height=2.0, ceiling_height=2.0)

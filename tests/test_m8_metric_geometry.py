import json
from pathlib import Path

import numpy as np
import pytest

from floorplan_ai.canonical.schema import Opening, OpeningType, Provenance, Uncertainty, Wall
from floorplan_ai.capture import photo_metadata
from floorplan_ai.dataset.models import CaptureInput
from floorplan_ai.depth.base import MetricDepthResult
from floorplan_ai.depth.fusion import fuse_metric_clouds, scale_points, scale_pose_translation
from floorplan_ai.frontend.photo import PhotoFrontendConfig, reconstruct_photos
from floorplan_ai.inference.openings import infer_openings
from floorplan_ai.inference.structural import StructuralInferenceConfig, infer_structure
from floorplan_ai.measurement.metrics import measurements_for
from floorplan_ai.reconstruction.models import (
    ReconstructionCamera,
    ReconstructionImage,
    ReconstructionPoint,
    ReconstructionPose,
    ReconstructionResult,
)


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


def test_photo_metric_depth_flows_to_structure_and_opening_measurement(tmp_path, monkeypatch):
    """Exercise the real photo frontend boundary through canonical measurement output.

    Reconstruction and metric depth are mocked locally, while canonical construction,
    metric scaling, dense fusion, artifact persistence, structural inference, and
    measurement generation remain real pipeline code.
    """
    from PIL import Image
    from floorplan_ai.frontend import common
    from floorplan_ai.geometry.planes import ExtractedPlane, PlaneExtractionResult
    from floorplan_ai.inference import structural

    image_path = tmp_path / "room.jpg"
    Image.new("RGB", (100, 100), (128, 128, 128)).save(image_path, quality=95)

    # SfM is deliberately unit-scale: the matched depth evidence is 2x the
    # reconstructed camera depth, so the metric scale must be exactly 2.
    sparse_xyz = ((0.0, 0.0, 2.0), (0.2, 0.0, 2.0), (-0.2, 0.1, 2.0))

    def reconstruction(*args, **kwargs):
        return ReconstructionResult(
            success=True,
            backend_name="mock-photo",
            camera_models=(
                ReconstructionCamera(
                    camera_id=1,
                    model="SIMPLE_PINHOLE",
                    width=100,
                    height=100,
                    params=(50.0, 50.0, 50.0),
                ),
            ),
            poses=(
                ReconstructionPose(
                    image_id=1,
                    image_name="room.jpg",
                    camera_id=1,
                    qvec=(1.0, 0.0, 0.0, 0.0),
                    tvec=(0.0, 0.0, 0.0),
                ),
            ),
            images=(ReconstructionImage(image_id=1, name="room.jpg", camera_id=1),),
            points=tuple(
                ReconstructionPoint(point_id=i, xyz=point)
                for i, point in enumerate(sparse_xyz)
            ),
            diagnostics={"correspondences": []},
        )

    class Backend:
        def reconstruct(self, *args, **kwargs):
            return reconstruction(*args, **kwargs)

    class Depth:
        def predict(self, image_path: Path, focal_length_px=None):
            depth = np.full((100, 100), 4.0, dtype=float)
            confidence = np.ones_like(depth)
            return MetricDepthResult(
                depth_map=depth,
                focal_length_px=50.0,
                confidence_map=confidence,
                model_name="mock-depth-pro",
                model_version="test",
                provenance={"runtime": "offline-test"},
            )

    # Keep the frontend's plane-extraction boundary but make the structural
    # geometry deterministic for a synthetic fixture.
    rectangle = ((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0))
    planes = (
        ExtractedPlane((0.0, 0.0, 1.0), 0.0, rectangle, 100, 1.0, 0.0, "HORIZONTAL", 1.0),
        ExtractedPlane((0.0, 0.0, 1.0), -3.0, tuple((x, y, 3.0) for x, y, _ in rectangle), 100, 1.0, 0.0, "HORIZONTAL", 1.0),
        ExtractedPlane((0.0, 1.0, 0.0), 2.0, ((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0), (2.0, -2.0, 3.0), (-2.0, -2.0, 3.0)), 100, 1.0, 0.0, "VERTICAL", 1.0),
        ExtractedPlane((0.0, 1.0, 0.0), -2.0, ((-2.0, 2.0, 0.0), (2.0, 2.0, 0.0), (2.0, 2.0, 3.0), (-2.0, 2.0, 3.0)), 100, 1.0, 0.0, "VERTICAL", 1.0),
        ExtractedPlane((1.0, 0.0, 0.0), 2.0, ((-2.0, -2.0, 0.0), (-2.0, 2.0, 0.0), (-2.0, 2.0, 3.0), (-2.0, -2.0, 3.0)), 100, 1.0, 0.0, "VERTICAL", 1.0),
        ExtractedPlane((1.0, 0.0, 0.0), -2.0, ((2.0, -2.0, 0.0), (2.0, 2.0, 0.0), (2.0, 2.0, 3.0), (2.0, -2.0, 3.0)), 100, 1.0, 0.0, "VERTICAL", 1.0),
    )

    monkeypatch.setattr(common, "extract_planes", lambda *args, **kwargs: PlaneExtractionResult(planes, 0, 1))
    monkeypatch.setattr(structural, "extract_planes", lambda *args, **kwargs: PlaneExtractionResult(planes, 0, 1))

    metric_capture = CaptureInput(
        capture_id="room",
        source_type="photo",
        file=image_path.name,
        resolved_file=image_path,
        metadata={"focal_length": 4.0},
    )
    model = reconstruct_photos(
        (metric_capture,),
        tmp_path / "result",
        PhotoFrontendConfig(
            reconstruction=Backend(),
            metric_depth=common.MetricDepthConfig(estimator=Depth(), depth_stride=10, maximum_depth_points=500),
        ),
    )

    assert model.scale_estimates[-1].scale_factor == pytest.approx(2.0)
    assert model.scale_estimates[-1].confidence > 0.99
    assert model.poses[0].camera_to_frame[2][3] == pytest.approx(0.0)
    assert model.geometries[0].vertex_buffer_reference == "depth/metric_fused_points.xyz"
    assert Path(tmp_path / "result" / model.geometries[0].vertex_buffer_reference).is_file()
    fused = np.loadtxt(tmp_path / "result" / model.geometries[0].vertex_buffer_reference)
    assert np.max(np.abs(fused), axis=0).max() >= 4.0

    seen_cloud = {}

    def fake_openings(points, walls, *, floor_height, ceiling_height, config=None):
        cloud = np.asarray(tuple(points), dtype=float)
        seen_cloud["points"] = cloud
        wall = next(wall for wall in walls if wall.start_point_2d[1] == pytest.approx(-2.0))
        return (
            Opening(
                parent_wall_id=wall.wall_id,
                opening_type=OpeningType.DOOR,
                offset_along_wall=1.0,
                width=0.9,
                height=2.1,
                sill_height=0.0,
                connected_room_ids=wall.room_ids,
                uncertainty=Uncertainty(distribution_type="synthetic", confidence_bounds=(0.0, 0.01)),
                provenance=Provenance(generating_pipeline_stage="opening_inference"),
            ),
        )

    monkeypatch.setattr(structural, "infer_openings", fake_openings)
    structured = infer_structure(
        model,
        StructuralInferenceConfig(artifact_root=tmp_path / "result"),
    )
    assert structured.walls
    assert structured.rooms
    assert structured.openings and structured.openings[0].width == pytest.approx(0.9)
    np.testing.assert_allclose(np.sort(seen_cloud["points"], axis=0), np.sort(fused, axis=0))

    measurements = measurements_for(structured)
    opening_measurements = [
        item for item in measurements
        if item.metric_type == "OPENING_WIDTH" and item.target_entity_id == structured.openings[0].opening_id
    ]
    assert len(opening_measurements) == 1
    assert opening_measurements[0].nominal_value == pytest.approx(0.9)
    assert json.loads((tmp_path / "result" / "canonical.json").read_text())["scale_estimates"][-1]["scale_factor"] == pytest.approx(2.0)

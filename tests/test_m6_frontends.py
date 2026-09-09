import importlib.util
import json
from pathlib import Path
import pytest
from floorplan_ai.dataset.models import CaptureInput
from floorplan_ai.frontend.photo import PhotoFrontendConfig, reconstruct_photos
from floorplan_ai.reconstruction.models import (ReconstructionCamera, ReconstructionImage,
    ReconstructionPoint, ReconstructionPose, ReconstructionResult)


def result():
    return ReconstructionResult(success=True, backend_name="mock", camera_models=(
        ReconstructionCamera(camera_id=1, model="SIMPLE_PINHOLE", width=800, height=600, params=(700., 400., 300.)),),
        poses=(ReconstructionPose(image_id=1, image_name="one.jpg", camera_id=1, qvec=(1., 0., 0., 0.), tvec=(0., 0., 0.)),),
        images=(ReconstructionImage(image_id=1, name="one.jpg", camera_id=1),),
        points=tuple(ReconstructionPoint(point_id=i, xyz=(float(i), 0., 0.)) for i in range(3)),
        diagnostics={"correspondences": []})

class Backend:
    def reconstruct(self, *args, **kwargs): return result()


def test_mocked_photo_writes_complete_canonical(tmp_path, monkeypatch):
    from floorplan_ai.frontend import common
    from floorplan_ai.geometry.planes import ExtractedPlane, PlaneExtractionResult
    monkeypatch.setattr(common, "extract_planes", lambda *args: PlaneExtractionResult(
        (ExtractedPlane((0., 0., 1.), 0., (), 3, 1., 0., "HORIZONTAL", 1.),), 0, None))
    model = reconstruct_photos((CaptureInput(capture_id="one", source_type="photo", file="one.jpg", metadata={"focal_length": 4.0}),), tmp_path, PhotoFrontendConfig(reconstruction=Backend()))
    assert model.captures and model.cameras and model.poses and model.observations
    assert model.geometries and model.planes and model.scale_estimates and model.provenance
    assert model.cameras[0].prior_source == "EXIF+reconstruction"
    from floorplan_ai.canonical.schema import CanonicalWorldModel
    assert CanonicalWorldModel.model_validate_json((tmp_path / "canonical.json").read_text())
    assert json.loads((tmp_path / "diagnostics.json").read_text())["point_count"] == 3


@pytest.mark.skipif(not importlib.util.find_spec("cv2"), reason="OpenCV is unavailable in this runtime")
def test_mocked_video_preserves_frame_trajectory(tmp_path):
    import cv2
    import numpy as np
    from floorplan_ai.frontend.video import VideoFrontendConfig, reconstruct_video
    path = tmp_path / "tiny.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 4, (640, 480))
    for i in range(4): writer.write(np.full((480, 640, 3), i * 50, dtype=np.uint8))
    writer.release()
    class VideoBackend:
        def reconstruct(self, paths, *args, **kwargs):
            base = result()
            names = tuple(Path(p).name for p in paths)
            return base.model_copy(update={"poses": tuple(ReconstructionPose(image_id=i + 1, image_name=n, camera_id=1, qvec=(1.,0.,0.,0.), tvec=(0.,0.,0.)) for i,n in enumerate(names)), "images": tuple(ReconstructionImage(image_id=i + 1, name=n, camera_id=1) for i,n in enumerate(names))})
    model = reconstruct_video(CaptureInput(capture_id="video", source_type="video", file=path.name, resolved_file=path), tmp_path / "out", VideoFrontendConfig(reconstruction=VideoBackend(), frame_sampling={"target_fps": 2, "max_frames": 4}))
    entries = json.loads((tmp_path / "out" / "reconstruction" / "trajectory.json").read_text())
    assert model.captures and entries and all({"frame_id", "timestamp_seconds", "source_capture_id", "image_path", "pose_id"} <= entry.keys() for entry in entries)
    diagnostics = json.loads((tmp_path / "out" / "diagnostics.json").read_text())
    assert diagnostics["frames_decoded"] >= diagnostics["frames_selected"] and diagnostics["trajectory_pose_count"] == len(model.poses)

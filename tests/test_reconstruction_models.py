from floorplan_ai.reconstruction.models import ReconstructionResult, ScaleState
def test_failure_result_is_explicit():
 result=ReconstructionResult(success=False,backend_name='COLMAP',failure_reason='unavailable')
 assert result.scale_state is ScaleState.UNKNOWN and not result.points
import pytest
from floorplan_ai.reconstruction.colmap import ColmapBackend, colmap_pose_to_canonical
from floorplan_ai.reconstruction.models import ReconstructionCamera, ReconstructionPose

def test_colmap_missing_is_explicitly_degraded(tmp_path):
    result = ColmapBackend(executable='definitely-not-colmap').reconstruct((), tmp_path)
    assert not result.success and result.failure_reason and result.scale_state is ScaleState.UNKNOWN

def test_invalid_quaternion_is_rejected():
    with pytest.raises(ValueError, match='non-zero'):
        colmap_pose_to_canonical((0, 0, 0, 0), (0, 0, 0))

def test_valid_quaternion_is_normalized():
    assert colmap_pose_to_canonical((2, 0, 0, 0), (0, 0, 0))[0][0] == 1

def test_malformed_reconstruction_record_is_rejected():
    with pytest.raises(Exception):
        ReconstructionPose(image_id=1, image_name='bad.jpg', camera_id=1, qvec=(1, 0, 0), tvec=(0, 0, 0))

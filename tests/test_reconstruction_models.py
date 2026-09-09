from floorplan_ai.reconstruction.models import ReconstructionResult, ScaleState
def test_failure_result_is_explicit():
 result=ReconstructionResult(success=False,backend_name='COLMAP',failure_reason='unavailable')
 assert result.scale_state is ScaleState.UNKNOWN and not result.points

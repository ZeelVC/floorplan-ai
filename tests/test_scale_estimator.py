from floorplan_ai.reconstruction import ScaleEstimator
from floorplan_ai.reconstruction.models import ScaleState
def test_unscaled_result_does_not_claim_metric():
 estimate=ScaleEstimator().estimate()
 assert estimate.scale_factor == 1 and estimate.state is ScaleState.UNKNOWN and estimate.confidence < .5

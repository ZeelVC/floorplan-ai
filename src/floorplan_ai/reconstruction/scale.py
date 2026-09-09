"""Conservative scale estimation; never consumes evaluation data."""
from dataclasses import dataclass
from .models import ScaleState
@dataclass(frozen=True)
class ScaleResult: scale_factor:float; confidence:float; state:ScaleState; evidence:tuple[str,...]
class ScaleEstimator:
    def estimate(self, *, validated_camera_metadata: bool=False, geometric_consistency: bool=False, architectural_prior: bool=False)->ScaleResult:
        evidence=tuple(x for x,b in (("camera_metadata",validated_camera_metadata),("geometric_consistency",geometric_consistency),("architectural_prior",architectural_prior)) if b)
        if not evidence: return ScaleResult(1.0,.1,ScaleState.UNKNOWN,())
        return ScaleResult(1.0,.35,ScaleState.ESTIMATED,evidence)

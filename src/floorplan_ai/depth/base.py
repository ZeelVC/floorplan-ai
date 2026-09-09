"""Local-only metric depth interface and artifact metadata."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import numpy as np

@dataclass(frozen=True)
class MetricDepthResult:
    depth_map: np.ndarray
    focal_length_px: float | None
    confidence_map: np.ndarray
    model_name: str
    model_version: str
    provenance: dict[str, str]

class MetricDepthEstimator(Protocol):
    def predict(self, image_path: Path, focal_length_px: float | None = None) -> MetricDepthResult: ...

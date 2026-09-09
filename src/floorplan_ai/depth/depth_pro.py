"""Adapter for an explicitly installed, local Apple Depth Pro runtime.

No package import or checkpoint acquisition happens until ``predict``.  This keeps
normal reconstruction offline and makes the optional dependency failure explicit.
"""
from __future__ import annotations
from pathlib import Path
import importlib
import numpy as np
from .base import MetricDepthResult

class DepthProEstimator:
    def __init__(self, model_path: Path, device: str = "auto"):
        self.model_path, self.device = Path(model_path), device
        if not self.model_path.exists():
            raise FileNotFoundError("Depth Pro model not found. Run: floorplan-ai fetch-models")
        self._model = None
        self._transform = None
        self._module = None

    def _load(self) -> None:
        """Load the local model once, then reuse it for every accepted keyframe."""
        if self._model is not None:
            return
        try:
            module = importlib.import_module("depth_pro")
        except ImportError as exc:
            raise RuntimeError("Depth Pro local runtime is unavailable; install it during setup.") from exc
        model, transform = module.create_model_and_transforms(device=self.device, precision=None)
        model.load_state_dict(module.load_checkpoint(str(self.model_path)), strict=True)
        self._module, self._model, self._transform = module, model, transform

    def predict(self, image_path: Path, focal_length_px: float | None = None) -> MetricDepthResult:
        self._load()
        prediction = self._model.infer(self._transform(str(image_path)), f_px=focal_length_px)
        depth = np.asarray(prediction["depth"], dtype=np.float32)
        focal = float(prediction.get("focal_length_px", focal_length_px)) if prediction.get("focal_length_px", focal_length_px) else None
        confidence = confidence_from_depth(depth)
        return MetricDepthResult(depth, focal, confidence, "Apple Depth Pro", "local", {"checkpoint": str(self.model_path), "runtime": "local_only"})

def confidence_from_depth(depth: np.ndarray) -> np.ndarray:
    valid = np.isfinite(depth) & (depth > 0)
    if not valid.any(): return np.zeros(depth.shape, dtype=np.float32)
    low, high = np.percentile(depth[valid], (1, 99))
    edge = np.zeros_like(depth, dtype=float)
    edge[1:-1, 1:-1] = np.hypot(np.diff(depth, axis=0, prepend=depth[:1]), np.diff(depth, axis=1, prepend=depth[:, :1]))[1:-1,1:-1]
    scale = np.nanpercentile(edge[valid], 95) or 1.0
    return (valid * np.clip(1 - edge / scale, 0.0, 1.0) * ((depth >= low) & (depth <= high))).astype(np.float32)

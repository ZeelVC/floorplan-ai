"""Adapter for an explicitly installed, local Apple Depth Pro runtime.

No package import or checkpoint acquisition happens until ``predict``.  This keeps
normal reconstruction offline and makes the optional dependency failure explicit.
"""
from __future__ import annotations
from dataclasses import replace
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
        self._resolved_device = None

    def _resolve_device(self) -> str:
        """Resolve the user-friendly ``auto`` setting to a real torch device string."""
        if self.device != "auto":
            return self.device
        try:
            torch = importlib.import_module("torch")
        except ImportError:
            return "cpu"
        if bool(getattr(torch.cuda, "is_available", lambda: False)()):
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and bool(getattr(mps, "is_available", lambda: False)()):
            return "mps"
        return "cpu"

    def _load(self) -> None:
        """Load Apple's model directly from the explicitly configured local checkpoint."""
        if self._model is not None:
            return
        try:
            module = importlib.import_module("depth_pro")
            torch = importlib.import_module("torch")
        except ImportError as exc:
            raise RuntimeError("Depth Pro local runtime is unavailable; install it during setup.") from exc
        self._resolved_device = self._resolve_device()
        device = torch.device(self._resolved_device)
        try:
            depth_pro_module = importlib.import_module("depth_pro.depth_pro")
            default_config = depth_pro_module.DEFAULT_MONODEPTH_CONFIG_DICT
            config = replace(default_config, checkpoint_uri=str(self.model_path))
            model, transform = module.create_model_and_transforms(
                config=config,
                device=device,
                precision=torch.float32,
            )
        except (AttributeError, TypeError):
            model, transform = module.create_model_and_transforms(
                device=device,
                precision=torch.float32,
            )
            loader = getattr(module, "load_checkpoint", None)
            if loader is None:
                raise RuntimeError("Depth Pro runtime does not expose a supported local checkpoint loader.")
            state_dict = loader(str(self.model_path))
            model.load_state_dict(state_dict, strict=True)
        model.eval()
        self._module, self._model, self._transform = module, model, transform

    def predict(self, image_path: Path, focal_length_px: float | None = None) -> MetricDepthResult:
        self._load()
        image, _, exif_focal = self._module.load_rgb(image_path)
        transformed = self._transform(image)
        torch = importlib.import_module("torch")
        if isinstance(transformed, np.ndarray):
            transformed = torch.from_numpy(transformed)
        transformed = transformed.to(torch.device(self._resolved_device))
        supplied_focal = focal_length_px if focal_length_px is not None else exif_focal
        if supplied_focal is None:
            prediction = self._model.infer(transformed)
        else:
            f_px = torch.tensor(float(supplied_focal), device=torch.device(self._resolved_device))
            prediction = self._model.infer(transformed, f_px=f_px)
        depth_value = prediction["depth"]
        depth = np.asarray(depth_value.detach().cpu().numpy() if hasattr(depth_value, "detach") else depth_value, dtype=np.float32)
        raw_focal = prediction.get("focallength_px", prediction.get("focal_length_px", supplied_focal))
        focal = float(raw_focal.detach().cpu().item() if hasattr(raw_focal, "detach") else raw_focal) if raw_focal is not None else None
        confidence = confidence_from_depth(depth)
        return MetricDepthResult(
            depth,
            focal,
            confidence,
            "Apple Depth Pro",
            "local",
            {
                "checkpoint": str(self.model_path),
                "runtime": "local_only",
                "requested_device": self.device,
                "resolved_device": self._resolved_device,
            },
        )

def confidence_from_depth(depth: np.ndarray) -> np.ndarray:
    valid = np.isfinite(depth) & (depth > 0)
    if not valid.any(): return np.zeros(depth.shape, dtype=np.float32)
    low, high = np.percentile(depth[valid], (1, 99))
    edge = np.zeros_like(depth, dtype=float)
    edge[1:-1, 1:-1] = np.hypot(np.diff(depth, axis=0, prepend=depth[:1]), np.diff(depth, axis=1, prepend=depth[:, :1]))[1:-1,1:-1]
    scale = np.nanpercentile(edge[valid], 95) or 1.0
    return (valid * np.clip(1 - edge / scale, 0.0, 1.0) * ((depth >= low) & (depth <= high))).astype(np.float32)

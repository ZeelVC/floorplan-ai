from pathlib import Path
from typing import Protocol, Sequence
from .models import ReconstructionResult
class ReconstructionBackend(Protocol):
    def reconstruct(self, inputs: Sequence[Path], output_dir: Path, *, camera_model: str = "SIMPLE_RADIAL", single_camera: bool = False) -> ReconstructionResult: ...

from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
from typing import Sequence
from floorplan_ai.dataset.models import CaptureDataset,CaptureInput
from floorplan_ai.reconstruction import ColmapBackend
from .common import build_model
@dataclass(frozen=True)
class PhotoFrontendConfig: reconstruction:object=field(default_factory=ColmapBackend); image:dict=field(default_factory=dict); plane:dict=field(default_factory=dict); scale:dict=field(default_factory=dict)
def reconstruct_photos(captures:CaptureDataset|Sequence[CaptureInput],output_dir:Path,config:PhotoFrontendConfig|None=None):
    config=config or PhotoFrontendConfig(); items=tuple(captures.captures if isinstance(captures,CaptureDataset) else captures)
    if not items or any(x.source_type!='photo' for x in items):raise ValueError('reconstruct_photos requires one or more photo CaptureInput records')
    paths=[x.resolved_file or Path(x.file) for x in items]; return build_model(items,config.reconstruction.reconstruct(paths,output_dir),output_dir,'photo')

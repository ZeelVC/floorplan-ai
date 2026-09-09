from __future__ import annotations
from dataclasses import dataclass,field
from pathlib import Path
from typing import Sequence
from floorplan_ai.dataset.models import CaptureDataset,CaptureInput
from floorplan_ai.reconstruction import ColmapBackend
from floorplan_ai.capture import photo_metadata
from .common import build_model, MetricDepthConfig
@dataclass(frozen=True)
class PhotoFrontendConfig: reconstruction:object=field(default_factory=ColmapBackend); image:dict=field(default_factory=dict); plane:dict=field(default_factory=dict); scale:dict=field(default_factory=dict); metric_depth: MetricDepthConfig | None = None
def reconstruct_photos(captures:CaptureDataset|Sequence[CaptureInput],output_dir:Path,config:PhotoFrontendConfig|None=None):
    config=config or PhotoFrontendConfig(); items=tuple(captures.captures if isinstance(captures,CaptureDataset) else captures)
    if not items or any(x.source_type!='photo' for x in items):raise ValueError('reconstruct_photos requires one or more photo CaptureInput records')
    paths=[x.resolved_file or Path(x.file) for x in items]
    enriched=[]; priors={}
    for item,path in zip(items,paths):
        metadata={**item.metadata,**photo_metadata(path)}
        enriched.append(item.model_copy(update={'metadata':metadata}))
        focal=metadata.get('focal_length_35mm')
        if focal and metadata.get('width'):
            priors[path.name]={'width':metadata['width'],'focal_length_pixels':float(focal)*float(metadata['width'])/36.0}
    try: result=config.reconstruction.reconstruct(paths,output_dir,camera_priors=priors)
    except TypeError: result=config.reconstruction.reconstruct(paths,output_dir)
    return build_model(tuple(enriched),result,output_dir,'photo',config.plane,config.metric_depth)

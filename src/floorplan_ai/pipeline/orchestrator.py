from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from floorplan_ai.dataset.models import CaptureInput
from floorplan_ai.frontend import reconstruct_photos,reconstruct_video
from floorplan_ai.frontend.photo import PhotoFrontendConfig
from floorplan_ai.frontend.common import MetricDepthConfig
from floorplan_ai.depth import DepthProEstimator
from floorplan_ai.inference import StructuralInferenceConfig, infer_structure
from floorplan_ai.measurement import measurements_for
from floorplan_ai.output import export_json,export_svg,export_dxf
from floorplan_ai.canonical.schema import CanonicalWorldModel, Provenance
from floorplan_ai.stitching import candidate_pairs, components, reconcile
from .routing import detect_input,photo_groups
@dataclass(frozen=True)
class PipelineConfig:
 depth_enabled: bool = True
 depth_model_path: Path = Path('models/depth_pro.pt')
 depth_device: str = 'auto'
 disable_drift_correction: bool = False
@dataclass(frozen=True)
class ReconstructionRunResult: output_dir:Path; model:object
def run_reconstruction(input_path:Path,output_dir:Path,config:PipelineConfig=PipelineConfig()):
 if config.depth_enabled and not config.depth_model_path.exists(): raise RuntimeError(f'metric_depth: Depth Pro checkpoint missing: {config.depth_model_path}')
 depth_config = MetricDepthConfig(DepthProEstimator(config.depth_model_path, config.depth_device)) if config.depth_enabled else None
 output_dir.mkdir(parents=True,exist_ok=True); mode=detect_input(input_path)
 if mode=='video': model=reconstruct_video(CaptureInput(capture_id='video',source_type='video',file=input_path.name,resolved_file=input_path),output_dir)
 else:
  local_models=[]
  for group in photo_groups(input_path):
   local_output=output_dir/'reconstruction'/group.capture_id
   inputs=tuple(CaptureInput(capture_id=f'{group.capture_id}-{i}',source_type='photo',file=p.name,resolved_file=p,metadata={'room_group_id':group.room_group_id} if group.room_group_id else {}) for i,p in enumerate(group.paths))
   local_models.append(infer_structure(reconstruct_photos(inputs,local_output,PhotoFrontendConfig(metric_depth=depth_config)), StructuralInferenceConfig(artifact_root=local_output)))
  # Models remain independent components unless registration evidence supports a transform.
  if len(local_models)==1: model=local_models[0]
  else:
   fields=('frames','captures','cameras','poses','observations','geometries','planes','rooms','walls','openings','relationships','scale_estimates')
   payload={field:tuple(item for local in local_models for item in getattr(local,field)) for field in fields}
   model=CanonicalWorldModel(**payload,provenance=Provenance(generating_pipeline_stage='property_stitching'))
  model=reconcile(model)
 model=model.model_copy(update={'measurements':measurements_for(model)})
 export_json(model,output_dir/'floorplan.json'); export_svg(model,output_dir/'floorplan.svg'); export_dxf(model,output_dir/'floorplan.dxf')
 diagnostics=json.loads((output_dir/'diagnostics.json').read_text()) if (output_dir/'diagnostics.json').exists() else {}; diagnostics['stitching_components']=len(components(len(model.rooms), ())) if mode=='photo' else 1; diagnostics.update({'drift_correction_enabled':not config.disable_drift_correction,'wall_count':len(model.walls),'room_count':len(model.rooms),'opening_count':len(model.openings)}); (output_dir/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2,sort_keys=True)); (output_dir/'provenance.json').write_text(model.provenance.model_dump_json(indent=2) if model.provenance else '{}')
 return ReconstructionRunResult(output_dir,model)

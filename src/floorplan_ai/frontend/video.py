from __future__ import annotations
import json
from dataclasses import dataclass,field
from pathlib import Path
from floorplan_ai.dataset.models import CaptureInput
from floorplan_ai.reconstruction import ColmapBackend
from floorplan_ai.video.frames import extract_frames
from floorplan_ai.video.quality import FrameQualityConfig,filter_frames
from .common import build_model
@dataclass(frozen=True)
class VideoFrontendConfig: frame_sampling:dict=field(default_factory=lambda:{'target_fps':2,'max_frames':300}); quality:FrameQualityConfig=field(default_factory=FrameQualityConfig); reconstruction:object=field(default_factory=ColmapBackend); plane:dict=field(default_factory=dict); scale:dict=field(default_factory=dict)
def reconstruct_video(capture:CaptureInput,output_dir:Path,config:VideoFrontendConfig|None=None):
 config=config or VideoFrontendConfig()
 if capture.source_type!='video':raise ValueError('reconstruct_video requires a video CaptureInput')
 frames=extract_frames(capture.resolved_file or Path(capture.file),output_dir/'frames',**config.frame_sampling); selected,rejected=filter_frames(frames,config.quality)
 if not selected:raise ValueError('Video decoding produced no usable frames')
 result=config.reconstruction.reconstruct([f.path for f in selected],output_dir); inputs=tuple(CaptureInput(capture_id=f'{capture.capture_id}-{f.frame_id}',source_type='photo',file=str(f.path.relative_to(output_dir))) for f in selected)
 model=build_model(inputs,result,output_dir,'video'); trajectory=[{'frame_id':f.frame_id,'timestamp_seconds':f.timestamp_seconds} for f in selected]; (output_dir/'reconstruction'/'trajectory.json').write_text(json.dumps(trajectory,indent=2,sort_keys=True)); diag=json.loads((output_dir/'diagnostics.json').read_text()); diag.update({'frames_decoded':len(frames),'frames_selected':len(selected),'frames_rejected':len(rejected),'trajectory_pose_count':len(model.poses)}); (output_dir/'diagnostics.json').write_text(json.dumps(diag,indent=2,sort_keys=True)); return model

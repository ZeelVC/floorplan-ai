from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
from floorplan_ai.canonical.schema import *
from floorplan_ai.geometry import PlaneConfig, extract_planes, write_ply
from floorplan_ai.reconstruction.colmap import colmap_pose_to_canonical
from floorplan_ai.reconstruction.models import ReconstructionResult
from floorplan_ai.reconstruction.scale import ScaleEstimator

_STABLE_SCOPE = ''
def stable_id(value:str)->UUID:return uuid5(NAMESPACE_URL,'floorplan-ai/m6/'+_STABLE_SCOPE+'/'+value)
def provenance(stage:str,captures=(),poses=(),observations=()):return Provenance(source_capture_ids=tuple(captures),source_pose_ids=tuple(poses),source_observation_ids=tuple(observations),generating_pipeline_stage=stage,timestamp=datetime.now(timezone.utc))
def camera_intrinsics(camera):
    p=camera.params; model=camera.model; focal=None; principal=None; distortion=()
    if model=='SIMPLE_PINHOLE': focal=(p[0],p[0]); principal=(p[1],p[2])
    elif model=='PINHOLE': focal=(p[0],p[1]); principal=(p[2],p[3])
    elif model=='SIMPLE_RADIAL': focal=(p[0],p[0]); principal=(p[1],p[2]); distortion=(p[3],)
    elif model=='RADIAL': focal=(p[0],p[0]); principal=(p[1],p[2]); distortion=(p[3],p[4])
    return focal,principal,distortion

def build_model(capture_inputs, result:ReconstructionResult, output_dir:Path, source_type:str, plane_config:dict|None=None)->CanonicalWorldModel:
    global _STABLE_SCOPE
    _STABLE_SCOPE = str(output_dir.resolve())
    output_dir.mkdir(parents=True,exist_ok=True); frame=CoordinateFrame(frame_id=stable_id(str(output_dir.resolve())+'/frame'),frame_type=FrameType.LOCAL)
    captures=tuple(Capture(capture_id=stable_id('capture/'+c.capture_id),capture_type=source_type,payload_reference=c.file,metadata=dict(c.metadata)) for c in capture_inputs)
    cap_by_name={Path(c.file).name:capture.capture_id for c,capture in zip(capture_inputs,captures)}; default_capture=captures[0].capture_id
    cameras=[]; camera_by_backend={}
    for raw in result.camera_models:
        focal,pp,dist=camera_intrinsics(raw); cid=stable_id('camera/'+str(raw.camera_id)); camera_by_backend[raw.camera_id]=cid
        matching=next((c for c in capture_inputs if Path(c.file).name in {image.name for image in result.images if image.camera_id == raw.camera_id}), None)
        metadata=matching.metadata if matching else {}
        prior='EXIF+reconstruction' if metadata.get('focal_length') or metadata.get('focal_length_35mm') else 'reconstruction'
        cameras.append(Camera(camera_id=cid,capture_id=cap_by_name.get(Path(matching.file).name,default_capture) if matching else default_capture,focal_length=focal,principal_point=pp,distortion_coefficients=dist,resolution=(raw.width,raw.height),prior_source=prior))
    poses=[]; pose_by_name={}
    for raw in result.poses:
        pid=stable_id('pose/'+str(raw.image_id)); pose_by_name[raw.image_name]=pid; poses.append(Pose(pose_id=pid,frame_id=frame.frame_id,camera_to_frame=colmap_pose_to_canonical(raw.qvec,raw.tvec)))
    observations=[]
    for c,cap in zip(capture_inputs,captures):
        name=Path(c.file).name; observations.append(Observation(observation_id=stable_id('image/'+c.capture_id),pose_id=pose_by_name.get(name),camera_id=(camera_by_backend.get(next((x.camera_id for x in result.images if x.name==name),-1))),observation_type=ObservationType.IMAGE,payload_reference=c.file))
    obsdir=output_dir/'observations'; obsdir.mkdir(exist_ok=True); correspondence={'pairs':result.diagnostics.get('correspondences',[]),'reconstruction_success':result.success}; (obsdir/'correspondences.json').write_text(json.dumps(correspondence,sort_keys=True,indent=2))
    if len(captures)>1: observations.append(Observation(observation_id=stable_id('correspondences'),observation_type=ObservationType.FEATURE_CORRESPONDENCE,payload_reference='observations/correspondences.json'))
    geometries=[]; planes=[]; plane_result=None
    if result.success and result.points:
        points_path=output_dir/'reconstruction'/'points.ply'; write_ply(result.points,points_path); xyz=[p.xyz for p in result.points]; lo=tuple(min(v[i] for v in xyz) for i in range(3)); hi=tuple(max(v[i] for v in xyz) for i in range(3)); geometries.append(Geometry3D(geometry_id=stable_id('geometry/points'),frame_id=frame.frame_id,geometry_type=GeometryType.POINT_CLOUD,vertex_buffer_reference='reconstruction/points.ply',bounding_box=(lo,hi),point_density=len(xyz)/max(1e-9,(hi[0]-lo[0])*(hi[1]-lo[1])*(hi[2]-lo[2]))))
        try: plane_result=extract_planes(xyz, PlaneConfig(**(plane_config or {})))
        except RuntimeError: plane_result=None
        for i,p in enumerate(plane_result.planes): planes.append(Plane(plane_id=stable_id('plane/'+str(i)),frame_id=frame.frame_id,normal_vector=p.normal,distance_offset=p.offset,boundary_polygon_3d=p.boundary,inlier_count=p.inlier_count,rmse=p.rmse,uncertainty=Uncertainty(distribution_type='plane_fit',confidence_bounds=(max(0.,p.rmse*.5),p.rmse*1.5)),provenance=provenance('plane_extraction',tuple(c.capture_id for c in captures))))
    scale=ScaleEstimator().estimate(validated_camera_metadata=False)
    canonical=CanonicalWorldModel(frames=(frame,),captures=captures,cameras=tuple(cameras),poses=tuple(poses),observations=tuple(observations),geometries=tuple(geometries),planes=tuple(planes),scale_estimates=(ScaleEstimate(frame_id=frame.frame_id,scale_factor=scale.scale_factor,confidence=scale.confidence,evidence=(),provenance=provenance('scale_estimation',tuple(c.capture_id for c in captures))),),provenance=provenance(source_type+'_reconstruction',tuple(c.capture_id for c in captures)))
    rdir=output_dir/'reconstruction'; rdir.mkdir(exist_ok=True); (rdir/'cameras.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.camera_models],sort_keys=True,indent=2)); (rdir/'poses.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.poses],sort_keys=True,indent=2))
    diag={'source_type':source_type,'input_count':len(capture_inputs),'successful_input_count':len(capture_inputs),'backend':result.backend_name,'reconstruction_success':result.success,'camera_count':len(cameras),'pose_count':len(poses),'point_count':len(result.points),'plane_count':len(planes),'floor_plane_found':bool(plane_result and plane_result.floor_index is not None),'ceiling_plane_found':bool(plane_result and plane_result.ceiling_index is not None),'wall_plane_candidate_count':sum(p.orientation=='VERTICAL' for p in (plane_result.planes if plane_result else ())),'scale_state':scale.state.value,'scale_confidence':scale.confidence,'warnings':[] if result.success else [result.failure_reason],'errors':[]}
    (output_dir/'diagnostics.json').write_text(json.dumps(diag,sort_keys=True,indent=2)); (output_dir/'canonical.json').write_text(canonical.to_json()); return canonical

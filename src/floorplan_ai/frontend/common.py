from __future__ import annotations
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
import numpy as np
from floorplan_ai.canonical.schema import *
from floorplan_ai.geometry import PlaneConfig, extract_planes, write_ply
from floorplan_ai.reconstruction.colmap import colmap_pose_to_canonical
from floorplan_ai.reconstruction.models import ReconstructionResult
from floorplan_ai.reconstruction.scale import ScaleEstimator
from floorplan_ai.depth import MetricDepthEstimator, robust_scale_estimate, transform_points, unproject_depth, scale_points, scale_pose_translation, fuse_metric_clouds

@dataclass(frozen=True)
class MetricDepthConfig:
    estimator: MetricDepthEstimator
    depth_stride: int = 4
    maximum_depth_points: int = 100_000
    min_confidence: float = 0.2
    require_scale_evidence: bool = True
    fusion_distance_threshold: float = 0.02

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

def _planes_from_result(plane_result,world):
    return tuple(Plane(plane_id=stable_id('plane/'+str(i)),frame_id=world.frames[0].frame_id,normal_vector=p.normal,distance_offset=p.offset,boundary_polygon_3d=p.boundary,inlier_count=p.inlier_count,rmse=p.rmse,uncertainty=Uncertainty(distribution_type='plane_fit',confidence_bounds=(max(0.,p.rmse*.5),p.rmse*1.5)),provenance=provenance('plane_extraction',tuple(c.capture_id for c in world.captures))) for i,p in enumerate(plane_result.planes))

def _write_point_cloud(points,path):
    path.parent.mkdir(parents=True,exist_ok=True); np.savetxt(path,np.asarray(points,dtype=float),fmt='%.7f')

def _scale_uncertainty(scale):
    return Uncertainty(distribution_type='depth_scale_mad',confidence_bounds=(0.0,scale.uncertainty))

def _scale_sparse_geometry(result,poses,factor):
    points=np.asarray([p.xyz for p in result.points],dtype=float) if result.points else np.empty((0,3),dtype=float)
    scaled_points=scale_points(points,factor) if len(points) else points
    poses_scaled=tuple(p.model_copy(update={'camera_to_frame':scale_pose_translation(p.camera_to_frame,factor)}) for p in poses)
    return scaled_points,poses_scaled

def _write_outputs(world,result,output_dir,source_type,captures,scale,plane_result):
    rdir=output_dir/'reconstruction'; rdir.mkdir(exist_ok=True)
    (rdir/'cameras.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.camera_models],sort_keys=True,indent=2))
    (rdir/'poses.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.poses],sort_keys=True,indent=2))
    planes=world.planes
    horizontal=[p for p in planes if abs(p.normal_vector[2])>=0.85]
    floor_plane=min(horizontal,key=lambda p:-p.distance_offset) if horizontal else None
    ceiling_plane=None
    if floor_plane is not None:
        floor_z=-floor_plane.distance_offset/floor_plane.normal_vector[2]
        above=[p for p in horizontal if p.plane_id!=floor_plane.plane_id and (-p.distance_offset/p.normal_vector[2])>floor_z]
        ceiling_plane=max(above,key=lambda p:p.inlier_count) if above else None
    metric_scale=world.scale_estimates[-1] if world.scale_estimates else None
    diag={'source_type':source_type,'input_count':len(captures),'successful_input_count':len(captures),'backend':result.backend_name,'reconstruction_success':result.success,'camera_count':len(world.cameras),'pose_count':len(world.poses),'point_count':len(result.points),'plane_count':len(planes),'floor_plane_found':floor_plane is not None,'ceiling_plane_found':ceiling_plane is not None,'wall_plane_candidate_count':sum(abs(p.normal_vector[2])<=.2 for p in planes),'scale_state':scale.state.value,'scale_confidence':float(metric_scale.confidence if metric_scale else scale.confidence),'warnings':[] if result.success else [result.failure_reason],'errors':[]}
    (output_dir/'diagnostics.json').write_text(json.dumps(diag,sort_keys=True,indent=2))
    (output_dir/'canonical.json').write_text(world.to_json())

def build_model(capture_inputs, result:ReconstructionResult, output_dir:Path, source_type:str, plane_config:dict|None=None, metric_depth=None)->CanonicalWorldModel:
    global _STABLE_SCOPE
    _STABLE_SCOPE = str(output_dir.resolve())
    output_dir.mkdir(parents=True,exist_ok=True)

    # Never allow a failed or empty camera reconstruction to reach metric-depth
    # fusion.  Previously this was converted into the much less useful
    # "no valid reconstructed frame" error, hiding the actual COLMAP failure.
    if not result.success:
        reason = result.failure_reason or 'reconstruction backend reported failure without a reason'
        raise RuntimeError(f'{source_type}_reconstruction: {reason}')
    if not result.camera_models:
        raise RuntimeError(f'{source_type}_reconstruction: backend produced no camera models; verify COLMAP input and feature extraction')
    if not result.poses:
        raise RuntimeError(f'{source_type}_reconstruction: backend produced no registered camera poses; provide overlapping views of the same scene and verify COLMAP mapper output')

    frame=CoordinateFrame(frame_id=stable_id(str(output_dir.resolve())+'/frame'),frame_type=FrameType.LOCAL)
    captures=tuple(Capture(capture_id=stable_id('capture/'+c.capture_id),capture_type=source_type,payload_reference=c.file,metadata=dict(c.metadata)) for c in capture_inputs)
    cap_by_name={Path(c.payload_reference).name:c.capture_id for c in captures}; default_capture=captures[0].capture_id
    cameras=[]; camera_by_backend={}
    for raw in result.camera_models:
        focal,pp,dist=camera_intrinsics(raw); cid=stable_id('camera/'+str(raw.camera_id)); camera_by_backend[raw.camera_id]=cid
        matching=next((c for c in capture_inputs if Path(c.file).name in {image.name for image in result.images if image.camera_id == raw.camera_id}), None)
        metadata=matching.metadata if matching else {}
        prior='EXIF+reconstruction' if metadata.get('focal_length') or metadata.get('focal_length_35mm') else 'reconstruction'
        cameras.append(Camera(camera_id=cid,capture_id=cap_by_name.get(Path(matching.file).name,default_capture) if matching else default_capture,focal_length=focal,principal_point=pp,distortion_coefficients=dist,resolution=(raw.width,raw.height),prior_source=prior))
    poses=[]; pose_by_name={}
    for raw in result.poses:
        pid=stable_id('pose/'+str(raw.image_id)); pose_by_name[raw.image_name]=pid
        poses.append(Pose(pose_id=pid,frame_id=frame.frame_id,camera_to_frame=colmap_pose_to_canonical(raw.qvec,raw.tvec)))
    observations=[]
    for c in capture_inputs:
        name=Path(c.file).name
        observations.append(Observation(observation_id=stable_id('image/'+c.capture_id),pose_id=pose_by_name.get(name),camera_id=(camera_by_backend.get(next((x.camera_id for x in result.images if x.name==name),-1))),observation_type=ObservationType.IMAGE,payload_reference=c.file))
    obsdir=output_dir/'observations'; obsdir.mkdir(exist_ok=True)
    (obsdir/'correspondences.json').write_text(json.dumps({'pairs':result.diagnostics.get('correspondences',[]),'reconstruction_success':result.success},sort_keys=True,indent=2))
    if len(captures)>1: observations.append(Observation(observation_id=stable_id('correspondences'),observation_type=ObservationType.FEATURE_CORRESPONDENCE,payload_reference='observations/correspondences.json'))
    scale=ScaleEstimator().estimate(validated_camera_metadata=False)
    canonical=CanonicalWorldModel(frames=(frame,),captures=captures,cameras=tuple(cameras),poses=tuple(poses),observations=tuple(observations),geometries=(),scale_estimates=(ScaleEstimate(frame_id=frame.frame_id,scale_factor=scale.scale_factor,confidence=scale.confidence,evidence=(),provenance=provenance('scale_estimation',tuple(c.capture_id for c in captures))),),provenance=provenance(source_type+'_reconstruction',tuple(c.capture_id for c in captures)))
    if metric_depth is not None:
        canonical=integrate_metric_depth(canonical,capture_inputs,result,output_dir,metric_depth,plane_config)
    else:
        canonical=integrate_sparse_geometry(canonical,result,output_dir,plane_config)
    _write_outputs(canonical,result,output_dir,source_type,captures,scale,None)
    return canonical

def integrate_sparse_geometry(world,result,output_dir:Path,plane_config=None):
    if not result.points:return world
    points=np.asarray([p.xyz for p in result.points],dtype=float); path=output_dir/'reconstruction'/'points_metric.xyz'; _write_point_cloud(points,path)
    geometry=Geometry3D(geometry_id=stable_id('geometry/points'),frame_id=world.frames[0].frame_id,geometry_type=GeometryType.POINT_CLOUD,vertex_buffer_reference=str(path.relative_to(output_dir)),bounding_box=(tuple(np.min(points,0)),tuple(np.max(points,0))),point_density=0.)
    try: plane_result=extract_planes(points,PlaneConfig(**(plane_config or {})))
    except RuntimeError: plane_result=type('PR',(),{'planes':()})()
    return world.model_copy(update={'geometries':(geometry,),'planes':_planes_from_result(plane_result,world)})

def integrate_metric_depth(world,capture_inputs,result,output_dir:Path,config,plane_config=None):
    cameras={camera.camera_id:camera for camera in world.cameras}; pose_by_id={pose.pose_id:pose for pose in world.poses}
    raw_pose_ids={raw.image_name:stable_id('pose/'+str(raw.image_id)) for raw in result.poses}; raw_camera_ids={raw.name:stable_id('camera/'+str(raw.camera_id)) for raw in result.images}; inputs={Path(item.file).name:item for item in capture_inputs}
    out=output_dir/'depth'; out.mkdir(parents=True,exist_ok=True)
    observations=list(world.observations); sparse_depth=[]; metric_depth=[]; camera_pose_pairs=[]
    for image_name,pose_id in raw_pose_ids.items():
        pose=pose_by_id.get(pose_id); camera=cameras.get(raw_camera_ids.get(image_name)); item=inputs.get(Path(image_name).name)
        if pose is None or camera is None or item is None or camera.focal_length is None or camera.principal_point is None: continue
        fx,fy=camera.focal_length; cx,cy=camera.principal_point; K=np.array(((fx,0.,cx),(0.,fy,cy),(0.,0.,1.)))
        prediction=config.estimator.predict(item.resolved_file or Path(item.file),focal_length_px=float(fx)); depth,confidence=np.asarray(prediction.depth_map),np.asarray(prediction.confidence_map)
        if depth.ndim!=2 or depth.size==0 or confidence.shape!=depth.shape: raise RuntimeError(f'metric_depth: invalid depth result for {image_name}')
        mask=np.isfinite(depth)&(depth>0)&(confidence>=config.min_confidence); camera_points=unproject_depth(depth,K,mask,stride=config.depth_stride,maximum_points=config.maximum_depth_points)
        if not len(camera_points): raise RuntimeError(f'metric_depth: no confident depth points for {image_name}')
        camera_pose_pairs.append((pose,camera_points)); stem=Path(image_name).stem; depth_path,mask_path=out/f'{stem}.depth.npy',out/f'{stem}.confidence.npy'; np.save(depth_path,depth); np.save(mask_path,mask)
        observations.append(Observation(observation_id=stable_id('depth/'+image_name),pose_id=pose.pose_id,camera_id=camera.camera_id,observation_type=ObservationType.DEPTH,payload_reference=str(depth_path.relative_to(output_dir)),confidence_mask=str(mask_path.relative_to(output_dir)))
        inverse=np.linalg.inv(np.asarray(pose.camera_to_frame))
        for point in result.points:
            local=inverse@np.array((*point.xyz,1.))
            if local[2]<=0: continue
            pixel=K@local[:3]; u,v=int(round(pixel[0]/pixel[2])),int(round(pixel[1]/pixel[2]))
            if 0<=v<depth.shape[0] and 0<=u<depth.shape[1] and mask[v,u]: sparse_depth.append(float(local[2])); metric_depth.append(float(depth[v,u]))
    if not camera_pose_pairs: raise RuntimeError('metric_depth: no valid reconstructed frame has usable intrinsics and pose')
    try: scale=robust_scale_estimate(np.array(sparse_depth),np.array(metric_depth))
    except ValueError as exc:
        if config.require_scale_evidence: raise RuntimeError(f'metric_depth: insufficient scale correspondences: {exc}') from exc
        class _ScaleFallback: pass
        scale=_ScaleFallback(); scale.scale=1.0; scale.uncertainty=0.0; scale.confidence=0.0; scale.state=ScaleState.UNKNOWN
    factor=float(scale.scale); sparse_metric,poses_metric=_scale_sparse_geometry(result,world.poses,factor)
    dense_metric=np.vstack([transform_points(points,scale_pose_translation(pose.camera_to_frame,factor)) for pose,points in camera_pose_pairs]); fused=fuse_metric_clouds(sparse_metric,dense_metric,distance_threshold=config.fusion_distance_threshold)
    if not len(fused): raise RuntimeError('metric_depth: fused metric cloud is empty')
    point_path=out/'metric_fused_points.xyz'; _write_point_cloud(fused,point_path)
    bbox=(tuple(np.min(fused,axis=0)),tuple(np.max(fused,axis=0)))
    geometry=Geometry3D(geometry_id=stable_id('geometry/metric-fused'),frame_id=world.frames[0].frame_id,geometry_type=GeometryType.POINT_CLOUD,vertex_buffer_reference=str(point_path.relative_to(output_dir)),bounding_box=bbox,point_density=0.)
    plane_result=extract_planes(fused,PlaneConfig(**(plane_config or {}))); planes=_planes_from_result(plane_result,world)
    metric_scale=ScaleEstimate(frame_id=world.frames[0].frame_id,scale_factor=factor,confidence=float(scale.confidence),evidence=(ScaleEvidenceType.METRIC_DEPTH,ScaleEvidenceType.GEOMETRIC_CONSISTENCY),uncertainty=_scale_uncertainty(scale),provenance=provenance('metric_depth_scale',tuple(c.capture_id for c in world.captures)))
    return world.model_copy(update={'poses':poses_metric,'observations':tuple(observations),'geometries':(geometry,),'planes':planes,'scale_estimates':(metric_scale,)})

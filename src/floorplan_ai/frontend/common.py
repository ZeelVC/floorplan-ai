from __future__ import annotations
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL
from floorplan_ai.canonical.schema import *
from floorplan_ai.geometry import PlaneConfig, extract_planes, write_ply
from floorplan_ai.reconstruction.colmap import colmap_pose_to_canonical
from floorplan_ai.reconstruction.models import ReconstructionResult
from floorplan_ai.reconstruction.scale import ScaleEstimator
from floorplan_ai.depth import MetricDepthEstimator, robust_scale_estimate, transform_points, unproject_depth


@dataclass(frozen=True)
class MetricDepthConfig:
    """Settings for the local metric-depth stage of a photo reconstruction."""

    estimator: MetricDepthEstimator
    depth_stride: int = 4
    maximum_depth_points: int = 100_000
    min_confidence: float = 0.2
    require_scale_evidence: bool = True

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

def build_model(capture_inputs, result:ReconstructionResult, output_dir:Path, source_type:str, plane_config:dict|None=None, metric_depth=None)->CanonicalWorldModel:
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
    if metric_depth is not None:
        canonical = integrate_metric_depth(canonical, capture_inputs, result, output_dir, metric_depth)
    rdir=output_dir/'reconstruction'; rdir.mkdir(exist_ok=True); (rdir/'cameras.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.camera_models],sort_keys=True,indent=2)); (rdir/'poses.json').write_text(json.dumps([x.model_dump(mode='json') for x in result.poses],sort_keys=True,indent=2))
    diag={'source_type':source_type,'input_count':len(capture_inputs),'successful_input_count':len(capture_inputs),'backend':result.backend_name,'reconstruction_success':result.success,'camera_count':len(cameras),'pose_count':len(poses),'point_count':len(result.points),'plane_count':len(planes),'floor_plane_found':bool(plane_result and plane_result.floor_index is not None),'ceiling_plane_found':bool(plane_result and plane_result.ceiling_index is not None),'wall_plane_candidate_count':sum(p.orientation=='VERTICAL' for p in (plane_result.planes if plane_result else ())),'scale_state':scale.state.value,'scale_confidence':scale.confidence,'warnings':[] if result.success else [result.failure_reason],'errors':[]}
    (output_dir/'diagnostics.json').write_text(json.dumps(diag,sort_keys=True,indent=2)); (output_dir/'canonical.json').write_text(canonical.to_json()); return canonical


def integrate_metric_depth(world, capture_inputs, result, output_dir: Path, config):
    """Persist local metric depth, canonical depth points, and matched scale evidence."""
    from floorplan_ai.depth import robust_scale_estimate, transform_points, unproject_depth
    cameras = {camera.camera_id: camera for camera in world.cameras}
    pose_by_id = {pose.pose_id: pose for pose in world.poses}
    raw_pose_ids = {raw.image_name: stable_id('pose/' + str(raw.image_id)) for raw in result.poses}
    raw_camera_ids = {raw.name: stable_id('camera/' + str(raw.camera_id)) for raw in result.images}
    inputs = {Path(item.file).name: item for item in capture_inputs}
    out = output_dir / 'depth'; out.mkdir(parents=True, exist_ok=True)
    clouds, observations, sparse, metric = [], list(world.observations), [], []
    for image_name, pose_id in raw_pose_ids.items():
        pose, camera, item = pose_by_id.get(pose_id), cameras.get(raw_camera_ids.get(image_name)), inputs.get(Path(image_name).name)
        if pose is None or camera is None or item is None or camera.focal_length is None or camera.principal_point is None:
            continue
        fx, fy = camera.focal_length; cx, cy = camera.principal_point
        K = np.array(((fx, 0., cx), (0., fy, cy), (0., 0., 1.)))
        prediction = config.estimator.predict(item.resolved_file or Path(item.file), focal_length_px=float(fx))
        depth, confidence = np.asarray(prediction.depth_map), np.asarray(prediction.confidence_map)
        if depth.ndim != 2 or depth.size == 0 or confidence.shape != depth.shape:
            raise RuntimeError(f'metric_depth: invalid depth result for {image_name}')
        mask = np.isfinite(depth) & (depth > 0) & (confidence >= config.min_confidence)
        camera_points = unproject_depth(depth, K, mask, stride=config.depth_stride, maximum_points=config.maximum_depth_points)
        if not len(camera_points):
            raise RuntimeError(f'metric_depth: no confident depth points for {image_name}')
        clouds.append(transform_points(camera_points, pose.camera_to_frame))
        stem = Path(image_name).stem; depth_path, mask_path = out / f'{stem}.depth.npy', out / f'{stem}.confidence.npy'
        np.save(depth_path, depth); np.save(mask_path, mask)
        observations.append(Observation(observation_id=stable_id('depth/' + image_name), pose_id=pose.pose_id, camera_id=camera.camera_id, observation_type=ObservationType.DEPTH, payload_reference=str(depth_path.relative_to(output_dir)), confidence_mask=str(mask_path.relative_to(output_dir))))
        inverse = np.linalg.inv(np.asarray(pose.camera_to_frame))
        for point in result.points:
            local = inverse @ np.array((*point.xyz, 1.))
            if local[2] <= 0: continue
            pixel = K @ local[:3]; u, v = int(round(pixel[0] / pixel[2])), int(round(pixel[1] / pixel[2]))
            if 0 <= v < depth.shape[0] and 0 <= u < depth.shape[1] and mask[v, u]: sparse.append(float(local[2])); metric.append(float(depth[v, u]))
    if not clouds: raise RuntimeError('metric_depth: no valid reconstructed frame has usable intrinsics and pose')
    try: scale = robust_scale_estimate(np.array(sparse), np.array(metric))
    except ValueError as exc:
        if config.require_scale_evidence: raise RuntimeError(f'metric_depth: insufficient scale correspondences: {exc}') from exc
        scale = None
    points = np.vstack(clouds); point_path = out / 'metric_fused_points.xyz'; np.savetxt(point_path, points, fmt='%.7f')
    bbox = (tuple(np.min(points, axis=0)), tuple(np.max(points, axis=0)))
    geometry = Geometry3D(geometry_id=stable_id('geometry/metric-depth'), frame_id=world.frames[0].frame_id, geometry_type=GeometryType.POINT_CLOUD, vertex_buffer_reference=str(point_path.relative_to(output_dir)), bounding_box=bbox, point_density=0.)
    scales = world.scale_estimates
    if scale is not None:
        scales = (ScaleEstimate(frame_id=world.frames[0].frame_id, scale_factor=scale.scale, confidence=scale.confidence, evidence=(ScaleEvidenceType.METRIC_DEPTH, ScaleEvidenceType.GEOMETRIC_CONSISTENCY), uncertainty=Uncertainty(distribution_type='depth_scale_mad', confidence_bounds=(0., scale.uncertainty)), provenance=provenance('metric_depth_scale', tuple(c.capture_id for c in world.captures))),)
    return world.model_copy(update={'observations': tuple(observations), 'geometries': (*world.geometries, geometry), 'scale_estimates': scales})

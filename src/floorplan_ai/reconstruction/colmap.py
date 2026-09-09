"""Isolated subprocess adapter for COLMAP's sparse reconstruction pipeline."""
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path
from typing import Sequence
from .models import *

def colmap_pose_to_canonical(qvec: Sequence[float], tvec: Sequence[float]) -> tuple[tuple[float,float,float,float],...]:
    """Invert COLMAP world-to-camera qvec/tvec into canonical camera_to_frame."""
    qw,qx,qy,qz=(float(x) for x in qvec); n=(qw*qw+qx*qx+qy*qy+qz*qz)**.5
    if n == 0: raise ValueError("COLMAP quaternion must be non-zero")
    qw,qx,qy,qz=(x/n for x in (qw,qx,qy,qz))
    r=((1-2*(qy*qy+qz*qz),2*(qx*qy-qz*qw),2*(qx*qz+qy*qw)),(2*(qx*qy+qz*qw),1-2*(qx*qx+qz*qz),2*(qy*qz-qx*qw)),(2*(qx*qz-qy*qw),2*(qy*qz+qx*qw),1-2*(qx*qx+qy*qy)))
    rt=tuple(tuple(r[j][i] for j in range(3)) for i in range(3)); t=tuple(float(x) for x in tvec); c=tuple(-sum(rt[i][j]*t[j] for j in range(3)) for i in range(3))
    return tuple(tuple(rt[i][j] if j<3 else c[i] for j in range(4)) for i in range(3))+((0.,0.,0.,1.),)
class ColmapBackend:
    def __init__(self, executable:str="colmap", dense:bool=False): self.executable=executable; self.dense=dense
    def _run(self,args:list[str],log:Path)->None:
        result=subprocess.run(args, check=False, capture_output=True, text=True)
        log.write_text(result.stdout+"\n"+result.stderr,encoding="utf-8")
        if result.returncode: raise RuntimeError(f"{' '.join(args[1:])} failed ({result.returncode}): {result.stderr.strip()}")
    def reconstruct(self, inputs:Sequence[Path], output_dir:Path, *, camera_model:str="SIMPLE_RADIAL", single_camera:bool=False)->ReconstructionResult:
        if shutil.which(self.executable) is None: return ReconstructionResult(success=False,backend_name="COLMAP",failure_reason="COLMAP executable not found. Install COLMAP and ensure `colmap` is on PATH.")
        if not inputs: return ReconstructionResult(success=False,backend_name="COLMAP",failure_reason="No input images supplied.")
        root=output_dir/'colmap'; sparse=root/'sparse'; logs=root/'logs'; dense=root/'dense'; [p.mkdir(parents=True,exist_ok=True) for p in (sparse,logs,dense)]
        db=root/'database.db'
        try:
            self._run([self.executable,'feature_extractor','--database_path',str(db),'--image_path',str(inputs[0].parent),'--ImageReader.camera_model',camera_model,'--ImageReader.single_camera','1' if single_camera else '0'],logs/'feature_extractor.log')
            self._run([self.executable,'exhaustive_matcher','--database_path',str(db)],logs/'exhaustive_matcher.log')
            self._run([self.executable,'mapper','--database_path',str(db),'--image_path',str(inputs[0].parent),'--output_path',str(sparse)],logs/'mapper.log')
            models=sorted(p for p in sparse.iterdir() if p.is_dir())
            if not models: raise RuntimeError('mapper produced no sparse model')
            model=models[0]
            if self.dense:
                self._run([self.executable,'image_undistorter','--image_path',str(inputs[0].parent),'--input_path',str(model),'--output_path',str(dense)],logs/'image_undistorter.log'); self._run([self.executable,'patch_match_stereo','--workspace_path',str(dense)],logs/'patch_match_stereo.log'); self._run([self.executable,'stereo_fusion','--workspace_path',str(dense),'--output_path',str(dense/'fused.ply')],logs/'stereo_fusion.log')
            # Text conversion is reliable across COLMAP binary model versions.
            self._run([self.executable,'model_converter','--input_path',str(model),'--output_path',str(model/'text'),'--output_type','TXT'],logs/'model_converter.log')
            return self._parse(model/'text')
        except (OSError,RuntimeError) as exc: return ReconstructionResult(success=False,backend_name='COLMAP',failure_reason=str(exc),diagnostics={'workspace':str(root)})
    def _parse(self,path:Path)->ReconstructionResult:
        cams=[]; poses=[]; images=[]; points=[]
        for line in (path/'cameras.txt').read_text().splitlines():
            if line.startswith('#') or not line: continue
            x=line.split(); cams.append(ReconstructionCamera(camera_id=int(x[0]),model=x[1],width=int(x[2]),height=int(x[3]),params=tuple(map(float,x[4:]))))
        lines=[x for x in (path/'images.txt').read_text().splitlines() if x and not x.startswith('#')]
        for line in lines[::2]:
            x=line.split(); pose=ReconstructionPose(image_id=int(x[0]),qvec=tuple(map(float,x[1:5])),tvec=tuple(map(float,x[5:8])),camera_id=int(x[8]),image_name=x[9]); poses.append(pose); images.append(ReconstructionImage(image_id=pose.image_id,name=pose.image_name,camera_id=pose.camera_id))
        for line in (path/'points3D.txt').read_text().splitlines():
            if line.startswith('#') or not line: continue
            x=line.split(); points.append(ReconstructionPoint(point_id=int(x[0]),xyz=tuple(map(float,x[1:4])),rgb=tuple(map(int,x[4:7])),error=float(x[7])))
        return ReconstructionResult(success=True,backend_name='COLMAP',camera_models=tuple(cams),poses=tuple(poses),points=tuple(points),images=tuple(images),diagnostics={'model_path':str(path)})

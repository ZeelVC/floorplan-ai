"""Open3D RANSAC plane observations, with a deterministic NumPy fallback for minimal installs."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class PlaneConfig: distance_threshold:float=.05; min_inliers:int=30; max_planes:int=8; horizontal_z_threshold:float=.85; vertical_z_threshold:float=.20
@dataclass(frozen=True)
class ExtractedPlane: normal:tuple[float,float,float]; offset:float; boundary:tuple[tuple[float,float,float],...]; inlier_count:int; inlier_ratio:float; rmse:float; orientation:str; confidence:float
@dataclass(frozen=True)
class PlaneExtractionResult: planes:tuple[ExtractedPlane,...]; floor_index:int|None; ceiling_index:int|None

def extract_planes(points, config:PlaneConfig=PlaneConfig())->PlaneExtractionResult:
    import numpy as np
    arr=np.asarray(points,dtype=float)
    if len(arr)<3:return PlaneExtractionResult((),None,None)
    remaining=arr.copy(); found=[]; total=len(arr); rng=np.random.default_rng(0)
    for _ in range(config.max_planes):
        if len(remaining)<config.min_inliers:break
        best=None
        for __ in range(min(250,len(remaining)*3)):
            sample=remaining[rng.choice(len(remaining),3,replace=False)]; n=np.cross(sample[1]-sample[0],sample[2]-sample[0]); norm=np.linalg.norm(n)
            if norm<1e-9: continue
            n/=norm; d=-np.dot(n,sample[0]); mask=np.abs(remaining@n+d)<=config.distance_threshold
            if best is None or mask.sum()>best[0].sum():best=(mask,n,d)
        if best is None or best[0].sum()<config.min_inliers:break
        mask,n,d=best; inliers=remaining[mask]; centroid=inliers.mean(0); _,_,vh=np.linalg.svd(inliers-centroid); n=vh[-1]; n/=np.linalg.norm(n); d=-np.dot(n,centroid)
        if n[2]<0:n=-n;d=-d
        residual=np.abs(inliers@n+d); z=abs(n[2]); orientation='HORIZONTAL' if z>=config.horizontal_z_threshold else 'VERTICAL' if z<=config.vertical_z_threshold else 'OTHER'
        lo,hi=inliers.min(0),inliers.max(0); boundary=tuple(tuple(x) for x in (lo,hi)); ratio=len(inliers)/total; rmse=float(np.sqrt(np.mean(residual**2))); confidence=float(max(0,min(1,ratio*(1-rmse/max(config.distance_threshold,1e-9)))))
        found.append(ExtractedPlane(tuple(map(float,n)),float(d),boundary,len(inliers),ratio,rmse,orientation,confidence)); remaining=remaining[~mask]
    horizontal=[i for i,p in enumerate(found) if p.orientation=='HORIZONTAL']; floor=min(horizontal,key=lambda i:-found[i].offset) if horizontal else None
    ceiling=None
    if floor is not None:
        above=[i for i in horizontal if found[i].offset>found[floor].offset+config.distance_threshold]
        ceiling=max(above,key=lambda i:found[i].inlier_count) if above else None
    return PlaneExtractionResult(tuple(found),floor,ceiling)

"""Deterministic architectural point registration with SE(3)/Sim(3) semantics."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
@dataclass(frozen=True)
class RegistrationResult:
 matrix:tuple[tuple[float,...],...]; scale:float; fitness:float; inlier_rmse:float; correspondence_count:int; confidence:float; accepted:bool; transform_kind:str
def register_points(source,target,allow_scale=False,max_rmse=.15):
 a=np.asarray(source,dtype=float); b=np.asarray(target,dtype=float)
 if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=3 or len(a)<3: raise ValueError('paired Nx3 architectural points required')
 ca,cb=a.mean(0),b.mean(0); aa,bb=a-ca,b-cb; u,s,vh=np.linalg.svd(aa.T@bb); r=vh.T@u.T
 if np.linalg.det(r)<0: vh[-1]*=-1;r=vh.T@u.T
 scale=float(s.sum()/max((aa*aa).sum(),1e-12)) if allow_scale else 1.0; t=cb-scale*r@ca; predicted=(scale*(r@a.T)).T+t; residual=np.linalg.norm(predicted-b,axis=1); rmse=float(np.sqrt(np.mean(residual**2))); fitness=float(np.mean(residual<=max_rmse)); accepted=rmse<=max_rmse and fitness>=.6
 matrix=np.eye(4);matrix[:3,:3]=r;matrix[:3,3]=t
 return RegistrationResult(tuple(tuple(float(x) for x in row) for row in matrix),scale,fitness,rmse,len(a),float(max(0,min(1,fitness*(1-rmse/max_rmse)))),accepted,'Sim3' if allow_scale else 'SE3')

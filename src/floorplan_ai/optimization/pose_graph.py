"""Portable robust pose-graph translation optimizer (SciPy)."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares
@dataclass(frozen=True)
class PoseEdge: source:int; target:int; translation:tuple[float,float,float]; weight:float=1.; loop:bool=False
class PoseGraphOptimizer:
 def optimize(self,positions,edges):
  raw=np.asarray(positions,dtype=float); n=len(raw)
  if n<2 or not edges:return raw
  def residual(x):
   p=np.vstack((raw[0],x.reshape(n-1,3))); return np.concatenate([np.sqrt(e.weight)*(p[e.target]-p[e.source]-np.asarray(e.translation)) for e in edges])
  result=least_squares(residual,raw[1:].ravel(),loss='huber',f_scale=.1)
  return np.vstack((raw[0],result.x.reshape(n-1,3)))

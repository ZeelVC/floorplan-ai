"""Local ORB verification; no learned weights or network calls."""
from __future__ import annotations
def verified_loops(descriptors, temporal_exclusion=10, threshold=.8):
 import numpy as np
 out=[]
 for i,a in enumerate(descriptors):
  for j,b in enumerate(descriptors[:i-temporal_exclusion]):
   similarity=float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-12))
   if similarity>=threshold: out.append((j,i,similarity))
 return tuple(out)

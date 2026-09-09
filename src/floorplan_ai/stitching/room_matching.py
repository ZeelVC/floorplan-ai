from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class RoomCandidate: left:int; right:int; reason:str; confidence:float
def candidate_pairs(models):
 out=[]
 for i,left in enumerate(models):
  for j,right in enumerate(models[:i]):
   if left.openings and right.openings: out.append(RoomCandidate(j,i,'opening evidence',.7))
   elif left.walls and right.walls: out.append(RoomCandidate(j,i,'architectural geometry',.35))
 return tuple(out)

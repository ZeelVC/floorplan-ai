from __future__ import annotations
from dataclasses import dataclass
from floorplan_ai.canonical.schema import CanonicalWorldModel
from .planes import select_floor_ceiling
from .walls import walls_from_planes
from .rooms import rooms_from_walls
from .topology import topology
@dataclass(frozen=True)
class StructuralInferenceConfig: min_wall_length:float=.3; min_room_area:float=.5
def infer_structure(world_model:CanonicalWorldModel, config:StructuralInferenceConfig|None=None)->CanonicalWorldModel:
 config=config or StructuralInferenceConfig(); floor,ceiling=select_floor_ceiling(world_model.planes)
 altitude=lambda p:-p.distance_offset/p.normal_vector[2]
 walls=walls_from_planes(world_model.planes,altitude(floor) if floor else None,altitude(ceiling) if ceiling else None,config.min_wall_length)
 rooms=rooms_from_walls(walls,floor.plane_id if floor else None,ceiling.plane_id if ceiling else None,config.min_room_area)
 # Wall room references must resolve; rebuild after polygonization.
 walls=tuple(w.model_copy(update={'room_ids':tuple(r.room_id for r in rooms if w.wall_id in r.wall_ids)}) for w in walls)
 rooms=tuple(r.model_copy(update={'wall_ids':tuple(w.wall_id for w in walls if w.wall_id in r.wall_ids)}) for r in rooms)
 return world_model.model_copy(update={'walls':walls,'rooms':rooms,'relationships':topology(rooms,walls)})

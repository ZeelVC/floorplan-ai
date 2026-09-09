from __future__ import annotations
from floorplan_ai.canonical.schema import Plane

def select_floor_ceiling(planes: tuple[Plane,...], z_threshold: float=.85) -> tuple[Plane|None, Plane|None]:
    horizontal=[p for p in planes if abs(p.normal_vector[2]) >= z_threshold]
    if not horizontal: return None,None
    # Plane altitude, with upward normals normalized by M6.
    altitude=lambda p: -p.distance_offset/p.normal_vector[2]
    floor=min(horizontal,key=lambda p:(altitude(p),-p.inlier_count))
    candidates=[p for p in horizontal if altitude(p)>altitude(floor)+.3]
    ceiling=min(candidates,key=lambda p:(abs(altitude(p)-altitude(floor)-2.5),-p.inlier_count)) if candidates else None
    return floor,ceiling

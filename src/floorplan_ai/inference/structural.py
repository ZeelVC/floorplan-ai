from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from floorplan_ai.canonical.schema import CanonicalWorldModel
from .openings import infer_openings
from .planes import select_floor_ceiling
from .walls import walls_from_planes
from .rooms import rooms_from_walls
from .topology import topology

@dataclass(frozen=True)
class StructuralInferenceConfig:
    min_wall_length: float = .3
    min_room_area: float = .5
    artifact_root: Path | None = None

def infer_structure(world_model: CanonicalWorldModel, config: StructuralInferenceConfig | None = None) -> CanonicalWorldModel:
    """Infer structure and openings from canonical geometry artifacts only."""
    config = config or StructuralInferenceConfig()
    floor, ceiling = select_floor_ceiling(world_model.planes)
    altitude = lambda plane: -plane.distance_offset / plane.normal_vector[2]
    walls = walls_from_planes(world_model.planes, altitude(floor) if floor else None, altitude(ceiling) if ceiling else None, config.min_wall_length)
    rooms = rooms_from_walls(walls, floor.plane_id if floor else None, ceiling.plane_id if ceiling else None, config.min_room_area)
    walls = tuple(wall.model_copy(update={'room_ids': tuple(room.room_id for room in rooms if wall.wall_id in room.wall_ids)}) for wall in walls)
    openings = ()
    if floor and ceiling and walls and config.artifact_root is not None:
        cloud = _metric_cloud(world_model, config.artifact_root)
        if cloud is not None:
            openings = infer_openings(cloud, walls, floor_height=altitude(floor), ceiling_height=altitude(ceiling))
    rooms = tuple(room.model_copy(update={'wall_ids': tuple(wall.wall_id for wall in walls if wall.wall_id in room.wall_ids), 'opening_ids': tuple(opening.opening_id for opening in openings if set(opening.connected_room_ids) & {room.room_id})}) for room in rooms)
    return world_model.model_copy(update={'walls': walls, 'rooms': rooms, 'openings': openings, 'relationships': topology(rooms, walls, openings)})

def _metric_cloud(world: CanonicalWorldModel, root: Path) -> np.ndarray | None:
    geometry = next((item for item in world.geometries if item.vertex_buffer_reference.endswith('metric_fused_points.xyz')), None)
    if geometry is None:
        return None
    path = root / geometry.vertex_buffer_reference
    if not path.is_file():
        raise RuntimeError(f'structural_inference: metric point cloud artifact missing: {path}')
    points = np.loadtxt(path, dtype=float)
    return np.atleast_2d(points) if points.size else None

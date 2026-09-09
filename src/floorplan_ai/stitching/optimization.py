"""Deterministic global cleanup and topology optimization after registration."""
from __future__ import annotations

from collections import defaultdict
from math import acos, degrees

import numpy as np
from shapely.geometry import Polygon

from floorplan_ai.canonical.schema import CanonicalWorldModel, RelationshipType, SpatialRelationship


DEFAULT_TOLERANCE = 0.15


def _segment_angle(a, b) -> float:
    vector = np.asarray(b, dtype=float) - np.asarray(a, dtype=float)
    return degrees(np.arctan2(vector[1], vector[0])) % 180.0


def _parallel(a, b, tolerance_degrees: float = 5.0) -> bool:
    delta = abs(_segment_angle(a.start_point_2d, a.end_point_2d) - _segment_angle(b.start_point_2d, b.end_point_2d))
    delta = min(delta, 180.0 - delta)
    return delta <= tolerance_degrees


def _endpoint_distance(a, b) -> float:
    direct = np.linalg.norm(np.asarray(a.start_point_2d) - np.asarray(b.start_point_2d)) + np.linalg.norm(np.asarray(a.end_point_2d) - np.asarray(b.end_point_2d))
    reverse = np.linalg.norm(np.asarray(a.start_point_2d) - np.asarray(b.end_point_2d)) + np.linalg.norm(np.asarray(a.end_point_2d) - np.asarray(b.start_point_2d))
    return float(min(direct, reverse) / 2.0)


def _merge_walls(model: CanonicalWorldModel, tolerance: float) -> tuple[CanonicalWorldModel, dict]:
    walls = list(model.walls)
    mapping = {wall.wall_id: wall.wall_id for wall in walls}
    kept = []
    for wall in walls:
        duplicate = next(
            (
                existing
                for existing in kept
                if _parallel(existing, wall)
                and abs(existing.length - wall.length) <= tolerance
                and _endpoint_distance(existing, wall) <= tolerance
            ),
            None,
        )
        if duplicate is None:
            kept.append(wall)
        else:
            mapping[wall.wall_id] = duplicate.wall_id
    if len(kept) == len(walls):
        return model, mapping

    rooms = tuple(
        room.model_copy(update={"wall_ids": tuple(dict.fromkeys(mapping.get(wall_id, wall_id) for wall_id in room.wall_ids))})
        for room in model.rooms
    )
    openings = tuple(
        opening.model_copy(update={"parent_wall_id": mapping.get(opening.parent_wall_id, opening.parent_wall_id)})
        for opening in model.openings
    )
    kept = [
        wall.model_copy(update={"room_ids": tuple(dict.fromkeys(room_id for room_id in wall.room_ids))})
        for wall in kept
    ]
    # Recompute wall-to-room links from the remapped room boundaries.
    room_by_wall = defaultdict(list)
    for room in rooms:
        for wall_id in room.wall_ids:
            room_by_wall[wall_id].append(room.room_id)
    kept = [wall.model_copy(update={"room_ids": tuple(room_by_wall.get(wall.wall_id, wall.room_ids))}) for wall in kept]
    openings = tuple(
        opening.model_copy(update={"connected_room_ids": tuple(room_by_wall.get(opening.parent_wall_id, opening.connected_room_ids))})
        for opening in openings
    )
    return model.model_copy(update={"walls": tuple(kept), "rooms": rooms, "openings": openings}), mapping


def _room_overlap(a, b) -> float:
    try:
        first = Polygon(a.boundary_polygon_2d)
        second = Polygon(b.boundary_polygon_2d)
        union = first.union(second).area
        return 0.0 if union <= 0 else first.intersection(second).area / union
    except Exception:
        return 0.0


def _merge_rooms(model: CanonicalWorldModel, threshold: float = 0.9) -> CanonicalWorldModel:
    rooms = list(model.rooms)
    mapping = {room.room_id: room.room_id for room in rooms}
    kept = []
    for room in rooms:
        duplicate = next((existing for existing in kept if _room_overlap(existing, room) >= threshold), None)
        if duplicate is None:
            kept.append(room)
            continue
        mapping[room.room_id] = duplicate.room_id
    if len(kept) == len(rooms):
        return model

    rooms = [
        room.model_copy(update={"wall_ids": tuple(dict.fromkeys(wall_id for wall_id in room.wall_ids)), "opening_ids": tuple(dict.fromkeys(opening_id for opening_id in room.opening_ids))})
        for room in kept
    ]
    walls = tuple(
        wall.model_copy(update={"room_ids": tuple(dict.fromkeys(mapping.get(room_id, room_id) for room_id in wall.room_ids))})
        for wall in model.walls
    )
    openings = tuple(
        opening.model_copy(update={"connected_room_ids": tuple(dict.fromkeys(mapping.get(room_id, room_id) for room_id in opening.connected_room_ids))})
        for opening in model.openings
    )
    room_by_id = {room.room_id: room for room in rooms}
    wall_by_id = {wall.wall_id: wall for wall in walls}
    opening_by_id = {opening.opening_id: opening for opening in openings}
    rooms = [
        room.model_copy(
            update={
                "wall_ids": tuple(wall_id for wall_id in wall_by_id if room.room_id in wall_by_id[wall_id].room_ids),
                "opening_ids": tuple(opening_id for opening_id in opening_by_id if room.room_id in opening_by_id[opening_id].connected_room_ids),
            }
        )
        for room in rooms
    ]
    return model.model_copy(update={"rooms": tuple(rooms), "walls": walls, "openings": openings})


def build_property_topology(model: CanonicalWorldModel) -> tuple[SpatialRelationship, ...]:
    """Build explicit room adjacency and opening connectivity from canonical geometry."""
    edges = []
    seen = set()
    def add(source, target, relation, confidence):
        key = (source, target, relation)
        if key not in seen:
            seen.add(key)
            edges.append(SpatialRelationship(source_id=source, target_id=target, relationship_type=relation, confidence=confidence, provenance=None))

    for room in model.rooms:
        for wall_id in room.wall_ids:
            add(room.room_id, wall_id, RelationshipType.BOUNDED_BY, 1.0)
    for wall in model.walls:
        for opening_id in [opening.opening_id for opening in model.openings if opening.parent_wall_id == wall.wall_id]:
            add(wall.wall_id, opening_id, RelationshipType.HOSTS, 1.0)

    for opening in model.openings:
        rooms = tuple(dict.fromkeys(opening.connected_room_ids))
        if len(rooms) >= 2:
            for index, source in enumerate(rooms):
                for target in rooms[index + 1:]:
                    add(source, target, RelationshipType.CONNECTED_VIA_OPENING, 0.9)
                    add(target, source, RelationshipType.CONNECTED_VIA_OPENING, 0.9)
    for wall in model.walls:
        rooms = tuple(dict.fromkeys(wall.room_ids))
        if len(rooms) >= 2:
            for index, source in enumerate(rooms):
                for target in rooms[index + 1:]:
                    add(source, target, RelationshipType.ADJACENT_TO, 0.75)
                    add(target, source, RelationshipType.ADJACENT_TO, 0.75)
    return tuple(edges)


def optimize_property(model: CanonicalWorldModel, *, wall_tolerance: float = DEFAULT_TOLERANCE, room_overlap_threshold: float = 0.9) -> CanonicalWorldModel:
    """Apply conservative global duplicate suppression and rebuild property topology."""
    optimized, _ = _merge_walls(model, wall_tolerance)
    optimized = _merge_rooms(optimized, room_overlap_threshold)
    optimized = optimized.model_copy(update={"relationships": build_property_topology(optimized)})
    return optimized.model_copy(update={"provenance": optimized.provenance.model_copy(update={"generating_pipeline_stage": "global_property_optimization"}) if optimized.provenance else None})

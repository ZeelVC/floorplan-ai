from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from floorplan_ai.canonical.schema import (
    CanonicalWorldModel,
    CoordinateFrame,
    Opening,
    OpeningType,
    Plane,
    RelationshipType,
    Room,
    Wall,
)
from floorplan_ai.stitching.optimization import build_property_topology, optimize_property


def _model():
    frame = CoordinateFrame(frame_type="world")
    plane = Plane(frame_id=frame.frame_id, normal_vector=(0.0, 0.0, 1.0), distance_offset=0.0)
    room_a = Room(
        boundary_polygon_2d=((0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0), (0.0, 0.0)),
        wall_ids=(),
    )
    room_b = Room(
        boundary_polygon_2d=((0.02, 0.01), (4.01, 0.0), (4.0, 3.0), (0.0, 3.0), (0.02, 0.01)),
        wall_ids=(),
    )
    wall_a = Wall(
        supporting_plane_id=plane.plane_id,
        start_point_2d=(0.0, 0.0),
        end_point_2d=(4.0, 0.0),
        room_ids=(room_a.room_id,),
    )
    wall_b = Wall(
        supporting_plane_id=plane.plane_id,
        start_point_2d=(0.0, 0.0),
        end_point_2d=(4.0, 0.0),
        room_ids=(room_b.room_id,),
    )
    opening = Opening(
        parent_wall_id=wall_b.wall_id,
        opening_type=OpeningType.DOOR,
        offset_along_wall=1.0,
        width=0.9,
        height=2.0,
        connected_room_ids=(room_b.room_id,),
    )
    rooms = (
        room_a.model_copy(update={"wall_ids": (wall_a.wall_id,)}),
        room_b.model_copy(update={"wall_ids": (wall_b.wall_id,), "opening_ids": (opening.opening_id,)}),
    )
    return CanonicalWorldModel(frames=(frame,), planes=(plane,), rooms=rooms, walls=(wall_a, wall_b), openings=(opening,))


def test_global_optimization_removes_duplicate_walls_and_rooms():
    optimized = optimize_property(_model())
    assert len(optimized.walls) == 1
    assert len(optimized.rooms) == 1
    assert len(optimized.openings) == 1
    assert optimized.openings[0].parent_wall_id == optimized.walls[0].wall_id
    assert optimized.openings[0].connected_room_ids == (optimized.rooms[0].room_id,)


def test_property_topology_contains_room_adjacency_and_opening_links():
    model = _model()
    room_ids = {room.room_id for room in model.rooms}
    edges = build_property_topology(model)
    assert any(edge.relationship_type is RelationshipType.BOUNDED_BY for edge in edges)
    assert any(edge.relationship_type is RelationshipType.HOSTS for edge in edges)
    assert not any(
        edge.relationship_type is RelationshipType.CONNECTED_VIA_OPENING
        for edge in edges
        if edge.source_id in room_ids
    )

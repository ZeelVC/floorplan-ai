from __future__ import annotations

from math import cos, sin, pi

from floorplan_ai.canonical.schema import CoordinateFrame, Plane, Wall, CanonicalWorldModel
from floorplan_ai.stitching import reconcile_models


def _transform(p, angle, tx, ty):
    c, s = cos(angle), sin(angle)
    x, y = p
    return (c * x - s * y + tx, s * x + c * y + ty)


def _model(offset=(0.0, 0.0), angle=0.0):
    tx, ty = offset
    frame = CoordinateFrame()
    plane = Plane(frame_id=frame.frame_id, normal_vector=(0.0, 0.0, 1.0), distance_offset=0.0)
    base = [((0.0, 0.0), (2.0, 0.0)), ((0.0, 0.0), (0.0, 3.0)), ((2.0, 0.0), (2.0, 4.0))]
    walls = tuple(
        Wall(
            supporting_plane_id=plane.plane_id,
            start_point_2d=_transform(a, angle, tx, ty),
            end_point_2d=_transform(b, angle, tx, ty),
        )
        for a, b in base
    )
    return CanonicalWorldModel(frames=(frame,), planes=(plane,), walls=walls)


def test_reconcile_models_registers_unique_wall_landmarks():
    reference = _model()
    incoming = _model(offset=(7.0, -4.0), angle=pi / 2)

    merged = reconcile_models((reference, incoming))

    assert len(merged.walls) == 6
    assert len(merged.planes) == 2
    assert max(abs(w.start_point_2d[0]) for w in merged.walls) < 2.01
    assert max(abs(w.start_point_2d[1]) for w in merged.walls) < 4.01


def test_reconcile_models_keeps_ambiguous_geometry_separate():
    reference = _model()
    incoming = CanonicalWorldModel(
        frames=(CoordinateFrame(),),
        planes=(),
        walls=(),
    )

    merged = reconcile_models((reference, incoming))

    assert len(merged.walls) == 3
    assert len(merged.frames) == 2

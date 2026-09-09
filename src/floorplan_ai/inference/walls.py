from __future__ import annotations

from math import atan2, degrees

from floorplan_ai.canonical.schema import Wall, Uncertainty


def walls_from_planes(planes, floor_height: float | None = None, ceiling_height: float | None = None, min_length=.3):
    out = []
    for p in planes:
        if abs(p.normal_vector[2]) > .2 or len(p.boundary_polygon_3d) < 2:
            continue
        pts = p.boundary_polygon_3d
        nx, ny, _ = p.normal_vector
        dx, dy = -ny, nx
        values = [x * dx + y * dy for x, y, _ in pts]
        lo, hi = min(values), max(values)
        if hi - lo < min_length:
            continue
        cx = sum(x for x, _, _ in pts) / len(pts)
        cy = sum(y for _, y, _ in pts) / len(pts)
        # Project the centroid onto the supporting plane normal. Using only
        # the tangent component collapses Y-normal walls onto y=0.
        base = cx * nx + cy * ny
        sx, sy = dx * lo + nx * base, dy * lo + ny * base
        ex, ey = dx * hi + nx * base, dy * hi + ny * base
        angle = abs((degrees(atan2(dy, dx)) % 90))
        deviation = min(angle, 90 - angle)
        height = (ceiling_height - floor_height) if floor_height is not None and ceiling_height is not None else None
        out.append(
            Wall(
                supporting_plane_id=p.plane_id,
                start_point_2d=(sx, sy),
                end_point_2d=(ex, ey),
                height=height,
                manhattan_deviation=deviation,
                uncertainty=Uncertainty(distribution_type='plane_residual', confidence_bounds=(0., p.rmse or .05)),
                provenance=p.provenance,
            )
        )
    return tuple(sorted(out, key=lambda w: (
        round(w.start_point_2d[0], 6), round(w.start_point_2d[1], 6),
        round(w.end_point_2d[0], 6), round(w.end_point_2d[1], 6),
    )))

"""Conservative stitching of independently reconstructed canonical models."""
from __future__ import annotations

import numpy as np

from floorplan_ai.canonical.schema import CanonicalWorldModel, Plane, Provenance
from .registration import register_points


def _wall_signature(wall):
    return round(wall.length, 2)


def _registration_points(source, target, tolerance=0.08):
    """Build conservative wall-midpoint correspondences from unique wall lengths."""
    sm = {}
    tm = {}
    for wall in source.walls:
        sm.setdefault(_wall_signature(wall), []).append(wall)
    for wall in target.walls:
        tm.setdefault(_wall_signature(wall), []).append(wall)

    source_points, target_points = [], []
    for length in sorted(set(sm) & set(tm)):
        if len(sm[length]) != 1 or len(tm[length]) != 1:
            continue
        a, b = sm[length][0], tm[length][0]
        source_points.append(
            (
                (a.start_point_2d[0] + a.end_point_2d[0]) / 2,
                (a.start_point_2d[1] + a.end_point_2d[1]) / 2,
                0.0,
            )
        )
        target_points.append(
            (
                (b.start_point_2d[0] + b.end_point_2d[0]) / 2,
                (b.start_point_2d[1] + b.end_point_2d[1]) / 2,
                0.0,
            )
        )

    if len(source_points) < 3:
        return None
    # Three non-collinear architectural landmarks are required. Midpoints that are
    # effectively collinear cannot constrain a stable 2-D rigid transform.
    centered = np.asarray(source_points, dtype=float)[:, :2]
    if np.linalg.matrix_rank(centered - centered.mean(axis=0)) < 2:
        return None

    result = register_points(source_points, target_points, allow_scale=False, max_rmse=tolerance)
    return result if result.accepted else None


def _transform_point(point, matrix):
    x, y = point
    return (
        float(matrix[0][0] * x + matrix[0][1] * y + matrix[0][3]),
        float(matrix[1][0] * x + matrix[1][1] * y + matrix[1][3]),
    )


def _transform_plane(plane, matrix):
    n = np.asarray(plane.normal_vector, dtype=float)
    r = np.asarray(matrix, dtype=float)[:3, :3]
    t = np.asarray(matrix, dtype=float)[:3, 3]
    transformed_normal = r @ n
    transformed_offset = float(plane.distance_offset - transformed_normal.dot(t))
    boundary = tuple(
        tuple(float(v) for v in (r @ np.asarray(point) + t))
        for point in plane.boundary_polygon_3d
    )
    return plane.model_copy(
        update={
            "normal_vector": tuple(float(v) for v in transformed_normal),
            "distance_offset": transformed_offset,
            "boundary_polygon_3d": boundary,
        }
    )


def _transform_model_2d(model, matrix):
    """Transform architectural geometry and the planes that support it."""
    rooms = tuple(
        room.model_copy(
            update={
                "boundary_polygon_2d": tuple(
                    _transform_point(p, matrix) for p in room.boundary_polygon_2d
                )
            }
        )
        for room in model.rooms
    )
    walls = tuple(
        wall.model_copy(
            update={
                "start_point_2d": _transform_point(wall.start_point_2d, matrix),
                "end_point_2d": _transform_point(wall.end_point_2d, matrix),
            }
        )
        for wall in model.walls
    )
    planes = tuple(_transform_plane(plane, matrix) for plane in model.planes)
    return model.model_copy(update={"rooms": rooms, "walls": walls, "planes": planes})


def reconcile_models(models):
    """Merge local models and align a model only when conservative geometry evidence exists.

    Models without at least three uniquely identifiable wall-length correspondences remain
    separate coordinate components. This prevents arbitrary placement from being presented
    as a stitched floorplan.
    """
    models = tuple(models)
    if not models:
        return CanonicalWorldModel()
    if len(models) == 1:
        return models[0]

    accepted = [models[0]]
    for incoming in models[1:]:
        reference = accepted[0]
        result = _registration_points(incoming, reference)
        if result is not None:
            incoming = _transform_model_2d(incoming, result.matrix)
        accepted.append(incoming)

    fields = (
        "frames",
        "captures",
        "cameras",
        "poses",
        "observations",
        "geometries",
        "planes",
        "rooms",
        "walls",
        "openings",
        "relationships",
        "scale_estimates",
    )
    payload = {
        field: tuple(item for model in accepted for item in getattr(model, field))
        for field in fields
    }
    return CanonicalWorldModel(
        **payload,
        provenance=Provenance(generating_pipeline_stage="property_stitching"),
    )


def reconcile(model):
    """Backward-compatible single-model entry point."""
    return model

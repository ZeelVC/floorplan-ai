"""Geometry-only opening inference on locally parameterized wall support."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from floorplan_ai.canonical.schema import Opening, OpeningType, Provenance, Uncertainty, Wall


@dataclass(frozen=True)
class OpeningInferenceConfig:
    """Conservative support-grid thresholds, in metres unless stated otherwise."""

    longitudinal_bin_size: float = 0.05
    vertical_bin_size: float = 0.05
    wall_tolerance: float = 0.12
    min_width: float = 0.55
    min_height: float = 0.45
    min_support_per_cell: int = 1
    edge_support_bins: int = 2


def infer_openings(
    points: Iterable[Iterable[float]],
    walls: Iterable[Wall],
    *,
    floor_height: float,
    ceiling_height: float,
    config: OpeningInferenceConfig | None = None,
) -> tuple[Opening, ...]:
    """Infer persistent, wall-local occupancy gaps from a reconstructed cloud.

    Points are assumed to be in the canonical z-up frame. A candidate must be
    bounded by observed wall support on both longitudinal sides, which avoids
    interpreting an unobserved wall end as an opening.
    """
    config = config or OpeningInferenceConfig()
    if ceiling_height <= floor_height:
        raise ValueError("ceiling_height must be above floor_height")
    cloud = np.asarray(tuple(points), dtype=float)
    if cloud.size == 0:
        return ()
    if cloud.ndim != 2 or cloud.shape[1] != 3:
        raise ValueError("points must be an Nx3 canonical point cloud")
    openings: list[Opening] = []
    for wall in walls:
        openings.extend(_openings_for_wall(cloud, wall, floor_height, ceiling_height, config))
    return tuple(openings)


def _openings_for_wall(cloud: np.ndarray, wall: Wall, floor: float, ceiling: float, config: OpeningInferenceConfig) -> list[Opening]:
    start, end = np.asarray(wall.start_point_2d), np.asarray(wall.end_point_2d)
    direction = end - start
    length = float(np.linalg.norm(direction))
    if length <= 1e-9:
        return []
    tangent = direction / length
    relative = cloud[:, :2] - start
    longitudinal = relative @ tangent
    lateral = relative[:, 0] * -tangent[1] + relative[:, 1] * tangent[0]
    keep = (
        (longitudinal >= 0)
        & (longitudinal <= length)
        & (np.abs(lateral) <= config.wall_tolerance)
        & (cloud[:, 2] >= floor)
        & (cloud[:, 2] <= ceiling)
    )
    support = cloud[keep]
    if support.size == 0:
        return []
    n_long = max(1, int(np.ceil(length / config.longitudinal_bin_size)))
    n_vertical = max(1, int(np.ceil((ceiling - floor) / config.vertical_bin_size)))
    grid = np.zeros((n_long, n_vertical), dtype=int)
    u = np.clip(((longitudinal[keep] / length) * n_long).astype(int), 0, n_long - 1)
    v = np.clip((((support[:, 2] - floor) / (ceiling - floor)) * n_vertical).astype(int), 0, n_vertical - 1)
    np.add.at(grid, (u, v), 1)
    occupied = grid >= config.min_support_per_cell
    candidates: list[Opening] = []
    for lo in range(n_long):
        for hi in range(lo + 1, n_long + 1):
            width = (hi - lo) * length / n_long
            if width < config.min_width:
                continue
            if lo < config.edge_support_bins or hi > n_long - config.edge_support_bins:
                continue
            left = occupied[max(0, lo - config.edge_support_bins):lo]
            right = occupied[hi:min(n_long, hi + config.edge_support_bins)]
            if not left.any() or not right.any():
                continue
            empty = ~occupied[lo:hi].any(axis=0)
            for z0, z1 in _runs(empty):
                height = (z1 - z0) * (ceiling - floor) / n_vertical
                if height < config.min_height:
                    continue
                sill = floor + z0 * (ceiling - floor) / n_vertical
                if any(abs(candidate.offset_along_wall - lo * length / n_long) < config.longitudinal_bin_size for candidate in candidates):
                    continue
                opening_type = _classify(width, height, sill - floor)
                candidates.append(
                    Opening(
                        parent_wall_id=wall.wall_id,
                        opening_type=opening_type,
                        offset_along_wall=lo * length / n_long,
                        width=width,
                        height=height,
                        sill_height=max(0.0, sill - floor),
                        connected_room_ids=wall.room_ids,
                        uncertainty=Uncertainty(distribution_type="occupancy_grid", confidence_bounds=(0.0, max(config.longitudinal_bin_size, config.vertical_bin_size))),
                        provenance=Provenance(generating_pipeline_stage="opening_inference"),
                    )
                )
                break
    selected: list[Opening] = []
    for candidate in sorted(candidates, key=lambda item: (-item.width, item.offset_along_wall)):
        if not any(_overlap(candidate, existing) for existing in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda item: item.offset_along_wall)


def _runs(values: np.ndarray) -> list[tuple[int, int]]:
    starts = np.flatnonzero(np.diff(np.r_[False, values, False].astype(int)) == 1)
    ends = np.flatnonzero(np.diff(np.r_[False, values, False].astype(int)) == -1)
    return list(zip(starts, ends))


def _classify(width: float, height: float, sill: float) -> OpeningType:
    if sill <= 0.15 and 0.6 <= width <= 1.5 and 1.7 <= height <= 2.5:
        return OpeningType.DOOR
    if sill >= 0.35 and 0.3 <= width <= 3.0 and 0.3 <= height <= 2.0:
        return OpeningType.WINDOW
    if sill <= 0.15:
        return OpeningType.ARCHWAY
    return OpeningType.OTHER


def _overlap(first: Opening, second: Opening) -> bool:
    return first.offset_along_wall < second.offset_along_wall + second.width and second.offset_along_wall < first.offset_along_wall + first.width

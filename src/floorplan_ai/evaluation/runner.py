"""Deterministic, evaluation-only benchmark metrics for canonical floorplans."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from floorplan_ai.canonical.schema import CanonicalWorldModel, MeasurementType


def _polygon_area(points: Iterable[tuple[float, float]]) -> float:
    pts = list(points)
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2.0) if len(pts) >= 3 else 0.0


def _match_by_value(predictions, truths, value_fn):
    remaining = set(range(len(truths)))
    pairs = []
    for prediction in predictions:
        if not remaining:
            break
        index = min(remaining, key=lambda i: abs(value_fn(prediction) - value_fn(truths[i])))
        pairs.append((prediction, truths[index]))
        remaining.remove(index)
    return pairs


def _summary(errors: list[float], threshold: float | None = None) -> dict:
    if not errors:
        return {"matched": 0, "mean_absolute_error": None, "max_absolute_error": None, "pass_rate": None}
    return {"matched": len(errors), "mean_absolute_error": sum(errors) / len(errors), "max_absolute_error": max(errors), "pass_rate": sum(error <= threshold for error in errors) / len(errors) if threshold is not None else None}


def _relative_errors(pairs, value_fn) -> list[float]:
    return [abs(value_fn(pred) - value_fn(gt)) / value_fn(gt) for pred, gt in pairs if value_fn(gt) > 0]


def _metric_measurements(model, metric_type: str):
    return [m for m in model.measurements if str(getattr(m.metric_type, "value", m.metric_type)) == metric_type]


def _measurement_errors(prediction, ground_truth, metric_type: str):
    pred = _metric_measurements(prediction, metric_type)
    gt = _metric_measurements(ground_truth, metric_type)
    pairs = _match_by_value(pred, gt, lambda m: m.nominal_value)
    return [abs(p.nominal_value - g.nominal_value) for p, g in pairs], pairs


def _capture_type(model) -> str:
    types = {capture.capture_type for capture in model.captures}
    return "video" if types == {"video"} else "photo"


def evaluate(prediction: Path, ground_truth: Path, report_out: Path) -> dict:
    """Evaluate prediction against evaluation-only ground truth."""
    p = CanonicalWorldModel.from_json(Path(prediction).read_text())
    g = CanonicalWorldModel.from_json(Path(ground_truth).read_text())

    wall_pairs = _match_by_value(p.walls, g.walls, lambda w: w.length)
    wall_errors = [abs(a.length - b.length) for a, b in wall_pairs]
    wall_relative = _relative_errors(wall_pairs, lambda w: w.length)

    opening_errors, _ = _measurement_errors(p, g, "OPENING_WIDTH")
    if not opening_errors:
        opening_pairs = _match_by_value(p.openings, g.openings, lambda o: o.width)
        opening_errors = [abs(a.width - b.width) for a, b in opening_pairs]

    ceiling_errors, _ = _measurement_errors(p, g, MeasurementType.CEILING_HEIGHT.value)
    footprint_pred = sum(_polygon_area(room.boundary_polygon_2d) for room in p.rooms)
    footprint_gt = sum(_polygon_area(room.boundary_polygon_2d) for room in g.rooms)
    footprint_error = abs(footprint_pred - footprint_gt) if footprint_gt > 0 else None
    footprint_relative = footprint_error / footprint_gt if footprint_error is not None else None

    pred_signatures = sorted((len(room.wall_ids), len(room.opening_ids)) for room in p.rooms)
    gt_signatures = sorted((len(room.wall_ids), len(room.opening_ids)) for room in g.rooms)
    capture_type = _capture_type(p)
    wall_threshold = 0.03 if capture_type == "video" else 0.08

    report = {
        "schema_version": 1,
        "capture_type": capture_type,
        "prediction_rooms": len(p.rooms), "ground_truth_rooms": len(g.rooms),
        "prediction_walls": len(p.walls), "ground_truth_walls": len(g.walls),
        "prediction_openings": len(p.openings), "ground_truth_openings": len(g.openings),
        "wall_length": _summary(wall_errors, wall_threshold),
        "wall_length_relative": {"matched": len(wall_relative), "mean_relative_error": sum(wall_relative) / len(wall_relative) if wall_relative else None, "pass_rate": sum(error <= wall_threshold for error in wall_relative) / len(wall_relative) if wall_relative else None},
        "opening_width": _summary(opening_errors, 0.02),
        "ceiling_height": _summary(ceiling_errors, 0.015),
        "footprint": {"prediction_area_m2": footprint_pred, "ground_truth_area_m2": footprint_gt, "absolute_error_m2": footprint_error, "relative_error": footprint_relative, "passes_8_percent": footprint_relative <= 0.08 if footprint_relative is not None else None},
        "room_topology": {"room_count_match": len(p.rooms) == len(g.rooms), "adjacency_signature_match": pred_signatures == gt_signatures, "prediction_relationships": len(p.relationships), "ground_truth_relationships": len(g.relationships)},
        "confidence": {"measurements_with_95_interval": sum(m.interval_95 is not None for m in p.measurements), "measurements_total": len(p.measurements)},
    }
    report_out = Path(report_out)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, sort_keys=True))
    return report

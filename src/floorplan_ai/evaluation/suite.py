"""Multi-capture benchmark aggregation without exposing ground truth to inference."""
from __future__ import annotations

import json
from pathlib import Path

from .runner import evaluate


def evaluate_suite(predictions: list[Path], ground_truths: list[Path], report_out: Path) -> dict:
    if len(predictions) != len(ground_truths):
        raise ValueError("predictions and ground_truths must contain the same number of captures")
    if not predictions:
        raise ValueError("at least one prediction/ground-truth pair is required")

    cases = [evaluate(prediction, truth, Path(report_out).with_name(f".{Path(prediction).stem}.evaluation.json")) for prediction, truth in zip(predictions, ground_truths)]

    def aggregate(metric: str, field: str = "pass_rate"):
        values = [case[metric][field] for case in cases if case[metric][field] is not None]
        return sum(values) / len(values) if values else None

    suite = {
        "schema_version": 1,
        "capture_count": len(cases),
        "cases": cases,
        "aggregate": {
            "wall_length_pass_rate": aggregate("wall_length"),
            "opening_width_pass_rate": aggregate("opening_width"),
            "ceiling_height_pass_rate": aggregate("ceiling_height"),
            "footprint_8_percent_pass_rate": sum(case["footprint"]["passes_8_percent"] is True for case in cases) / len(cases),
            "room_count_match_rate": sum(case["room_topology"]["room_count_match"] for case in cases) / len(cases),
            "adjacency_signature_match_rate": sum(case["room_topology"]["adjacency_signature_match"] for case in cases) / len(cases),
        },
        "benchmark_gates": {
            "photo_wall_length_gate": "<=8% relative error per matched wall",
            "video_wall_length_gate": "<=3% relative error per matched wall",
            "opening_width_gate": "<=0.02 m per matched opening",
            "ceiling_height_gate": "<=0.015 m per matched room",
            "footprint_gate": "<=8% relative area error",
            "repeatability_gate": "<=0.01 m spread across repeated captures (requires repeatability input)",
        },
    }
    report_out = Path(report_out)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(suite, indent=2, sort_keys=True))
    return suite

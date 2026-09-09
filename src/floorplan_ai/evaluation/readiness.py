"""Preflight validation for completed unseen-property reconstruction outputs."""
from __future__ import annotations

import json
from pathlib import Path

from floorplan_ai.canonical.schema import CanonicalWorldModel


REQUIRED_ARTIFACTS = ("floorplan.json", "floorplan.svg", "floorplan.dxf", "diagnostics.json", "provenance.json")


def validate_output(output_dir: Path) -> dict:
    """Validate a completed run without requiring benchmark ground truth."""
    root = Path(output_dir)
    checks: dict[str, bool] = {
        "canonical_model_valid": False,
        "has_rooms": False,
        "has_walls": False,
        "has_measurements": False,
        "all_measurements_have_95_intervals": False,
        "supported_capture_type": False,
        "diagnostics_valid": False,
        "provenance_valid": False,
    }
    errors: list[str] = []

    for name in REQUIRED_ARTIFACTS:
        present = (root / name).is_file() and (root / name).stat().st_size > 0
        checks[f"artifact:{name}"] = present
        if not present:
            errors.append(f"missing or empty artifact: {name}")

    model = None
    floorplan = root / "floorplan.json"
    if floorplan.is_file():
        try:
            model = CanonicalWorldModel.from_json(floorplan.read_text())
            checks["canonical_model_valid"] = True
        except Exception as exc:
            errors.append(f"invalid floorplan.json: {exc}")

    if model is not None:
        checks["has_rooms"] = bool(model.rooms)
        checks["has_walls"] = bool(model.walls)
        if not model.rooms:
            errors.append("canonical model contains no rooms")
        if not model.walls:
            errors.append("canonical model contains no walls")

        missing_intervals = [m.measurement_id for m in model.measurements if m.interval_95 is None]
        checks["all_measurements_have_95_intervals"] = bool(model.measurements) and not missing_intervals
        checks["has_measurements"] = bool(model.measurements) and not missing_intervals
        if not model.measurements:
            errors.append("canonical model contains no measurements")
        if missing_intervals:
            errors.append(f"measurements without 95% intervals: {len(missing_intervals)}")

        capture_types = {capture.capture_type for capture in model.captures}
        checks["supported_capture_type"] = bool(capture_types) and capture_types <= {"photo", "video"}
        if not checks["supported_capture_type"]:
            errors.append("run contains unsupported or missing capture modality")

    diagnostics_path = root / "diagnostics.json"
    if diagnostics_path.is_file():
        try:
            diagnostics = json.loads(diagnostics_path.read_text())
            checks["diagnostics_valid"] = isinstance(diagnostics, dict)
            if not checks["diagnostics_valid"]:
                errors.append("diagnostics.json is not a JSON object")
        except json.JSONDecodeError as exc:
            errors.append(f"invalid diagnostics.json: {exc}")

    provenance_path = root / "provenance.json"
    if provenance_path.is_file():
        try:
            json.loads(provenance_path.read_text())
            checks["provenance_valid"] = True
        except json.JSONDecodeError as exc:
            errors.append(f"invalid provenance.json: {exc}")

    ready = not errors
    return {"schema_version": 1, "ready": ready, "checks": checks, "errors": errors}

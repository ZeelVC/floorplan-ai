"""JSON-manifest loading and customer-actionable capture validation."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import CaptureDataset, CaptureInput, EvaluationReference, Manifest, Property, Trial

MANIFEST_FILENAME = "floorplan-dataset.json"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi"}


class DatasetValidationError(ValueError):
    """An input-contract violation written for a customer to correct."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("Dataset validation failed:\n" + "\n".join(f"- {problem}" for problem in problems))
        self.problems = tuple(problems)


def _model_error(error: ValidationError) -> DatasetValidationError:
    problems = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"])
        if item["loc"] and item["loc"][-1] == "source_type":
            problems.append(f"Unsupported source_type {item.get('input')!r} at manifest field '{location}'. Expected one of: photo, video.")
            continue
        problems.append(f"manifest field '{location}': {item['msg']}.")
    return DatasetValidationError(problems)


def _ordered(captures: tuple[CaptureInput, ...]) -> tuple[CaptureInput, ...]:
    # Explicit sequence wins; unsequenced captures use their ID as the documented fallback.
    return tuple(sorted(captures, key=lambda capture: (capture.sequence is None, capture.sequence if capture.sequence is not None else 0, capture.capture_id)))


def _read_manifest(root: Path) -> Manifest:
    manifest_path = root / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise DatasetValidationError([f"manifest '{MANIFEST_FILENAME}' does not exist in '{root}'. Add the required manifest file."])
    try:
        raw: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise DatasetValidationError([f"manifest '{MANIFEST_FILENAME}' is not valid JSON (line {error.lineno}, column {error.colno}). Correct its syntax."]) from error
    except OSError as error:
        raise DatasetValidationError([f"manifest '{MANIFEST_FILENAME}' cannot be read: {error.strerror or error}. Check file permissions."]) from error
    try:
        return Manifest.model_validate(raw)
    except ValidationError as error:
        raise _model_error(error) from error


def _validate_and_resolve(root: Path, manifest: Manifest) -> CaptureDataset:
    problems: list[str] = []
    property_ids: set[str] = set()
    capture_ids: set[str] = set()
    properties: list[Property] = []
    for property_ in manifest.properties:
        if property_.property_id in property_ids:
            problems.append(f"duplicate property_id '{property_.property_id}'. Use a unique property_id.")
        property_ids.add(property_.property_id)
        room_ids = [room.room_id for room in property_.rooms]
        if len(room_ids) != len(set(room_ids)):
            problems.append(f"property '{property_.property_id}' contains duplicate room_id values. Use unique room IDs.")
        trial_ids: set[str] = set()
        trials: list[Trial] = []
        for trial in property_.trials:
            if trial.trial_id in trial_ids:
                problems.append(f"duplicate trial_id '{trial.trial_id}' within property '{property_.property_id}'. Use a unique trial_id.")
            trial_ids.add(trial.trial_id)
            local_ids: set[str] = set()
            resolved: list[CaptureInput] = []
            for capture in trial.captures:
                if capture.capture_id in local_ids:
                    problems.append(f"duplicate capture_id '{capture.capture_id}' within trial '{trial.trial_id}'. Use a unique capture_id.")
                if capture.capture_id in capture_ids:
                    problems.append(f"duplicate capture_id '{capture.capture_id}' in dataset '{manifest.dataset_id}'. Capture IDs must be unique across the dataset.")
                local_ids.add(capture.capture_id)
                capture_ids.add(capture.capture_id)
                if capture.room_id is not None and capture.room_id not in room_ids:
                    problems.append(f"capture '{capture.capture_id}' references unknown room_id '{capture.room_id}' in property '{property_.property_id}'. Add that room or remove room_id.")
                path = root / capture.file
                expected_extensions = PHOTO_EXTENSIONS if capture.source_type == "photo" else VIDEO_EXTENSIONS
                if path.suffix.lower() not in expected_extensions:
                    expected = ", ".join(sorted(expected_extensions))
                    problems.append(f"capture '{capture.capture_id}' declares source_type '{capture.source_type}' but file '{capture.file}' has an incompatible extension. Expected one of: {expected}.")
                if not path.is_file():
                    problems.append(f"capture '{capture.capture_id}' references '{capture.file}', but the file does not exist. Add the original media file or correct 'file'.")
                elif not os.access(path, os.R_OK):
                    problems.append(f"capture '{capture.capture_id}' references '{capture.file}', but it is not readable. Check file permissions.")
                else:
                    try:
                        with path.open("rb") as media:
                            media.read(1)
                    except OSError as error:
                        problems.append(f"capture '{capture.capture_id}' references '{capture.file}', but it cannot be read: {error.strerror or error}. Check the file.")
                resolved.append(capture.model_copy(update={"resolved_file": path}))
            trials.append(trial.model_copy(update={"captures": _ordered(tuple(resolved))}))
        properties.append(property_.model_copy(update={"trials": tuple(sorted(trials, key=lambda item: item.trial_id))}))
    if problems:
        raise DatasetValidationError(problems)
    return CaptureDataset(dataset_id=manifest.dataset_id, root=root, properties=tuple(sorted(properties, key=lambda item: item.property_id)))


def load_dataset(dataset_root: str | Path) -> CaptureDataset:
    """Load inference captures only; ground truth is deliberately not returned."""
    # Use an absolute lexical path rather than Path.resolve().  On macOS, resolve()
    # canonicalizes /var/folders through the /private symlink, which makes the
    # returned media paths differ from the caller's Path even though they refer
    # to the same file.  Dataset paths are contracts, so preserve their spelling.
    root = Path(dataset_root).absolute()
    return _validate_and_resolve(root, _read_manifest(root))


def load_evaluation_reference(dataset_root: str | Path) -> EvaluationReference | None:
    """Return the separately declared evaluation reference without loading inference captures."""
    return _read_manifest(Path(dataset_root).absolute()).evaluation

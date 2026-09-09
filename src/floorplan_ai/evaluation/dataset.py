"""Evaluation-only access to a dataset's declared ground-truth artifact."""

import os
from pathlib import Path

from floorplan_ai.dataset.loader import DatasetValidationError, load_evaluation_reference


def ground_truth_path(dataset_root: str | Path) -> Path | None:
    """Resolve and validate an opt-in evaluation artifact; never expose it to inference."""
    root = Path(dataset_root).resolve()
    reference = load_evaluation_reference(root)
    if reference is None:
        return None

    path = root / reference.ground_truth_file
    if not path.is_file():
        raise DatasetValidationError([
            f"ground-truth reference '{reference.ground_truth_file}' does not exist as a regular file. "
            "Add the evaluation artifact or correct 'evaluation.ground_truth_file'."
        ])
    if not os.access(path, os.R_OK):
        raise DatasetValidationError([
            f"ground-truth reference '{reference.ground_truth_file}' is not readable. "
            "Check the evaluation artifact's file permissions."
        ])
    try:
        with path.open("rb") as ground_truth:
            ground_truth.read(1)
    except OSError as error:
        raise DatasetValidationError([
            f"ground-truth reference '{reference.ground_truth_file}' cannot be read: {error.strerror or error}. "
            "Check the evaluation artifact's file permissions."
        ]) from error
    return path

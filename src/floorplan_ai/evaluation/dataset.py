"""Evaluation-only access to a dataset's declared ground-truth artifact."""

from pathlib import Path

from floorplan_ai.dataset.loader import load_evaluation_reference


def ground_truth_path(dataset_root: str | Path) -> Path | None:
    """Resolve an opt-in ground-truth reference for evaluation; never for inference."""
    root = Path(dataset_root).resolve()
    reference = load_evaluation_reference(root)
    return None if reference is None else root / reference.ground_truth_file

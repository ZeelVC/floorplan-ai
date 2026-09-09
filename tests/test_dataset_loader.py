"""Contract tests for deterministic customer capture-dataset ingestion."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from floorplan_ai.dataset import DatasetValidationError, load_dataset
from floorplan_ai.evaluation import ground_truth_path


class DatasetLoaderTests(unittest.TestCase):
    def write_dataset(self, manifest: dict, files: tuple[str, ...] = ()) -> Path:
        directory = Path(tempfile.mkdtemp())
        (directory / "floorplan-dataset.json").write_text(json.dumps(manifest), encoding="utf-8")
        for name in files:
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"media")
        return directory

    def manifest(self, captures: list[dict], *, properties: list[dict] | None = None) -> dict:
        return {"schema_version": "1.0", "dataset_id": "customer-data", "properties": properties or [{"property_id": "home", "rooms": [{"room_id": "kitchen"}], "trials": [{"trial_id": "session", "captures": captures}]}]}

    def test_valid_photo_video_metadata_orientations_and_determinism(self) -> None:
        captures = [
            {"capture_id": "video", "source_type": "video", "file": "walk.mp4", "orientation": {"value": "unknown", "source": "derived"}, "metadata": {"frame_rate": 30}},
            {"capture_id": "vertical", "source_type": "photo", "file": "v.jpg", "room_id": "kitchen", "sequence": 2, "orientation": {"value": "vertical"}},
            {"capture_id": "horizontal", "source_type": "photo", "file": "h.jpg", "sequence": 1, "orientation": {"value": "horizontal"}},
        ]
        root = self.write_dataset(self.manifest(captures), ("walk.mp4", "v.jpg", "h.jpg"))
        first, second = load_dataset(root), load_dataset(root)
        self.assertEqual([item.capture_id for item in first.captures], ["horizontal", "vertical", "video"])
        self.assertEqual(first, second)
        self.assertEqual(first.captures[0].resolved_file, root / "h.jpg")

    def test_minimal_photo_only_video_only_and_multiple_properties(self) -> None:
        photo = self.write_dataset(self.manifest([{"capture_id": "photo", "source_type": "photo", "file": "a.jpg"}]), ("a.jpg",))
        video = self.write_dataset(self.manifest([{"capture_id": "video", "source_type": "video", "file": "a.mp4"}]), ("a.mp4",))
        properties = [
            {"property_id": "z", "trials": [{"trial_id": "two", "captures": [{"capture_id": "z-video", "source_type": "video", "file": "z.mp4"}]}]},
            {"property_id": "a", "trials": [{"trial_id": "one", "captures": [{"capture_id": "a-photo", "source_type": "photo", "file": "a.jpg"}]}]},
        ]
        multi = self.write_dataset(self.manifest([], properties=properties), ("z.mp4", "a.jpg"))
        self.assertEqual(len(load_dataset(photo).captures), 1)
        self.assertEqual(len(load_dataset(video).captures), 1)
        self.assertEqual([item.property_id for item in load_dataset(multi).properties], ["a", "z"])

    def test_synthetic_customer_fixture_is_general_photo_video_dataset(self) -> None:
        fixture = ROOT / "tests" / "fixtures" / "customer_dataset"
        dataset = load_dataset(fixture)
        self.assertEqual(dataset.dataset_id, "synthetic-customer")
        self.assertEqual([capture.capture_id for capture in dataset.captures], ["office-photo", "foyer-photo", "walkthrough"])

    def test_valid_ground_truth_is_isolated_from_inference_capture(self) -> None:
        raw = self.manifest([{"capture_id": "p", "source_type": "photo", "file": "p.jpg"}])
        raw["evaluation"] = {"ground_truth_file": "evaluation/truth.xlsx", "format": "xlsx"}
        root = self.write_dataset(raw, ("p.jpg", "evaluation/truth.xlsx"))
        dataset = load_dataset(root)
        self.assertEqual([capture.capture_id for capture in dataset.captures], ["p"])
        self.assertEqual(ground_truth_path(root), root / "evaluation/truth.xlsx")
        self.assertFalse(hasattr(dataset, "evaluation"))

    def test_missing_ground_truth_is_rejected_by_evaluation_api(self) -> None:
        raw = self.manifest([{"capture_id": "p", "source_type": "photo", "file": "p.jpg"}])
        raw["evaluation"] = {"ground_truth_file": "ground_truth/expected.json", "format": "json"}
        root = self.write_dataset(raw, ("p.jpg",))
        with self.assertRaisesRegex(DatasetValidationError, "ground_truth/expected.json.*does not exist"):
            ground_truth_path(root)

    def test_unreadable_ground_truth_is_rejected_by_evaluation_api(self) -> None:
        raw = self.manifest([{"capture_id": "p", "source_type": "photo", "file": "p.jpg"}])
        raw["evaluation"] = {"ground_truth_file": "ground_truth/expected.json", "format": "json"}
        root = self.write_dataset(raw, ("p.jpg", "ground_truth/expected.json"))
        with patch("floorplan_ai.evaluation.dataset.os.access", return_value=False):
            with self.assertRaisesRegex(DatasetValidationError, "ground_truth/expected.json.*not readable"):
                ground_truth_path(root)

    def test_actionable_invalid_datasets(self) -> None:
        missing = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(DatasetValidationError, "manifest.*does not exist"):
            load_dataset(missing)
        malformed = Path(tempfile.mkdtemp())
        (malformed / "floorplan-dataset.json").write_text("{bad", encoding="utf-8")
        with self.assertRaisesRegex(DatasetValidationError, "not valid JSON"):
            load_dataset(malformed)
        cases = [
            ({"schema_version": "2.0", "dataset_id": "x", "properties": []}, (), "schema_version"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "missing.jpg"}]), (), "does not exist"),
            (self.manifest([{"capture_id": "p", "source_type": "image_sequence", "file": "a.jpg"}]), (), "Unsupported source_type"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "wrong.mp4"}]), ("wrong.mp4",), "incompatible extension"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "a.jpg"}, {"capture_id": "p", "source_type": "photo", "file": "b.jpg"}]), ("a.jpg", "b.jpg"), "duplicate capture_id"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "a.jpg", "room_id": "unknown"}]), ("a.jpg",), "unknown room_id"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "a.jpg", "orientation": {"value": "diagonal"}}]), ("a.jpg",), "orientation"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "a.jpg", "sequence": -1}]), ("a.jpg",), "sequence"),
            (self.manifest([{"capture_id": "p", "source_type": "photo", "file": "a.jpg", "metadata": []}]), ("a.jpg",), "metadata"),
        ]
        for manifest, files, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(DatasetValidationError, message):
                    load_dataset(self.write_dataset(manifest, files))

    def test_duplicate_trial_is_rejected(self) -> None:
        properties = [{"property_id": "home", "trials": [
            {"trial_id": "same", "captures": [{"capture_id": "one", "source_type": "photo", "file": "one.jpg"}]},
            {"trial_id": "same", "captures": [{"capture_id": "two", "source_type": "photo", "file": "two.jpg"}]},
        ]}]
        with self.assertRaisesRegex(DatasetValidationError, "duplicate trial_id"):
            load_dataset(self.write_dataset(self.manifest([], properties=properties), ("one.jpg", "two.jpg")))


if __name__ == "__main__":
    unittest.main()

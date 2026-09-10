from __future__ import annotations

from pathlib import Path

from floorplan_ai.pipeline.routing import detect_input, photo_groups
from floorplan_ai.reconstruction.colmap import ColmapBackend


def test_photo_routing_accepts_heic_and_ignores_non_images(tmp_path: Path):
    (tmp_path / ".DS_Store").write_bytes(b"noise")
    (tmp_path / "room.heic").write_bytes(b"placeholder")
    (tmp_path / "room.heif").write_bytes(b"placeholder")
    (tmp_path / "note.txt").write_text("ignore")

    assert detect_input(tmp_path) == "photo"
    groups = photo_groups(tmp_path)
    assert [p.suffix.lower() for p in groups[0].paths] == [".heic", ".heif"]


def test_colmap_stages_only_supported_images(tmp_path: Path):
    images = tmp_path / "capture"
    images.mkdir()
    good = images / "1.jpeg"
    bad = images / ".DS_Store"
    good.write_bytes(b"placeholder")
    bad.write_bytes(b"noise")

    backend = ColmapBackend(executable="missing-colmap")
    staged = backend._stage_images((good, bad), tmp_path / "workspace")

    assert [p.name for p in staged] == ["1.jpeg"]
    assert (tmp_path / "workspace" / "images" / "1.jpeg").is_symlink()
    assert not (tmp_path / "workspace" / "images" / ".DS_Store").exists()

import json
from pathlib import Path

from floorplan_ai.canonical.schema import CanonicalWorldModel, Capture, CoordinateFrame, FrameType, Plane, Room, Wall
from floorplan_ai.evaluation import evaluate


def _model(wall_length: float, room_size: float, capture_type: str = "photo") -> CanonicalWorldModel:
    frame = CoordinateFrame(frame_type=FrameType.WORLD)
    plane = Plane(frame_id=frame.frame_id, normal_vector=(0.0, 0.0, 1.0), distance_offset=0.0)
    wall = Wall(supporting_plane_id=plane.plane_id, start_point_2d=(0.0, 0.0), end_point_2d=(wall_length, 0.0))
    room = Room(boundary_polygon_2d=((0.0, 0.0), (room_size, 0.0), (room_size, room_size), (0.0, room_size), (0.0, 0.0)), wall_ids=(wall.wall_id,))
    return CanonicalWorldModel(frames=(frame,), captures=(Capture(capture_type=capture_type),), planes=(plane,), walls=(wall,), rooms=(room,))


def test_evaluation_matches_entities_without_relying_on_ids(tmp_path: Path):
    prediction = _model(9.5, 4.0)
    ground_truth = _model(10.0, 4.0)
    prediction_path = tmp_path / "prediction.json"
    ground_truth_path = tmp_path / "ground_truth.json"
    report_path = tmp_path / "report.json"
    prediction_path.write_text(prediction.to_json())
    ground_truth_path.write_text(ground_truth.to_json())

    report = evaluate(prediction_path, ground_truth_path, report_path)

    assert report["wall_length"]["matched"] == 1
    assert report["wall_length"]["mean_absolute_error"] == 0.5
    assert report["wall_length"]["pass_rate"] == 0.0
    assert report["footprint"]["passes_8_percent"] is True
    assert json.loads(report_path.read_text())["schema_version"] == 1


def test_video_uses_three_percent_wall_gate():
    report = evaluate_from_models(_model(9.7, 4.0, "video"), _model(10.0, 4.0, "video"))
    assert report["capture_type"] == "video"
    assert report["wall_length"]["pass_rate"] == 0.0


def evaluate_from_models(prediction, ground_truth):
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        p = root / "p.json"
        g = root / "g.json"
        r = root / "r.json"
        p.write_text(prediction.to_json())
        g.write_text(ground_truth.to_json())
        return evaluate(p, g, r)

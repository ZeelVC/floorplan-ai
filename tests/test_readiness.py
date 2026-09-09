import json

from floorplan_ai.evaluation.readiness import REQUIRED_ARTIFACTS, validate_output


def _write_valid_output(path):
    for name in REQUIRED_ARTIFACTS:
        (path / name).write_text('{}')
    (path / 'floorplan.json').write_text(json.dumps({
        'schema_version': 1,
        'coordinate_frame': {'frame_id': 'world', 'transform': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]], 'metric_scale': 1.0},
        'captures': [{'capture_id':'c','capture_type':'photo','source':'x'}],
        'poses': [], 'walls': [], 'rooms': [], 'openings': [], 'planes': [],
        'measurements': [], 'relationships': [], 'uncertainties': [], 'provenance': None,
    }))


def test_readiness_rejects_missing_artifacts(tmp_path):
    report = validate_output(tmp_path)
    assert report['ready'] is False
    assert any('missing or empty artifact' in error for error in report['errors'])


def test_readiness_rejects_invalid_model(tmp_path):
    _write_valid_output(tmp_path)
    (tmp_path / 'floorplan.json').write_text('{not-json')
    report = validate_output(tmp_path)
    assert report['ready'] is False
    assert report['checks']['canonical_model_valid'] is False


def test_readiness_requires_measurement_intervals(tmp_path):
    _write_valid_output(tmp_path)
    report = validate_output(tmp_path)
    assert report['ready'] is False
    assert report['checks']['has_measurements'] is False

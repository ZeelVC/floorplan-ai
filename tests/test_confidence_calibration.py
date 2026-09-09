from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from floorplan_ai.calibration.calibrator import calibrate_measurements
from floorplan_ai.canonical.schema import Measurement, MeasurementType


def _measurement(value: float, sigma: float) -> Measurement:
    return Measurement(
        target_entity_id=uuid4(),
        metric_type=MeasurementType.WALL_LENGTH,
        nominal_value=value,
        standard_deviation=sigma,
        interval_95=(value - 1.96 * sigma, value + 1.96 * sigma),
        unit="m",
    )


def test_calibration_reports_undercoverage_and_widens_intervals():
    measurements = [_measurement(10.0, 0.1), _measurement(10.0, 0.1), _measurement(10.0, 0.1)]
    truth = {
        (measurements[0].target_entity_id, MeasurementType.WALL_LENGTH.value): 10.5,
        (measurements[1].target_entity_id, MeasurementType.WALL_LENGTH.value): 10.4,
        (measurements[2].target_entity_id, MeasurementType.WALL_LENGTH.value): 10.3,
    }
    result = calibrate_measurements(measurements, truth)
    assert result.sample_count == 3
    assert result.empirical_coverage == 0.0
    assert result.scale_factor > 1.0
    assert result.calibrated_coverage == 1.0


def test_calibration_does_not_shrink_uncertainty_when_data_is_already_well_calibrated():
    measurement = _measurement(10.0, 0.2)
    truth = {(measurement.target_entity_id, MeasurementType.WALL_LENGTH.value): 10.1}
    result = calibrate_measurements([measurement], truth)
    assert result.empirical_coverage == 1.0
    assert result.scale_factor == 1.0
    assert result.calibrated_coverage == 1.0


def test_calibration_ignores_unmatched_ground_truth_and_missing_sigma():
    measurement = Measurement(
        target_entity_id=uuid4(),
        metric_type=MeasurementType.WALL_LENGTH,
        nominal_value=4.0,
        unit="m",
    )
    result = calibrate_measurements([measurement], {})
    assert result.sample_count == 0
    assert result.scale_factor == 1.0

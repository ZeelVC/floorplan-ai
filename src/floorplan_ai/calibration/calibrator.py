from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from typing import Mapping, Sequence

from floorplan_ai.canonical.schema import Measurement


@dataclass(frozen=True)
class CalibrationResult:
    """Empirical calibration diagnostics for measurement intervals."""

    sample_count: int
    target_coverage: float
    empirical_coverage: float
    calibrated_coverage: float
    scale_factor: float
    normalized_error_quantile: float

    @property
    def calibrated_standard_deviation_multiplier(self) -> float:
        return self.scale_factor


def _validate_target(target_coverage: float) -> None:
    if not 0.0 < target_coverage < 1.0:
        raise ValueError("target_coverage must be between 0 and 1")


def _metric_key(measurement: Measurement) -> str:
    metric = measurement.metric_type
    return metric.value if hasattr(metric, "value") else str(metric)


def _pairs(
    predictions: Sequence[Measurement],
    ground_truth: Mapping[tuple[object, str], float],
) -> list[tuple[Measurement, float]]:
    pairs: list[tuple[Measurement, float]] = []
    for measurement in predictions:
        key = (measurement.target_entity_id, _metric_key(measurement))
        if key not in ground_truth:
            continue
        truth = float(ground_truth[key])
        if not isfinite(truth) or truth <= 0.0:
            raise ValueError("ground-truth measurements must be finite and positive")
        if measurement.standard_deviation is None or measurement.standard_deviation <= 0.0:
            continue
        pairs.append((measurement, truth))
    return pairs


def _finite_sample_quantile(values: Sequence[float], probability: float) -> float:
    """Return a conservative order-statistic quantile for finite samples.

    Calibration must not produce an interval that fails to cover the empirical
    target merely because interpolation between sparse observations yields a
    value below the largest required residual. The ceiling order statistic is
    therefore used: for three samples at 95%, the maximum residual is required.
    """
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, ceil(probability * len(ordered)) - 1))
    return ordered[index]


def calibrate_measurements(
    predictions: Sequence[Measurement],
    ground_truth: Mapping[tuple[object, str], float],
    *,
    target_coverage: float = 0.95,
) -> CalibrationResult:
    """Estimate an empirical uncertainty multiplier without altering predictions.

    ``ground_truth`` is evaluation-only and must never be supplied to the
    reconstruction or scale-inference pipeline. The returned multiplier can
    be used by an evaluation/reporting layer to widen intervals when empirical
    coverage is below the requested target.
    """
    _validate_target(target_coverage)
    pairs = _pairs(predictions, ground_truth)
    if not pairs:
        return CalibrationResult(0, target_coverage, 0.0, 0.0, 1.0, 0.0)

    normalized = [abs(measurement.nominal_value - truth) / measurement.standard_deviation for measurement, truth in pairs]
    raw_covered = sum(
        1
        for measurement, truth in pairs
        if measurement.interval_95 is not None
        and measurement.interval_95[0] <= truth <= measurement.interval_95[1]
    ) / len(pairs)

    quantile_value = _finite_sample_quantile(normalized, target_coverage)
    factor = max(1.0, quantile_value / 1.96)
    calibrated_covered = sum(
        1
        for measurement, truth in pairs
        if abs(measurement.nominal_value - truth) <= 1.96 * measurement.standard_deviation * factor
    ) / len(pairs)

    return CalibrationResult(
        sample_count=len(pairs),
        target_coverage=target_coverage,
        empirical_coverage=raw_covered,
        calibrated_coverage=calibrated_covered,
        scale_factor=factor,
        normalized_error_quantile=quantile_value,
    )

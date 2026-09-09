from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import quantiles
from typing import Mapping, Sequence

from floorplan_ai.canonical.schema import Measurement


@dataclass(frozen=True)
class CalibrationResult:
    """Empirical calibration diagnostics for measurement intervals.

    Ground truth is evaluation-only: it is consumed here to estimate how well
    predicted uncertainty describes observed errors. The result is never fed
    back into reconstruction or scale inference automatically.
    """

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


def _pairs(
    predictions: Sequence[Measurement],
    ground_truth: Mapping[tuple[object, str], float],
) -> list[tuple[Measurement, float]]:
    pairs: list[tuple[Measurement, float]] = []
    for measurement in predictions:
        key = (measurement.target_entity_id, str(measurement.metric_type))
        if key not in ground_truth:
            continue
        truth = float(ground_truth[key])
        if not isfinite(truth) or truth <= 0.0:
            raise ValueError("ground-truth measurements must be finite and positive")
        if measurement.standard_deviation is None or measurement.standard_deviation <= 0.0:
            continue
        pairs.append((measurement, truth))
    return pairs


def calibrate_measurements(
    predictions: Sequence[Measurement],
    ground_truth: Mapping[tuple[object, str], float],
    *,
    target_coverage: float = 0.95,
) -> CalibrationResult:
    """Estimate an empirical uncertainty multiplier without altering predictions.

    ``ground_truth`` is explicitly an evaluation-only mapping keyed by
    ``(target_entity_id, metric_type)``. The multiplier is the ratio between
    the empirical target quantile of ``|error| / sigma`` and the normal-theory
    95% z-value (1.96). It can be applied by a reporting/evaluation layer, but
    this function does not mutate the canonical model.
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

    if len(normalized) == 1:
        quantile_value = normalized[0]
    else:
        # statistics.quantiles is deterministic and avoids a dependency on a
        # numerical stack for this evaluation-only operation.
        q_index = min(99, max(1, round(target_coverage * 100)))
        quantile_value = quantiles(normalized, n=100, method="inclusive")[q_index - 1]

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

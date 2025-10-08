"""Health score calculation with robust error handling and data quality checks."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cipette.config import Config

# Create Config instance for property access
config = Config()

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    """Data quality levels for health score calculation."""

    EXCELLENT = 'excellent'  # All data available and reliable
    GOOD = 'good'  # Most data available, minor gaps
    FAIR = 'fair'  # Some data missing, calculations limited
    POOR = 'poor'  # Significant data gaps, unreliable results
    INSUFFICIENT = 'insufficient'  # Not enough data for meaningful calculation


@dataclass
class HealthScoreResult:
    """Result of health score calculation with metadata."""

    overall_score: float
    health_class: str
    data_quality: DataQuality
    breakdown: dict[str, float]
    warnings: list[str]
    errors: list[str]
    calculation_metadata: dict[str, Any]


class HealthScoreCalculator:
    """Robust health score calculator with error handling and data quality checks."""

    def __init__(self):
        self.weights = config.HEALTH_SCORE_WEIGHTS
        self.thresholds = {
            'excellent': config.HEALTH_SCORE_EXCELLENT,
            'good': config.HEALTH_SCORE_GOOD,
            'fair': config.HEALTH_SCORE_FAIR,
            'poor': config.HEALTH_SCORE_POOR,
        }

    def calculate_health_score(
        self,
        success_rate: float | None,
        mttr_seconds: float | None,
        avg_duration_seconds: float | None,
        total_runs: int,
        days: int = 30,
    ) -> HealthScoreResult:
        """Calculate health score with comprehensive error handling and data quality assessment.

        Args:
            success_rate: Success rate percentage (0-100)
            mttr_seconds: Mean Time To Recovery in seconds
            avg_duration_seconds: Average duration in seconds
            total_runs: Total number of runs
            days: Time period for throughput calculation

        Returns:
            HealthScoreResult with score, quality assessment, and metadata
        """
        warnings = []
        errors = []
        breakdown = {}

        try:
            # Assess data quality first
            data_quality = self._assess_data_quality(
                success_rate, mttr_seconds, avg_duration_seconds, total_runs, days
            )

            # Calculate individual scores with error handling
            success_rate_score = self._calculate_success_rate_score(
                success_rate, warnings
            )
            mttr_score = self._calculate_mttr_score(mttr_seconds, warnings)
            duration_score = self._calculate_duration_score(
                avg_duration_seconds, warnings
            )
            throughput_score = self._calculate_throughput_score(
                total_runs, days, warnings
            )

            breakdown = {
                'success_rate_score': success_rate_score,
                'mttr_score': mttr_score,
                'duration_score': duration_score,
                'throughput_score': throughput_score,
            }

            # Calculate overall score with validation
            overall_score = self._calculate_overall_score(breakdown, warnings)

            # Determine health class
            health_class = self._determine_health_class(overall_score)

            # Prepare metadata
            calculation_metadata = {
                'input_data': {
                    'success_rate': success_rate,
                    'mttr_seconds': mttr_seconds,
                    'avg_duration_seconds': avg_duration_seconds,
                    'total_runs': total_runs,
                    'days': days,
                },
                'weights_used': self.weights,
                'thresholds_used': self.thresholds,
            }

            return HealthScoreResult(
                overall_score=overall_score,
                health_class=health_class,
                data_quality=data_quality,
                breakdown=breakdown,
                warnings=warnings,
                errors=errors,
                calculation_metadata=calculation_metadata,
            )

        except Exception as e:
            logger.error(f'Health score calculation failed: {e}', exc_info=True)
            errors.append(f'Calculation error: {str(e)}')

            return HealthScoreResult(
                overall_score=0.0,
                health_class='unknown',
                data_quality=DataQuality.INSUFFICIENT,
                breakdown={},
                warnings=warnings,
                errors=errors,
                calculation_metadata={'error': str(e)},
            )

    def _assess_data_quality(
        self,
        success_rate: float | None,
        mttr_seconds: float | None,
        avg_duration_seconds: float | None,
        total_runs: int,
        days: int,
    ) -> DataQuality:
        """Assess the quality of input data for health score calculation."""
        available_metrics = 0
        total_metrics = 4

        # Check each metric
        if success_rate is not None:
            available_metrics += 1
        if mttr_seconds is not None:
            available_metrics += 1
        if avg_duration_seconds is not None:
            available_metrics += 1
        if total_runs > 0 and days > 0:
            available_metrics += 1

        # Determine quality based on available data
        if available_metrics == total_metrics and total_runs >= 10:
            return DataQuality.EXCELLENT
        elif available_metrics >= 3 and total_runs >= 5:
            return DataQuality.GOOD
        elif available_metrics >= 2 and total_runs >= 3:
            return DataQuality.FAIR
        elif available_metrics >= 1 and total_runs >= 1:
            return DataQuality.POOR
        else:
            return DataQuality.INSUFFICIENT

    def _calculate_success_rate_score(
        self, success_rate: float | None, warnings: list
    ) -> float:
        """Calculate success rate score with validation."""
        if success_rate is None:
            warnings.append('Success rate data not available')
            return 0.0

        if not isinstance(success_rate, (int, float)):
            warnings.append(f'Invalid success rate type: {type(success_rate)}')
            return 0.0

        if success_rate < 0 or success_rate > 100:
            warnings.append(f'Success rate out of valid range (0-100): {success_rate}')
            return max(0.0, min(100.0, success_rate))

        return float(success_rate)

    def _calculate_mttr_score(
        self, mttr_seconds: float | None, warnings: list
    ) -> float:
        """Calculate MTTR score with validation."""
        if mttr_seconds is None:
            warnings.append('MTTR data not available - assuming no failures')
            return 100.0  # No failures is good

        if not isinstance(mttr_seconds, (int, float)):
            warnings.append(f'Invalid MTTR type: {type(mttr_seconds)}')
            return 0.0

        if mttr_seconds < 0:
            warnings.append(f'Negative MTTR value: {mttr_seconds}')
            return 0.0

        if mttr_seconds == 0:
            warnings.append('MTTR is zero - this may indicate data quality issues')
            return 100.0

        # Calculate score (shorter is better)
        max_mttr = config.HEALTH_SCORE_MTTR_MAX_SECONDS
        if mttr_seconds > max_mttr:
            warnings.append(
                f'MTTR exceeds maximum threshold ({max_mttr}s): {mttr_seconds}s'
            )

        score = max(0.0, 100.0 - (mttr_seconds / max_mttr) * 100.0)
        return min(100.0, score)

    def _calculate_duration_score(
        self, avg_duration_seconds: float | None, warnings: list
    ) -> float:
        """Calculate duration score with validation."""
        if avg_duration_seconds is None:
            warnings.append('Duration data not available')
            return 0.0

        if not isinstance(avg_duration_seconds, (int, float)):
            warnings.append(f'Invalid duration type: {type(avg_duration_seconds)}')
            return 0.0

        if avg_duration_seconds < 0:
            warnings.append(f'Negative duration value: {avg_duration_seconds}')
            return 0.0

        if avg_duration_seconds == 0:
            warnings.append('Duration is zero - this may indicate data quality issues')
            return 0.0

        # Calculate score (shorter is better)
        max_duration = config.HEALTH_SCORE_DURATION_MAX_SECONDS
        if avg_duration_seconds > max_duration:
            warnings.append(
                f'Duration exceeds maximum threshold ({max_duration}s): {avg_duration_seconds}s'
            )

        score = max(0.0, 100.0 - (avg_duration_seconds / max_duration) * 100.0)
        return min(100.0, score)

    def _calculate_throughput_score(
        self, total_runs: int, days: int, warnings: list
    ) -> float:
        """Calculate throughput score with validation."""
        if not isinstance(total_runs, int) or total_runs < 0:
            warnings.append(f'Invalid total_runs value: {total_runs}')
            return 0.0

        if not isinstance(days, int) or days <= 0:
            warnings.append(f'Invalid days value: {days}')
            return 0.0

        if total_runs == 0:
            warnings.append('No runs found in the specified period')
            return 0.0

        runs_per_day = total_runs / days
        min_runs_per_day = config.HEALTH_SCORE_THROUGHPUT_MIN_DAYS

        if runs_per_day < min_runs_per_day:
            warnings.append(
                f'Low throughput: {runs_per_day:.2f} runs/day (minimum: {min_runs_per_day})'
            )

        score = min(100.0, (runs_per_day / min_runs_per_day) * 100.0)
        return max(0.0, score)

    def _calculate_overall_score(
        self, breakdown: dict[str, float], warnings: list
    ) -> float:
        """Calculate overall weighted score with validation."""
        try:
            # Validate weights sum to 1.0
            weight_sum = sum(self.weights.values())
            if abs(weight_sum - 1.0) > 0.001:
                warnings.append(f'Weights do not sum to 1.0: {weight_sum}')

            # Calculate weighted average
            overall_score = (
                breakdown['success_rate_score'] * self.weights['success_rate']
                + breakdown['mttr_score'] * self.weights['mttr']
                + breakdown['duration_score'] * self.weights['duration']
                + breakdown['throughput_score'] * self.weights['throughput']
            )

            # Validate result
            if not isinstance(overall_score, (int, float)):
                warnings.append(f'Invalid overall score type: {type(overall_score)}')
                return 0.0

            if overall_score < 0 or overall_score > 100:
                warnings.append(
                    f'Overall score out of valid range (0-100): {overall_score}'
                )
                return max(0.0, min(100.0, overall_score))

            return round(overall_score, 1)

        except Exception as e:
            warnings.append(f'Error calculating overall score: {str(e)}')
            return 0.0

    def _determine_health_class(self, overall_score: float) -> str:
        """Determine health class based on overall score."""
        if overall_score >= self.thresholds['excellent']:
            return 'excellent'
        elif overall_score >= self.thresholds['good']:
            return 'good'
        elif overall_score >= self.thresholds['fair']:
            return 'fair'
        else:
            return 'poor'


# Convenience function for backward compatibility
def calculate_health_score_safe(
    success_rate: float | None,
    mttr_seconds: float | None,
    avg_duration_seconds: float | None,
    total_runs: int,
    days: int = 30,
) -> dict[str, Any]:
    """Safe wrapper for health score calculation with backward compatibility.

    Returns:
        Dictionary compatible with existing code
    """
    calculator = HealthScoreCalculator()
    result = calculator.calculate_health_score(
        success_rate, mttr_seconds, avg_duration_seconds, total_runs, days
    )

    return {
        'overall_score': result.overall_score,
        'health_class': result.health_class,
        'data_quality': result.data_quality.value,
        'breakdown': result.breakdown,
        'warnings': result.warnings,
        'errors': result.errors,
        'calculation_metadata': result.calculation_metadata,
    }

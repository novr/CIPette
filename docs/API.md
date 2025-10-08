# CIPette API Documentation

## Health Score Calculator API

### HealthScoreCalculator Class

The `HealthScoreCalculator` class provides robust health score calculation with comprehensive error handling and data quality assessment.

#### Constructor

```python
from cipette.health_calculator import HealthScoreCalculator

calculator = HealthScoreCalculator()
```

#### Methods

##### `calculate_health_score()`

Calculate CI/CD health score with comprehensive error handling and data quality assessment.

**Parameters:**
- `success_rate` (Optional[float]): Success rate percentage (0-100)
- `mttr_seconds` (Optional[float]): Mean Time To Recovery in seconds
- `avg_duration_seconds` (Optional[float]): Average duration in seconds
- `total_runs` (int): Total number of runs
- `days` (int, optional): Time period for throughput calculation (default: 30)

**Returns:**
- `HealthScoreResult`: Object containing score, quality assessment, and metadata

**Example:**
```python
result = calculator.calculate_health_score(
    success_rate=95.0,
    mttr_seconds=300.0,
    avg_duration_seconds=600.0,
    total_runs=30,
    days=30
)

print(f"Health Score: {result.overall_score}")
print(f"Health Class: {result.health_class}")
print(f"Data Quality: {result.data_quality}")
print(f"Warnings: {result.warnings}")
```

### HealthScoreResult Class

Result object containing health score calculation results and metadata.

#### Attributes

- `overall_score` (float): Overall health score (0-100)
- `health_class` (str): Health classification ('excellent', 'good', 'fair', 'poor')
- `data_quality` (DataQuality): Data quality level
- `breakdown` (Dict[str, float]): Individual metric scores
- `warnings` (List[str]): Warning messages
- `errors` (List[str]): Error messages
- `calculation_metadata` (Dict[str, Any]): Calculation metadata

### DataQuality Enum

Data quality levels for health score calculation.

```python
from cipette.health_calculator import DataQuality

# Quality levels
DataQuality.EXCELLENT      # All data available and reliable
DataQuality.GOOD          # Most data available, minor gaps
DataQuality.FAIR          # Some data missing, calculations limited
DataQuality.POOR          # Significant data gaps, unreliable results
DataQuality.INSUFFICIENT  # Not enough data for meaningful calculation
```

### Convenience Functions

#### `calculate_health_score_safe()`

Safe wrapper for health score calculation with backward compatibility.

```python
from cipette.health_calculator import calculate_health_score_safe

result = calculate_health_score_safe(
    success_rate=95.0,
    mttr_seconds=300.0,
    avg_duration_seconds=600.0,
    total_runs=30,
    days=30
)

# Returns dictionary compatible with existing code
print(result['overall_score'])
print(result['health_class'])
print(result['data_quality'])
```

## Database API

### Health Score Integration

The database module now includes health score calculation in metrics retrieval.

#### `get_metrics_by_repository()`

Enhanced to include health score data.

**Returns:**
List of dictionaries with the following additional fields:
- `health_score` (float): Overall health score
- `health_class` (str): Health classification
- `data_quality` (str): Data quality level
- `health_breakdown` (Dict): Individual metric scores
- `health_warnings` (List[str]): Warning messages
- `health_errors` (List[str]): Error messages

**Example:**
```python
from cipette.database import get_metrics_by_repository

metrics = get_metrics_by_repository(repository="my-repo", days=30)

for metric in metrics:
    print(f"Repository: {metric['repository']}")
    print(f"Workflow: {metric['workflow_name']}")
    print(f"Health Score: {metric['health_score']}")
    print(f"Health Class: {metric['health_class']}")
    print(f"Data Quality: {metric['data_quality']}")
    
    if metric['health_warnings']:
        print(f"Warnings: {metric['health_warnings']}")
    
    if metric['health_errors']:
        print(f"Errors: {metric['health_errors']}")
```

## Web Application API

### Template Filters

New template filters for health score display.

#### `health_class`
Get CSS class for health score classification.

```html
<td class="{{ metric.health_class|health_class }}">
```

#### `health_emoji`
Get emoji for health score classification.

```html
<span class="health-emoji">{{ metric.health_class|health_emoji }}</span>
```

#### `data_quality_emoji`
Get emoji for data quality level.

```html
<span class="data-quality-indicator">
    {{ metric.data_quality|data_quality_emoji }}
</span>
```

#### `data_quality_class`
Get CSS class for data quality level.

```html
<span class="{{ metric.data_quality|data_quality_class }}">
```

#### `has_warnings`
Check if there are any warnings.

```html
{% if metric.health_warnings|has_warnings %}
    <span class="alert-warning">⚠️</span>
{% endif %}
```

#### `has_errors`
Check if there are any errors.

```html
{% if metric.health_errors|has_errors %}
    <span class="alert-error">⚠️</span>
{% endif %}
```

## Configuration

### Health Score Settings

Health score calculation parameters can be configured in `config.py`.

```python
# Health score weights
HEALTH_SCORE_WEIGHTS = {
    'success_rate': 0.35,    # 35% - Most important
    'mttr': 0.25,           # 25% - Recovery time
    'duration': 0.20,       # 20% - Execution time
    'throughput': 0.20      # 20% - Execution frequency
}

# Health score thresholds
HEALTH_SCORE_EXCELLENT = 85  # 85+ points: Excellent
HEALTH_SCORE_GOOD = 70       # 70-84 points: Good
HEALTH_SCORE_FAIR = 50       # 50-69 points: Fair
HEALTH_SCORE_POOR = 0        # <50 points: Poor

# Health score calculation parameters
HEALTH_SCORE_DURATION_MAX_SECONDS = 1800  # 30 minutes max
HEALTH_SCORE_MTTR_MAX_SECONDS = 7200      # 2 hours max
HEALTH_SCORE_THROUGHPUT_MIN_DAYS = 1      # Minimum 1 run per day
```

## Error Handling

### Exception Types

The health calculator handles various error conditions:

- **ValueError**: Invalid input values
- **TypeError**: Invalid data types
- **ZeroDivisionError**: Division by zero in calculations
- **General Exception**: Unexpected errors

### Error Recovery

- **Graceful Degradation**: System continues to function even with calculation errors
- **Detailed Logging**: All errors and warnings are logged with context
- **Fallback Values**: Default values provided when calculations fail
- **User Notification**: Errors and warnings displayed in UI

### Logging

Health score calculations are logged with appropriate levels:

- **INFO**: Normal calculation results
- **WARNING**: Data quality issues, missing data
- **ERROR**: Calculation failures, invalid data

Example log output:
```
2024-01-15 10:30:00 - cipette.database - WARNING - Health score warnings for my-repo/my-workflow: Success rate data not available, MTTR data not available - assuming no failures
2024-01-15 10:30:01 - cipette.database - ERROR - Health score errors for my-repo/my-workflow: Calculation error: Invalid MTTR type
```

## Testing

### Test Coverage

Comprehensive test coverage for health score functionality:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Edge Cases**: Boundary value testing
- **Error Conditions**: Exception handling testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run health calculator tests specifically
uv run pytest tests/test_database.py::test_health_calculator_robust -v

# Run with coverage
uv run pytest --cov=cipette.health_calculator
```

### Test Examples

```python
def test_health_calculator_robust():
    """Test robust health score calculator with error handling."""
    calculator = HealthScoreCalculator()
    
    # Test with missing data
    result = calculator.calculate_health_score(
        success_rate=None,
        mttr_seconds=None,
        avg_duration_seconds=600.0,
        total_runs=5,
        days=30
    )
    
    assert result.data_quality == DataQuality.FAIR
    assert len(result.warnings) > 0
    assert 'Success rate data not available' in result.warnings
```

## Migration Guide

### From Legacy Functions

If you're using the legacy `calculate_health_score()` function, you can migrate to the new system:

**Before:**
```python
from cipette.database import calculate_health_score

scores = calculate_health_score(
    success_rate=95.0,
    mttr_seconds=300.0,
    avg_duration_seconds=600.0,
    total_runs=30,
    days=30
)
```

**After:**
```python
from cipette.health_calculator import calculate_health_score_safe

result = calculate_health_score_safe(
    success_rate=95.0,
    mttr_seconds=300.0,
    avg_duration_seconds=600.0,
    total_runs=30,
    days=30
)

# Access scores the same way
scores = {
    'overall_score': result['overall_score'],
    'success_rate_score': result['breakdown']['success_rate_score'],
    # ... etc
}
```

### Backward Compatibility

The legacy functions are still available and will continue to work, but they now use the new robust calculation system internally.

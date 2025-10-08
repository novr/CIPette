# CIPette User Guide

## Overview

CIPette is a simple CI/CD dashboard for GitHub Actions that provides comprehensive health monitoring and insights. This guide will help you understand and use all the features effectively.

## Getting Started

### Installation

1. **Install uv** (fast Python package manager):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and setup**:
   ```bash
   git clone https://github.com/novr/CIPette
   cd CIPette
   uv sync
   ```

3. **Configure**:
   ```bash
   cp env.example .env
   # Edit .env with your GitHub token and repositories
   ```

4. **Run**:
   ```bash
   # Collect data
   uv run cipette-collect
   
   # View dashboard
   uv run cipette-web
   
   # Open http://localhost:5000
   ```

## Understanding the Dashboard

### Health Score System

The health score is a comprehensive 0-100 assessment of your CI/CD pipeline health.

#### Health Score Components

- **Success Rate (35%)**: Percentage of successful workflow runs
- **MTTR (25%)**: Mean Time To Recovery - how quickly you recover from failures
- **Duration (20%)**: Average execution time of workflows
- **Throughput (20%)**: Frequency of workflow executions

#### Health Score Levels

| Score Range | Level | Color | Description |
|-------------|-------|-------|-------------|
| 85-100 | 🟢 Excellent | Green | Outstanding performance |
| 70-84 | 🟡 Good | Yellow | Good performance with minor issues |
| 50-69 | 🟠 Fair | Orange | Acceptable but needs improvement |
| 0-49 | 🔴 Poor | Red | Significant issues requiring attention |

### Data Quality Indicators

Each health score includes a data quality indicator:

| Indicator | Quality | Description |
|-----------|---------|-------------|
| ✅ | Excellent | All data available and reliable |
| 👍 | Good | Most data available, minor gaps |
| ⚠️ | Fair | Some data missing, calculations limited |
| ❌ | Poor | Significant data gaps, unreliable results |
| ❓ | Insufficient | Not enough data for meaningful calculation |

### Warning and Error Indicators

- **⚠️ Warning**: Data quality issues or unusual values
- **⚠️ Error**: Calculation errors or critical issues

Hover over these indicators to see detailed information.

## Using the Dashboard

### Filtering Data

#### Time Period Filter
- **All time**: Shows all available data
- **Last 7 days**: Recent week performance
- **Last 30 days**: Recent month performance
- **Last 90 days**: Recent quarter performance

#### Repository Filter
- **All repositories**: Shows data from all configured repositories
- **Specific repository**: Shows data from selected repository only

### Interpreting Results

#### Health Score Breakdown

Click on any health score to see the detailed breakdown:

- **Success Rate Score**: Based on percentage of successful runs
- **MTTR Score**: Based on recovery time (shorter is better)
- **Duration Score**: Based on execution time (shorter is better)
- **Throughput Score**: Based on execution frequency (optimal range)

#### Understanding Warnings

Common warnings and their meanings:

- **"Success rate data not available"**: No success/failure data found
- **"MTTR data not available - assuming no failures"**: No failure data to calculate recovery time
- **"Duration data not available"**: No execution time data found
- **"Low throughput: X runs/day"**: Workflows running less frequently than recommended
- **"Success rate out of valid range"**: Success rate outside 0-100% range
- **"MTTR exceeds maximum threshold"**: Recovery time longer than 2 hours
- **"Duration exceeds maximum threshold"**: Execution time longer than 30 minutes

## Best Practices

### Data Collection

1. **Regular Collection**: Run data collection regularly to maintain up-to-date metrics
2. **Sufficient Data**: Ensure you have at least 10 runs for reliable health scores
3. **Multiple Repositories**: Monitor all your important repositories

### Interpreting Health Scores

1. **Focus on Trends**: Look for patterns over time rather than single scores
2. **Address Poor Scores**: Investigate and fix issues indicated by low scores
3. **Monitor Warnings**: Pay attention to data quality warnings
4. **Set Thresholds**: Establish acceptable health score thresholds for your team

### Troubleshooting

#### Low Health Scores

**Poor Success Rate**:
- Review failed workflow runs
- Check for flaky tests
- Improve test reliability
- Fix environment issues

**High MTTR**:
- Implement faster rollback procedures
- Improve monitoring and alerting
- Reduce deployment complexity
- Automate recovery processes

**Long Duration**:
- Optimize workflow steps
- Use caching for dependencies
- Parallelize independent tasks
- Review resource allocation

**Low Throughput**:
- Increase deployment frequency
- Implement continuous deployment
- Reduce manual approval steps
- Automate more processes

#### Data Quality Issues

**Insufficient Data**:
- Ensure workflows are running regularly
- Check data collection configuration
- Verify GitHub token permissions
- Review repository access

**Missing Metrics**:
- Check workflow completion status
- Verify data collection logs
- Ensure proper workflow configuration
- Review GitHub API rate limits

## Configuration

### Environment Variables

Key configuration options in your `.env` file:

```bash
# GitHub Configuration
GITHUB_TOKEN=your_github_token_here
TARGET_REPOSITORIES=owner/repo1,owner/repo2

# Data Collection
MAX_WORKFLOW_RUNS=10
MTTR_REFRESH_INTERVAL=300

# Web Application
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=false
```

### Health Score Thresholds

You can customize health score thresholds in `config.py`:

```python
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

## Advanced Usage

### Automated Monitoring

Set up automated health score monitoring:

```bash
# Create a monitoring script
#!/bin/bash
uv run cipette-collect
HEALTH_SCORE=$(uv run python -c "
from cipette.database import get_metrics_by_repository
metrics = get_metrics_by_repository()
if metrics:
    avg_score = sum(m['health_score'] for m in metrics) / len(metrics)
    print(f'{avg_score:.1f}')
else:
    print('0.0')
")

if (( $(echo "$HEALTH_SCORE < 70" | bc -l) )); then
    echo "Health score is low: $HEALTH_SCORE"
    # Send alert notification
fi
```

### Integration with CI/CD

Integrate health score checks into your CI/CD pipeline:

```yaml
# .github/workflows/health-check.yml
name: Health Check
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check Health Score
        run: |
          # Your health score checking logic here
          if [ "$HEALTH_SCORE" -lt 70 ]; then
            echo "Health score is below threshold"
            exit 1
          fi
```

## Troubleshooting

### Common Issues

#### "No Data Available"
- Check GitHub token permissions
- Verify repository names in configuration
- Ensure workflows have run recently
- Check data collection logs

#### "Health Score Calculation Failed"
- Review error logs for specific issues
- Check data quality indicators
- Verify input data validity
- Contact support if issues persist

#### "Database Connection Error"
- Check database file permissions
- Ensure sufficient disk space
- Verify database file integrity
- Restart the application

### Getting Help

1. **Check Logs**: Review application logs for error details
2. **Verify Configuration**: Ensure all settings are correct
3. **Test Data Collection**: Run data collection manually
4. **Review Documentation**: Check API documentation for details
5. **Report Issues**: Create GitHub issues for bugs or feature requests

## Performance Tips

### Optimization

1. **Regular Cleanup**: Periodically clean old data to maintain performance
2. **Efficient Filtering**: Use specific repository filters when possible
3. **Cache Management**: Monitor cache performance and adjust TTL as needed
4. **Resource Monitoring**: Monitor system resources during data collection

### Scaling

For large-scale deployments:

1. **Database Optimization**: Consider using PostgreSQL for large datasets
2. **Caching Strategy**: Implement Redis for distributed caching
3. **Load Balancing**: Use multiple application instances
4. **Monitoring**: Implement comprehensive monitoring and alerting

## Security Considerations

### GitHub Token Security

- Use minimal required permissions
- Rotate tokens regularly
- Store tokens securely
- Monitor token usage

### Data Privacy

- Review data collection scope
- Implement data retention policies
- Secure database access
- Regular security audits

## Support and Contributing

### Getting Support

- **Documentation**: Check this guide and API documentation
- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Join community discussions
- **Email**: Contact maintainers for critical issues

### Contributing

- **Code**: Submit pull requests for improvements
- **Documentation**: Help improve guides and documentation
- **Testing**: Report bugs and test new features
- **Feedback**: Share your experience and suggestions

---

For more technical details, see the [API Documentation](API.md).

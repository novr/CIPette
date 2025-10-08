# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2025-01-08

### Fixed
- Fix `sqlite3.Row` object access error in health score processing
- Resolve `IndexError: No item with that key` when accessing cached health scores
- Add missing health score columns to all-time metrics query
- Ensure proper health score display in dashboard

### Technical Improvements
- Improved database query construction for health score cache
- Enhanced error handling for SQLite row access
- Better null value handling in health score calculations

## [0.2.1] - 2025-01-27

### Fixed
- Resolve CI test failures caused by code formatting issues
- Fix semantic-release command in GitHub Actions workflow
- Ensure proper artifact upload in release pipeline

### Technical Improvements
- Improved CI/CD pipeline reliability
- Enhanced release automation workflow
- Better error handling in release process

## [0.2.0] - 2025-01-27

### Added
- TOML-based configuration system for flexible project settings
- Centralized configuration management with `config.toml`
- Enhanced configuration validation and error handling
- Support for all application settings in single configuration file

### Changed
- Migrated from environment variables to TOML configuration
- Removed dependency on `.env` file and `python-dotenv`
- Updated setup instructions to use `config.toml.example`
- Improved configuration loading with graceful fallbacks

### Technical Improvements
- Better separation of configuration concerns
- Enhanced error messages for missing configuration
- Improved code organization and maintainability
- Fixed all linting issues and code quality improvements

## [0.1.1] - 2025-10-08

### Fixed
- Resolve CI test failures in data collector tests
- Fix GITHUB_TOKEN validation in test environment
- Improve test mocking for GitHubClient methods
- Fix code formatting issues across all Python files
- Remove hardcoded version expectations from tests

### Technical Improvements
- Enhanced test stability and reliability
- Improved CI/CD pipeline consistency
- Better error handling in test environment

## [0.1.0] - 2025-10-08

### Added
- Initial release with MVP features
- GitHub Actions workflow data collection
- Basic metrics calculation (Duration, Success Rate, Throughput, MTTR)
- Web dashboard with filtering capabilities
- SQLite database storage
- CI/CD health score system (0-100 points)
- Data quality assessment (5 levels)
- Robust error handling with warnings and alerts
- MTTR and health score caching system
- Background cache refresh workers
- Template filters for UI display
- Comprehensive test coverage
- Semantic versioning system
- Git tag integration
- Version management scripts

### Technical Details
- **Framework**: Flask 3.0+
- **Database**: SQLite3
- **API**: GitHub Actions API
- **Python**: 3.11+ required
- **Package Manager**: uv

### Performance
- MTTR cache for 10-10,000x speedup
- Health score cache system
- Background workers for cache refresh
- Optimized database queries with proper indexing

### Documentation
- User guide with best practices
- API documentation for developers
- Configuration examples
- Version management guide

## [0.0.9] - 2025-01-27

### Added
- Core functionality implementation
- GitHub Actions API integration
- Basic data collection and storage
- SQLite database setup
- Initial web dashboard
- Basic error handling

### Changed
- Project structure optimization
- Documentation improvements

## [0.0.8] - 2025-01-27

### Added
- Database and API foundation
- Database connection management
- GitHub API client implementation
- Basic workflow data collection
- Error handling improvements

### Fixed
- Connection timeout issues
- API rate limiting

## [0.0.7] - 2025-01-27

### Added
- Performance optimizations
- MTTR cache implementation
- Background job system
- Query optimization
- Metrics caching

### Performance
- 10-10,000x speedup for MTTR calculations
- Reduced database load with caching

## [0.0.6] - 2025-01-27

### Added
- Web dashboard implementation
- Flask web application
- HTML templates and CSS styling
- Dashboard metrics display
- Repository filtering

### Changed
- UI/UX improvements
- Responsive design

## [0.0.5] - 2025-01-27

### Added
- Testing and quality improvements
- Comprehensive test suite
- Code quality improvements
- Error handling enhancements
- Documentation updates

### Fixed
- Test coverage gaps
- Code style inconsistencies

## [0.0.4] - 2025-01-27

### Added
- Security and stability improvements
- SQL injection protection
- Database schema normalization
- Enhanced error handling
- Configuration management

### Security
- SQL injection prevention
- Input validation
- Secure configuration handling

## [0.0.3] - 2025-01-27

### Added
- Health score system
- Health score calculation
- Data quality assessment
- Error handling improvements
- UI enhancements

### Changed
- Metrics calculation algorithm
- Dashboard display improvements

## [0.0.2] - 2025-01-27

### Added
- Enhanced health score features
- Robust health score calculation
- Data quality indicators
- Comprehensive error handling
- Documentation improvements

### Fixed
- Health score calculation edge cases
- Data quality assessment accuracy

## [0.0.1] - 2025-01-27

### Added
- Health score caching system
- Health score cache implementation
- Background refresh mechanism
- Robust error handling
- Performance optimizations

### Performance
- Cache-based health score calculation
- Background worker improvements

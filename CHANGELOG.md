# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup and structure

### Security
- fix(security): resolve CVE-2026-26007, CVE-2026-34073, CVE-2026-39892: bump cryptography to 46.0.7
- fix(security): resolve CVE-2025-68146, CVE-2026-22701: bump filelock to 3.20.3
- fix(security): resolve CVE-2026-42215, CVE-2026-42284, CVE-2026-44244, GHSA-mv93-w799-cj2w: bump gitpython to 3.1.50
- fix(security): resolve CVE-2026-23949: bump jaraco-context to 6.1.0
- fix(security): resolve CVE-2025-61669, CVE-2026-40110, CVE-2026-35397, CVE-2026-40934: bump jupyter-server to 2.18.0
- fix(security): resolve CVE-2026-42266, CVE-2026-42557: bump jupyterlab to 4.5.7
- fix(security): resolve CVE-2026-41066: bump lxml to 6.1.0
- fix(security): resolve CVE-2026-33079, CVE-2026-44708, CVE-2026-44896, CVE-2026-44897: bump mistune to 3.2.1
- fix(security): resolve CVE-2025-53000, CVE-2026-39378, CVE-2026-39377: bump nbconvert to 7.17.1
- fix(security): resolve CVE-2026-40171: bump notebook to 7.5.6
- fix(security): resolve CVE-2026-25990, CVE-2026-40192, CVE-2026-42308, CVE-2026-42309, CVE-2026-42310, CVE-2026-42311: bump pillow to 12.2.0
- fix(security): resolve CVE-2026-1703, CVE-2026-6357: bump pip to 26.1
- fix(security): resolve CVE-2026-0994: bump protobuf to 6.33.5
- fix(security): resolve CVE-2026-23490, CVE-2026-30922: bump pyasn1 to 0.6.3
- fix(security): resolve CVE-2026-4539: bump pygments to 2.20.0
- fix(security): resolve CVE-2025-71176: bump pytest to 9.0.3
- fix(security): resolve CVE-2026-28684: bump python-dotenv to 1.2.2
- fix(security): resolve CVE-2026-24486, CVE-2026-40347, CVE-2026-42561: bump python-multipart to 0.0.27
- fix(security): resolve CVE-2026-25645: bump requests to 2.33.0
- fix(security): resolve GHSA-78cv-mqj4-43f7, CVE-2026-31958, CVE-2026-35536: bump tornado to 6.5.5
- fix(security): resolve CVE-2026-21441, CVE-2026-44431, CVE-2026-44432: bump urllib3 to 2.7.0
- fix(security): resolve CVE-2026-22702: bump virtualenv to 21.3.3
- fix(security): resolve CVE-2026-21860, CVE-2026-27199: bump werkzeug to 3.1.8
- Documented PYSEC-2022-42969 (py 1.11.0, transitive via interrogate) as a deferred known vulnerability; vulnerable code path unused, no upstream fix available

## [0.1.0] - TBD

### Added
- Initial project structure with Poetry package management
- Pydantic v2 JSON schema validation
- Structured logging with structlog and rich console output
- Pre-commit hooks (Ruff format, Ruff lint, BasedPyright, Bandit, Safety)
- Comprehensive test suite with pytest
- GitHub Actions CI/CD pipeline with quality gates
- CLI tool foundation
- License

### Documentation
- README with project overview and quick start
- CONTRIBUTING guidelines with development workflow
- References to ByronWilliamsCPA org-level Security Policy
- References to ByronWilliamsCPA org-level Code of Conduct

### Infrastructure
- Poetry dependency management with lock file
- pytest test framework with coverage reporting
- GitHub issue tracking and templates
- Automated dependency security scanning (Safety, Bandit)
- Code quality enforcement (Ruff, BasedPyright)
- CI/CD pipeline with multiple quality gates

### Security
- Bandit security linting
- Safety dependency vulnerability scanning
- Pre-commit hooks for security validation

[Unreleased]: https://github.com/ByronWilliamsCPA/audio_processor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ByronWilliamsCPA/audio_processor/releases/tag/v0.1.0

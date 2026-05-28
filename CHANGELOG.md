# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project setup and structure
- feat(preprocessing): audio preprocessing pipeline phases 1-4 — FFmpeg-based format conversion and video audio extraction (`AudioConverter`), signal conditioning with resampling/normalization/DC-offset removal (`AudioConditioner`), SNR-based quality assessment (`QualityAssessor`), Silero VAD voice activity detection (`VADProcessor`), Deepgram Nova-2 transcription with diarization and summarization (`DeepgramTranscriptionClient`), multi-format transcript output (`ArtifactGenerator`), and ARQ background job orchestration (`process_audio_job`) with Redis-backed status tracking
- feat(api): REST endpoints for audio upload, job status polling, and result retrieval; job processing delegated to ARQ worker

### Fixed
- fix(jobs): correct field paths for `duration_ms` and `language` in `process_audio_job` result assembly; both now read from `TranscriptionResult.metadata` where they actually live, preventing `AttributeError` at runtime
- fix(api): guard `content-length` header parsing against malformed values; `int()` conversion is now wrapped in a `ValueError` handler so a non-numeric header no longer raises an unhandled exception
- fix(tests): restore `tmp_path` fixture in `test_custom_initialization` for `AudioConverter`, `AudioConditioner`, and `VADProcessor`; hardcoded `/custom/temp` caused `PermissionError` on systems without root access

### Fixed

- fix(renovate): switch Renovate manager from poetry to pep621 for uv-managed project; poetry manager was silently producing zero dependency PRs
- fix(renovate): correct pep621 matchDepTypes to project.dependencies / dependency-groups / tool.uv.dev-dependencies
- fix(renovate): add "regex" to enabledManagers; omitting it silently disabled customManagers and broke CI version-pin regex tracking
- fix(renovate): add project.optional-dependencies packageRule to group extras deps; ungrouped extras would have generated one PR per package
- fix(renovate): add "pin" to github-actions matchUpdateTypes so SHA digest-pin PRs are also auto-merged
- fix(renovate): replace no-op postUpdateOptions with uvUpdatePreciseVersion so lockFileMaintenance correctly regenerates uv.lock
- fix(ci): switch release workflow trigger from push to workflow_run so releases are gated behind CI success; add job-level if guard for workflow_run conclusion; disable PyPI publishing (private repo); remove unsupported attestations and environment inputs

### Security
- fix(security): resolve CVE-2026-26007, CVE-2026-34073, CVE-2026-39892: bump cryptography to 48.0.0
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
- fix(security): resolve PYSEC-2026-161 (CVE in starlette < 1.1.0): bump fastapi to >=0.133.0, resolves starlette to 1.1.0
- Documented CVE-2026-4538 / PYSEC-2026-139 (torch 2.9.1, CVSS 7.8 AV:L HIGH) as a deferred known vulnerability; no upstream fix; torch absent from production container (Dockerfile installs no optional extras); reassess-by 2026-07-26

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

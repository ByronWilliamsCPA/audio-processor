# Security Policy

## Reporting a Vulnerability

Do not open a public issue for security problems. Use one of these private
channels:

1. **GitHub Security Advisory** (preferred): use the
   [Private Vulnerability Reporting](https://github.com/ByronWilliamsCPA/audio-processor/security/advisories/new)
   form. Do not open a public issue.
2. **Email**: send details to **<byronawilliams@gmail.com>**. Use the subject
   line `SECURITY:` followed by a short summary.

Both channels are monitored by the maintainer. Reports remain confidential
until a fix is published.

## What to Include in a Report

A useful report contains, at minimum:

- A clear description of the issue and the security impact (what an attacker
  can do).
- The affected file path, component, or commit SHA.
- Steps to reproduce, including any inputs, environment, or configuration
  needed.
- A proof of concept if you have one (snippet, log, or test case).
- Suggested fix or mitigation, if known.
- Your contact details and whether you want public credit in the advisory.

## Supported Versions

| Version            | Supported |
|--------------------|-----------|
| `main` (latest)    | Yes       |
| Most recent tag    | Yes       |
| Older tags / SHAs  | No        |

## Response Timeline

| Stage                                  | Target                                        |
|----------------------------------------|-----------------------------------------------|
| Acknowledgement of report              | within 14 days (target: 5 business days)      |
| Triage and severity (non-critical)     | 10 business days from acknowledgement         |
| Triage and severity (critical)         | 2 business days from acknowledgement          |
| Fix or mitigation for critical reports | 14 calendar days from acknowledgement         |
| Fix released for other severities      | 30 calendar days from acknowledgement         |

These are targets, not guarantees. All windows run from acknowledgement of
the report. The maintainer will keep the reporter updated if a fix needs
longer.

## Security Surface

Audio Processor handles untrusted audio files and integrates with external
APIs. The key risk areas are:

### Path Traversal in File I/O

Audio files are accepted as user-supplied paths and passed to libraries
(librosa, pydub, ffmpeg-python, soundfile). Any path that is not validated
against an allow-list of directories before use can be exploited to read
or overwrite arbitrary files on the host.

**Controls applied**: all input paths are resolved to absolute paths and
checked against a configured upload directory before any I/O operation.
Temporary intermediate files are written only inside a controlled temp
directory and cleaned up on success or failure.

### Dependency CVEs in Audio Processing Libraries

The pipeline depends on librosa, pydub, ffmpeg-python, soundfile, and
silero-vad. These libraries have historically carried CVEs related to
malformed codec handling and native library bindings (especially FFmpeg).

**Controls applied**: `pip-audit` runs in CI on every push; known unfixed
CVEs are tracked in `docs/known-vulnerabilities.md`. FFmpeg is pinned to a
supported release. The `urllib3>=2.6.0` pin in `pyproject.toml` addresses
CVE-2025-66418 and CVE-2025-66471. Dependency updates are automated via
Renovate.

### Pipeline Injection

Audio metadata (ID3 tags, EXIF-style fields) returned from format detection
libraries can contain attacker-controlled strings that are later interpolated
into log messages, FFmpeg command arguments, or downstream API payloads.

**Controls applied**: metadata is extracted as typed fields, never
interpolated directly into shell commands (use `ffmpeg-python` Python API,
not `subprocess` with string concatenation), and sanitized before inclusion
in structured log output.

### External API Key Exposure

The Deepgram API key is loaded from environment variables. Hardcoding keys
in source, committing `.env` files, or logging request headers could expose
credentials.

**Controls applied**: API keys are loaded exclusively from environment
variables via Pydantic Settings; `.env` is listed in `.gitignore`; secret
scanning runs via `detect-secrets` and TruffleHog pre-commit hooks.

## Security Practices

- Static analysis: CodeQL, Bandit, Ruff security rules (`S` category)
- Dependency scanning: `pip-audit` in CI
- Container scanning: Trivy on Docker images in CI
- SBOM generation for tagged releases (CycloneDX format)
- Secret scanning: `detect-secrets` and TruffleHog as pre-commit hooks
- Least-privilege workflow tokens in GitHub Actions
- SHA-pinned third-party actions

## CVE and Advisory Workflow

For confirmed vulnerabilities rated Moderate or higher:

1. Request a CVE through GitHub.
2. Draft and publish a GitHub Security Advisory on the repository.
3. Record remediation in the advisory and in `CHANGELOG.md`.
4. Update or remove the entry in `docs/known-vulnerabilities.md`.

## Disclosure

This project follows coordinated disclosure. Public details are published in
the advisory once a fix or mitigation is available. Reporters who want credit
should say so in the report; otherwise credit is anonymous.

Last updated: 2026-05-16

---
title: "Template Feedback"
schema_type: common
status: published
owner: core-maintainer
purpose: "Document template issues for upstream fixes."
tags:
  - documentation
---
<!--
SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamshome.family>
SPDX-License-Identifier: CC-BY-4.0
-->

> **Purpose**: Document issues discovered in this project that should be addressed in the [cookiecutter-python-template](https://github.com/ByronWilliamsCPA/cookiecutter-python-template).
>
> **Generated From**: cookiecutter-python-template v0.1.0
> **Project Created**: __PROJECT_CREATION_DATE__

---

## How to Use This File

When working on this project, if you discover any issue that originates from the template itself (not project-specific), add it here with the following format:

```markdown
### [Short Title]

- **Priority**: Critical / High / Medium / Low
- **Category**: [Configuration / Documentation / Tooling / Structure / CI/CD / Security / Other]
- **Discovered**: YYYY-MM-DD

**Issue**: [Clear description of what's wrong or missing]

**Context**: [How was this discovered? What were you trying to do?]

**Suggested Fix**: [What should the template do differently?]

**Affected Files**: [List template files that need changes]
```

---

## Feedback Items

<!-- Add your feedback below this line -->

### Python Syntax Error in sentry.py

- **Priority**: Critical
- **Category**: Tooling
- **Discovered**: 2025-12-04

**Issue**: `src/{package_name}/core/sentry.py` has a Python syntax error at line 71 that prevents code from parsing. The `except ImportError:` statement has incorrect indentation, appearing outside the `try:` block.

**Context**: Discovered during CI pipeline execution. Ruff formatter fails with "Expected a statement" error, and mkdocs build fails because griffe cannot parse the file for API documentation generation.

**Current Code** (lines 68-75):
```python
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        except ImportError:  # ❌ Wrong indentation - outside try block
        logger.warning(
            "Sentry SDK not installed. Install with: uv add sentry-sdk[fastapi]"
        )
        return
```

**Suggested Fix**: Correct the indentation of `except` to align with `try:`:

```python
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:  # ✅ Correct indentation
        logger.warning(
            "Sentry SDK not installed. Install with: uv add sentry-sdk[fastapi]"
        )
        return
```

**Affected Files**:
- `{{cookiecutter.project_slug}}/src/{{cookiecutter.package_name}}/core/sentry.py` (line 71)

**Impact**: Blocks CI pipeline, prevents documentation builds, fails Ruff formatting. This is a critical blocker for any project generated from the template.

---

### Dependency Review Workflow Configuration Error

- **Priority**: High
- **Category**: CI/CD
- **Discovered**: 2025-12-04

**Issue**: `.github/workflows/dependency-review.yml` contains conflicting configuration parameters that cause the GitHub Actions dependency review check to fail.

**Context**: Discovered during PR CI checks. The workflow fails with error: "You cannot specify both allow-licenses and deny-licenses"

**Current Configuration**:
```yaml
# The workflow appears to have both:
allow-licenses: [...]
deny-licenses: [...]
```

**Suggested Fix**: Choose one approach (either allow-list OR deny-list, not both):

**Option A - Allow-list approach (recommended for permissive projects)**:
```yaml
with:
  allow-licenses: MIT, Apache-2.0, BSD-3-Clause, BSD-2-Clause, ISC, GPL-3.0-or-later
  # Remove deny-licenses parameter
```

**Option B - Deny-list approach (recommended for restrictive policies)**:
```yaml
with:
  deny-licenses: AGPL-3.0, GPL-2.0-only, LGPL-3.0
  # Remove allow-licenses parameter
```

**Affected Files**:
- `{{cookiecutter.project_slug}}/.github/workflows/dependency-review.yml`

**Impact**: Prevents dependency security reviews from running, which is a critical security check for detecting vulnerable dependencies in PRs.

---

### REUSE Compliance: GPL-3.0 Deprecated License Warning

- **Priority**: Medium
- **Category**: Configuration
- **Discovered**: 2025-12-04

**Issue**: REUSE compliance check reports "Deprecated licenses: GPL-3.0" because the license identifier format has changed in SPDX 3.x specification.

**Context**: The REUSE 3.2 specification uses `GPL-3.0-or-later` or `GPL-3.0-only` instead of the deprecated `GPL-3.0` identifier.

**Current**: Template likely uses `GPL-3.0` in LICENSES/ directory or REUSE.toml

**Suggested Fix**: Update license identifier format:
```toml
# REUSE.toml (if GPL-3.0 is used)
[[annotations]]
path = "**"
SPDX-FileCopyrightText = "..."
SPDX-License-Identifier = "GPL-3.0-or-later"  # ✅ Not GPL-3.0
```

Or if using LICENSES/ directory:
- Rename `LICENSES/GPL-3.0.txt` → `LICENSES/GPL-3.0-or-later.txt`
- Update all file headers from `GPL-3.0` → `GPL-3.0-or-later`

**Affected Files**:
- `{{cookiecutter.project_slug}}/LICENSES/` (license files)
- `{{cookiecutter.project_slug}}/REUSE.toml` (if using bulk annotations)
- Any files with inline `SPDX-License-Identifier: GPL-3.0` headers

**Impact**: REUSE compliance check fails, preventing PR merges if this check is required. This affects legal compliance and open-source licensing clarity.

---

### ClusterFuzzLite Action Not Found

- **Priority**: Medium
- **Category**: CI/CD
- **Discovered**: 2025-12-04

**Issue**: The ClusterFuzzLite continuous fuzzing workflow fails with "An action could not be found at the URI" error, suggesting the action SHA reference is invalid or the repository is inaccessible.

**Context**: GitHub Actions cannot download the ClusterFuzzLite action from `google/clusterfuzzlite@f090cc7d581f82fb0e0b04f0c9e56ff7f4a24e76`

**Error**:
```
An action could not be found at the URI 'https://api.github.com/repos/google/clusterfuzzlite/tarball/f090cc7d581f82fb0e0b04f0c9e56ff7f4a24e76'
```

**Suggested Fix**:

**Option A - Update to latest stable version**:
```yaml
# Use latest stable tag instead of specific SHA
- uses: google/clusterfuzzlite@v1
```

**Option B - Verify SHA is valid**:
- Check if the SHA `f090cc7d581f82fb0e0b04f0c9e56ff7f4a24e76` exists in google/clusterfuzzlite
- If not, update to a valid commit SHA from the main branch

**Option C - Make fuzzing optional**:
```yaml
# Add continue-on-error for non-critical fuzzing
- uses: google/clusterfuzzlite@v1
  continue-on-error: true  # Don't block PR on fuzzing failures
```

**Affected Files**:
- `{{cookiecutter.project_slug}}/.github/workflows/fuzzing.yml` (or similar)

**Impact**: Prevents continuous fuzzing from running. While fuzzing is valuable for security, this shouldn't block documentation-only PRs. Consider making fuzzing non-blocking or conditional on code changes.

---

### Missing REUSE Copyright Headers in Generated Planning Documents

- **Priority**: Low
- **Category**: Documentation
- **Discovered**: 2025-12-04

**Issue**: Planning document placeholders in `docs/planning/` don't include REUSE-compliant copyright headers, causing REUSE compliance failures when files are first generated.

**Context**: Template includes placeholder files like `docs/planning/project-vision.md`, `docs/planning/tech-spec.md`, etc. with YAML front matter but no REUSE headers. When these are generated, they fail REUSE compliance checks showing "14 files missing copyright/licensing information."

**Current**: Placeholder files have only YAML front matter, no REUSE headers

**Suggested Fix**: Add REUSE headers to all planning document templates:

```markdown
---
title: "Audio Processor - Project Vision & Scope"
schema_type: planning
status: draft
# SPDX-FileCopyrightText: {{cookiecutter.author_name}} <{{cookiecutter.author_email}}>
# SPDX-License-Identifier: {{cookiecutter.license}}
---
```

Or use bulk annotations in `.reuse/dep5`:
```
Files: docs/planning/*.md docs/planning/adr/*.md
Copyright: {{cookiecutter.author_name}} <{{cookiecutter.author_email}}>
License: {{cookiecutter.license}}
```

**Affected Files**:
- All files in `{{cookiecutter.project_slug}}/docs/planning/`
- `{{cookiecutter.project_slug}}/.reuse/dep5` (bulk annotation alternative)

**Impact**: Low severity (doesn't block development), but causes REUSE compliance failures on first PR. Adding headers or dep5 annotations would make initial project setup cleaner.

---

### Invalid setup-uv Action SHA in FIPS Workflow

- **Priority**: High
- **Category**: CI/CD
- **Discovered**: 2025-12-04

**Issue**: FIPS compliance workflow fails because the `astral-sh/setup-uv` action SHA reference is invalid or outdated.

**Context**: GitHub Actions cannot download the setup-uv action from the specified SHA `582b2d78a0f5913301dcc87c4e93301fdd2b6711`

**Error**:
```
An action could not be found at the URI 'https://api.github.com/repos/astral-sh/setup-uv/tarball/582b2d78a0f5913301dcc87c4e93301fdd2b6711'
```

**Suggested Fix**:
```yaml
# Use latest stable version tag instead of SHA
- uses: astral-sh/setup-uv@v5  # or current latest version
```

**Affected Files**:
- `{{cookiecutter.project_slug}}/.github/workflows/fips-compliance.yml`

**Impact**: Blocks FIPS compliance checks which are important for government/healthcare deployments. This affects projects that need to validate FIPS 140-2/140-3 compatibility.

---

### Python Compatibility Matrix Output Format Error

- **Priority**: High
- **Category**: CI/CD (Reusable Workflow)
- **Discovered**: 2025-12-04
- **Updated**: 2025-12-06

**Issue**: Python compatibility matrix workflow fails in the "Build Test Matrix" step with malformed JSON output from the reusable workflow.

**Context**: The local workflow calls `ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml@main` which produces invalid JSON in the matrix output step.

**Error**:
```
##[error]Unable to process file command 'output' successfully.
##[error]Invalid format '  "python": ['
jq: parse error: Unfinished JSON term at EOF at line 2, column 0
```

**Root Cause**: Issue is in the **org-level reusable workflow** (`ByronWilliamsCPA/.github`), not the project-level template. The matrix generation logic in the reusable workflow has malformed JSON output.

**Suggested Fix**: Fix the reusable workflow at `ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml`:

```yaml
# Ensure proper JSON array formatting in GITHUB_OUTPUT
- id: set-matrix
  run: |
    # Generate valid JSON without line breaks or invalid formatting
    MATRIX=$(jq -nc --arg pythons "${{ inputs.python-versions }}" \
                     --arg oses "${{ inputs.operating-systems }}" \
      '{
        python: ($pythons | fromjson),
        os: ($oses | fromjson)
      }')
    echo "matrix=$MATRIX" >> $GITHUB_OUTPUT
```

### Affected Files

- `ByronWilliamsCPA/.github/.github/workflows/python-compatibility.yml` (org-level reusable workflow)
- Projects calling this workflow will fail until fixed upstream

**Impact**: Prevents multi-Python version testing for ALL projects using the org-level reusable workflow. This is a critical blocker affecting the entire organization's CI infrastructure, not just template-generated projects.

**Workaround**: Until fixed, disable or skip python-compatibility workflow in project CI.

---

### Pre-existing Ruff Linting Errors in Template Files

- **Priority**: High
- **Category**: Code Quality
- **Discovered**: 2025-12-04

**Issue**: Multiple template-generated Python files contain Ruff linting violations that block CI, including unused imports, commented code, timezone issues, and PyStrict rule violations.

**Context**: Discovered during CI pipeline execution. Ruff check fails with 38+ linting errors across cache.py, sentry.py, and worker.py files that are generated from the template.

**Errors in Template Files:**

**src/{package_name}/core/sentry.py** (13 errors):
- `F401`: Unused import `collections.abc.Callable`
- `PLC0415` (multiple): Import statements inside functions (6 occurrences)
- `S607`: Partial executable path in subprocess
- `TRY300` (2x): Statements should be in else blocks
- `S110`: try-except-pass without logging
- `BLE001`: Blind except catching `Exception`
- `RUF059`: Unpacked variable never used
- `ARG001`: Unused function argument
- `SIM102`: Nested if statements should be combined

**src/{package_name}/core/cache.py** (1 error):
- `TRY400`: Should use `logging.exception` instead of `logging.error`

**src/{package_name}/jobs/worker.py** (24 errors):
- `ARG001` (8x): Unused function arguments (ctx, body, data)
- `DTZ003` (3x): `datetime.datetime.utcnow()` without timezone
- `ERA001` (7x): Commented-out code
- `TRY400`: Should use `logging.exception`
- `RUF012` (2x): Mutable class attributes need `ClassVar` annotation

**Suggested Fix**: Clean up all template files to pass Ruff checks with PyStrict-aligned rules:

1. Remove unused imports
2. Move imports to module top-level (or suppress PLC0415 for optional dependencies)
3. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
4. Remove commented-out code or use proper # noqa comments
5. Add `ClassVar` annotations to mutable class attributes
6. Use `logging.exception()` for logging in except blocks
7. Prefix unused args with underscore: `_ctx`, `_body`, `_data`

**Affected Files**:
- `{{cookiecutter.project_slug}}/src/{{cookiecutter.package_name}}/core/sentry.py`
- `{{cookiecutter.project_slug}}/src/{{cookiecutter.package_name}}/core/cache.py`
- `{{cookiecutter.project_slug}}/src/{{cookiecutter.package_name}}/jobs/worker.py`

**Impact**: Blocks CI pipeline on ALL projects generated from template. Code Quality Checks fail immediately, preventing merges and blocking development workflow. This is a critical blocker affecting template usability.

---

### Organization Reusable Workflows Experiencing startup_failure

- **Priority**: Critical
- **Category**: CI/CD (Organization Workflows)
- **Discovered**: 2025-12-06

**Issue**: Multiple organization-level reusable workflows are experiencing `startup_failure` errors, preventing CI checks from running on ALL projects that use them.

**Context**: During PR CI pipeline execution, three critical org-level workflows fail with `startup_failure` status before any jobs can start:

1. **Security Analysis** (`python-security-analysis.yml@main`) - ID: 19984575923
2. **SBOM & Security Scan** (`python-sbom.yml@main`) - ID: 19984575931
3. **PR Validation** (`python-pr-validation.yml@main`) - ID: 19984575936

**Error Symptoms**:

- Workflow status: `startup_failure`
- No logs available (`gh run view <id> --log` returns "log not found")
- Workflows fail before any jobs execute
- All recent runs show same failure pattern

**Affected Workflows in ByronWilliamsCPA/.github**:
- `.github/workflows/python-security-analysis.yml`
- `.github/workflows/python-sbom.yml`
- `.github/workflows/python-pr-validation.yml`

**Calling Pattern** (from project workflows):

```yaml
jobs:
  security:
    uses: ByronWilliamsCPA/.github/.github/workflows/python-security-analysis.yml@main
    with:
      source-directory: 'src'
      python-version: '3.12'
      # ... other inputs
```

**Possible Causes**:

1. **Syntax error** in the reusable workflow YAML
2. **Invalid action reference** within the workflow
3. **Missing required secrets/inputs** not properly defined
4. **Recent breaking change** to workflow syntax or GitHub Actions runtime

**Suggested Investigation Steps**:

1. Validate YAML syntax in all three org workflows
2. Check for invalid action references (wrong SHAs, deprecated actions)
3. Verify `workflow_call` input definitions match what callers provide
4. Check GitHub Actions status page for platform issues
5. Review recent commits to org workflows for breaking changes

**Impact**: CRITICAL - Blocks all security scanning, SBOM generation, and PR validation for ALL projects in the organization. This affects:

- Security vulnerability detection
- Dependency scanning
- License compliance
- PR quality checks
- Conventional commit enforcement

**Workaround**: Projects cannot fix this locally as the issue is in org-level reusable workflows. Must be fixed in `ByronWilliamsCPA/.github` repository.

---

## Submitting Feedback

Once you've collected feedback, you can:

1. **Create an issue** in the [cookiecutter-python-template repository](https://github.com/ByronWilliamsCPA/cookiecutter-python-template/issues)
2. **Submit a PR** if you have fixes for the template
3. **Share this file** with the template maintainers

When submitting, reference this project as the source of the feedback.

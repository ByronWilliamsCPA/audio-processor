---
title: "Development Setup"
schema_type: common
status: published
owner: core-maintainer
purpose: "Complete development environment setup guide for Audio Processor."
tags:
  - development
  - guide
---

This guide walks you through setting up a complete development environment for Audio Processor.

## Prerequisites

### Required

- **Python 3.12+** - [Download Python](https://www.python.org/downloads/)
- **UV** - Fast Python package manager
- **Git** - Version control
- **Docker & Docker Compose** - For Redis and containerized development

### Optional

- **FFmpeg** - Required for local audio processing (included in Docker)
- **Redis** - Can run locally or via Docker

## Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/ByronWilliamsCPA/audio-processor.git
cd audio-processor

# 2. Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies (includes audio processing stack)
uv sync --all-extras

# 4. Install pre-commit hooks
uv run pre-commit install

# 5. Copy environment template
cp .env.example .env
# Edit .env and add your DEEPGRAM_API_KEY

# 6. Run tests to verify setup
uv run pytest tests/ -v
```

## Detailed Setup

### Step 1: Install UV Package Manager

UV is a fast Python package manager that replaces pip/poetry/pipenv.

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip/pipx
pip install uv
```

Verify installation:

```bash
uv --version
# Should show: uv 0.x.x
```

### Step 2: Clone and Install Dependencies

```bash
# Clone repository
git clone https://github.com/ByronWilliamsCPA/audio-processor.git
cd audio-processor

# Install all dependencies including audio processing stack
uv sync --all-extras

# This installs:
# - Core dependencies (pydantic, structlog, click)
# - Audio processing (librosa, pydub, ffmpeg-python, soundfile, silero-vad)
# - ASR (deepgram-sdk)
# - Job queue (redis, rq)
# - Development tools (pytest, ruff, basedpyright)
```

### Step 3: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Deepgram API key
# Get one from: https://console.deepgram.com/
```

**Minimum required configuration:**

```bash
DEEPGRAM_API_KEY=your-api-key-here
```

### Step 4: Set Up Pre-commit Hooks

```bash
uv run pre-commit install
```

This installs hooks that run on every commit:
- Code formatting (Ruff)
- Linting (Ruff)
- Type checking (BasedPyright)
- Security scanning (Bandit, TruffleHog)

### Step 5: Verify Setup

```bash
# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check src/

# Run type checking
uv run basedpyright src/

# Start the API locally
uv run uvicorn audio_processor.api:app --reload
# Visit http://localhost:8000/docs
```

## Docker Development Environment

For a complete development stack with Redis:

```bash
# Start all services (app, redis, worker)
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps

# Stop services
docker-compose down
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| app | 8000 | FastAPI API server |
| redis | 6379 | Job queue and caching |
| worker | - | Background job processor |

### Rebuilding After Changes

```bash
# Rebuild after dependency changes
docker-compose up -d --build

# Rebuild specific service
docker-compose up -d --build app
```

## Troubleshooting

### UV Issues

**Problem: `uv: command not found`**

```bash
# Add UV to your PATH
export PATH="$HOME/.cargo/bin:$PATH"

# Or reinstall
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Problem: `uv sync` fails with lock file errors**

```bash
# Regenerate lock file
uv lock

# Then sync
uv sync --all-extras
```

### Pre-commit Issues

**Problem: Pre-commit hooks failing**

```bash
# Run hooks manually to see detailed errors
uv run pre-commit run --all-files

# Clean and reinstall hooks
uv run pre-commit clean
uv run pre-commit install --install-hooks
```

### Import Errors

**Problem: `ModuleNotFoundError: No module named 'librosa'`**

```bash
# Ensure you installed with --all-extras
uv sync --all-extras

# Verify audio packages are installed
uv run python -c "import librosa, pydub, soundfile; print('OK')"
```

### FFmpeg Issues

**Problem: `pydub` warning about FFmpeg**

FFmpeg is required for audio format conversion. Options:

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Or use Docker (FFmpeg is included)
docker-compose up -d
```

### Docker Issues

**Problem: Services not starting**

```bash
# Check service status
docker-compose ps

# View logs for specific service
docker-compose logs app
docker-compose logs redis

# Reset everything
docker-compose down -v
docker-compose up -d --build
```

**Problem: Port already in use**

```bash
# Check what's using the port
lsof -i :8000
lsof -i :6379

# Use different ports in .env
APP_PORT=8001
REDIS_PORT=6380
```

### Redis Connection Issues

**Problem: Cannot connect to Redis**

```bash
# If using Docker
docker-compose ps  # Check redis is running

# If running locally
redis-cli ping  # Should return PONG

# Check connection string
echo $REDIS_URL
```

### Type Checking Issues

**Problem: BasedPyright shows many errors**

```bash
# Run type checking
uv run basedpyright src/

# Errors vs Warnings:
# - Errors (0 expected): Must be fixed
# - Warnings: Can be ignored during development
```

### Test Failures

**Problem: Tests fail with import errors**

```bash
# Ensure you're using uv run
uv run pytest tests/ -v

# Not just pytest directly
pytest tests/  # This might use wrong environment
```

## Development Workflow

### Daily Development

```bash
# 1. Pull latest changes
git pull origin main

# 2. Update dependencies if needed
uv sync --all-extras

# 3. Create feature branch
git checkout -b feat/your-feature

# 4. Make changes, run tests
uv run pytest tests/ -v

# 5. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: your feature description"

# 6. Push and create PR
git push -u origin feat/your-feature
```

### Running Specific Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/unit/test_api.py -v

# Run specific test
uv run pytest tests/unit/test_api.py::TestHealthEndpoint -v

# Run with coverage
uv run pytest tests/ --cov=src/audio_processor --cov-report=html
```

### Code Quality Checks

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check . --fix

# Type check
uv run basedpyright src/

# Security scan
uv run bandit -r src/

# All checks at once
uv run pre-commit run --all-files
```

## IDE Setup

### VS Code

Install recommended extensions:
- Python
- Pylance (or Pyright)
- Ruff

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.analysis.typeCheckingMode": "strict",
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm

1. Set Python interpreter to `.venv/bin/python`
2. Enable Ruff plugin
3. Configure BasedPyright for type checking

## Next Steps

- [Configuration Guide](../guides/configuration.md) - Environment variables and settings
- [Contributing Guide](./contributing.md) - How to contribute
- [Testing Guide](./testing.md) - Writing and running tests
- [Architecture](./architecture.md) - System design overview

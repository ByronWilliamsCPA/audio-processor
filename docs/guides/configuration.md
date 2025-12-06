---
title: "Configuration"
schema_type: common
status: published
owner: core-maintainer
purpose: "Configuration guide for Audio Processor."
tags:
  - guide
  - configuration
---

This guide covers all configuration options for Audio Processor.

## Quick Start

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
# Edit .env with your settings
```

## Environment Variables

### Core Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ENVIRONMENT` | Environment name (development, staging, production) | `development` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `JSON_LOGS` | Enable JSON log format for production | `false` | No |

### Deepgram API (Required for Transcription)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEEPGRAM_API_KEY` | Deepgram API key from console.deepgram.com | - | **Yes** |
| `DEEPGRAM_MODEL` | ASR model (nova-2, nova, enhanced, base) | `nova-2` | No |
| `DEEPGRAM_DIARIZE` | Enable speaker diarization | `true` | No |
| `DEEPGRAM_SMART_FORMAT` | Enable smart formatting | `true` | No |
| `DEEPGRAM_SUMMARIZE` | Enable summarization | `true` | No |

### Redis (Job Queue)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` | No |
| `REDIS_PORT` | Redis port (for Docker) | `6379` | No |

### Application

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `APP_PORT` | API server port | `8000` | No |
| `AUDIO_TEMP_DIR` | Temp directory for audio processing | `/app/temp` | No |

### Monitoring (Optional)

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SENTRY_DSN` | Sentry error tracking DSN | - | No |
| `SENTRY_ENVIRONMENT` | Sentry environment tag | `development` | No |
| `SENTRY_TRACES_SAMPLE_RATE` | Performance monitoring sample rate | `0.1` | No |

## Configuration File

Create a `.env` file in your project root:

```bash
# =============================================================================
# Required Settings
# =============================================================================

# Deepgram API Key (get from https://console.deepgram.com/)
DEEPGRAM_API_KEY=your-deepgram-api-key-here

# =============================================================================
# Optional Settings (defaults shown)
# =============================================================================

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
JSON_LOGS=false

# Deepgram Options
DEEPGRAM_MODEL=nova-2
DEEPGRAM_DIARIZE=true
DEEPGRAM_SMART_FORMAT=true
DEEPGRAM_SUMMARIZE=true

# Redis (use defaults for Docker Compose)
REDIS_URL=redis://localhost:6379/0

# Application
APP_PORT=8000
```

## Docker Compose Configuration

When using Docker Compose, the services are pre-configured:

```yaml
# Redis is available at redis://redis:6379/0
# App runs on port 8000
# Worker connects to same Redis instance
```

Override settings in your `.env` file - Docker Compose reads them automatically.

## Pydantic Settings

Configuration is managed via Pydantic Settings for type safety:

```python
from audio_processor.core.config import settings

# Access settings
print(settings.log_level)
print(settings.environment)
```

## Development vs Production

### Development

```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
JSON_LOGS=false
SENTRY_TRACES_SAMPLE_RATE=1.0
```

### Production

```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
JSON_LOGS=true
SENTRY_DSN=https://your-sentry-dsn
SENTRY_TRACES_SAMPLE_RATE=0.1
```

## Getting a Deepgram API Key

1. Go to [console.deepgram.com](https://console.deepgram.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key with appropriate permissions
5. Copy the key to your `.env` file

**Note**: Deepgram offers $200 free credit for new accounts.

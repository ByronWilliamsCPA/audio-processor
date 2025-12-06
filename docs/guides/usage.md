---
title: "Usage"
schema_type: common
status: published
owner: core-maintainer
purpose: "Usage guide for Audio Processor."
tags:
  - guide
  - usage
---

This guide covers common usage patterns for Audio Processor.

## Installation

### From PyPI

```bash
pip install audio-processor
```

### From Source

```bash
git clone https://github.com/ByronWilliamsCPA/audio-processor
cd audio_processor
uv sync --all-extras
```

## Command Line Interface

### Available Commands

```bash
# Show help
audio_processor --help

# Hello command
audio_processor hello --name "World"

# Show configuration
audio_processor config
```

### Debug Mode

Enable debug logging:

```bash
audio_processor --debug hello --name "Test"
```

## Library Usage

### Basic Import

```python
from audio_processor import __version__

print(f"Version: {__version__}")
```

### Logging

```python
from audio_processor.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging(level="DEBUG", json_logs=False)

# Get a logger
logger = get_logger(__name__)
logger.info("Hello from Audio Processor")
```

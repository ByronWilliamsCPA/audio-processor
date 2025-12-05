"""Core configuration, settings, and exception modules."""

from audio_processor.core.config import Settings
from audio_processor.core.exceptions import (
    APIError,
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    ProjectBaseError,
    ResourceNotFoundError,
    ValidationError,
)

__all__ = [
    # Exceptions (sorted alphabetically)
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "BusinessLogicError",
    "ConfigurationError",
    "DatabaseError",
    "ExternalServiceError",
    "ProjectBaseError",
    "ResourceNotFoundError",
    # Configuration
    "Settings",
    "ValidationError",
]

"""Tests for Sentry error tracking integration."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from audio_processor.core.sentry import (
    add_breadcrumb,
    before_breadcrumb_hook,
    before_send_hook,
    capture_exception,
    capture_message,
    init_sentry,
    set_user_context,
)


@pytest.fixture
def mock_sentry_sdk():
    """Create a mock sentry_sdk module."""
    mock_sdk = MagicMock()
    mock_logging_module = MagicMock()

    # Set up the module structure
    mock_sdk.integrations = MagicMock()
    mock_sdk.integrations.logging = mock_logging_module
    mock_logging_module.LoggingIntegration = MagicMock()

    # Mock push_scope context manager
    mock_scope = MagicMock()
    mock_sdk.push_scope.return_value.__enter__.return_value = mock_scope
    mock_sdk.push_scope.return_value.__exit__.return_value = None

    with patch.dict(
        sys.modules,
        {
            "sentry_sdk": mock_sdk,
            "sentry_sdk.integrations": mock_sdk.integrations,
            "sentry_sdk.integrations.logging": mock_logging_module,
        },
    ):
        yield mock_sdk


class TestInitSentry:
    """Tests for init_sentry function."""

    def test_init_sentry_without_dsn(self) -> None:
        """Test init_sentry returns early when DSN not provided."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("audio_processor.core.sentry.logger.info") as mock_logger,
        ):
            init_sentry()

            # Should log that Sentry is disabled
            mock_logger.assert_called_once()
            assert "SENTRY_DSN not set" in str(mock_logger.call_args)

    def test_init_sentry_without_sdk_installed(self) -> None:
        """Test init_sentry handles missing sentry_sdk gracefully."""
        with (
            patch.dict("os.environ", {"SENTRY_DSN": "https://test@sentry.io/123"}),
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch("audio_processor.core.sentry.logger.warning") as mock_logger,
        ):
            init_sentry()

            # Should log warning about missing SDK
            mock_logger.assert_called_once()
            assert "Sentry SDK not installed" in str(mock_logger.call_args)

    def test_init_sentry_with_dsn(self, mock_sentry_sdk: MagicMock) -> None:
        """Test init_sentry initializes Sentry with DSN."""
        test_dsn = "https://test@sentry.io/123"

        with (
            patch.dict("os.environ", {"SENTRY_DSN": test_dsn}),
            patch("audio_processor.core.sentry.logger.info"),
        ):
            init_sentry()

            # Verify sentry_sdk.init was called
            mock_sentry_sdk.init.assert_called_once()
            call_kwargs = mock_sentry_sdk.init.call_args[1]

            assert call_kwargs["dsn"] == test_dsn
            assert call_kwargs["sample_rate"] == pytest.approx(1.0)
            assert call_kwargs["attach_stacktrace"] is True
            assert call_kwargs["send_default_pii"] is False

    def test_init_sentry_custom_parameters(self, mock_sentry_sdk: MagicMock) -> None:
        """Test init_sentry with custom parameters."""
        test_dsn = "https://test@sentry.io/123"
        test_env = "staging"
        test_release = "v1.0.0"

        with patch("audio_processor.core.sentry.logger.info"):
            init_sentry(
                dsn=test_dsn,
                environment=test_env,
                release=test_release,
                traces_sample_rate=0.5,
                profiles_sample_rate=0.2,
                enable_tracing=True,
                enable_profiling=True,
                debug=True,
            )

            call_kwargs = mock_sentry_sdk.init.call_args[1]

            assert call_kwargs["dsn"] == test_dsn
            assert call_kwargs["environment"] == test_env
            assert call_kwargs["release"] == test_release
            assert call_kwargs["traces_sample_rate"] == pytest.approx(0.5)
            assert call_kwargs["profiles_sample_rate"] == pytest.approx(0.2)
            assert call_kwargs["debug"] is True

    def test_init_sentry_environment_from_env(self, mock_sentry_sdk: MagicMock) -> None:
        """Test init_sentry reads environment from env vars."""
        test_dsn = "https://test@sentry.io/123"
        test_env = "production"

        with (
            patch.dict("os.environ", {"SENTRY_DSN": test_dsn, "SENTRY_ENVIRONMENT": test_env}),
            patch("audio_processor.core.sentry.logger.info"),
        ):
            init_sentry()

            call_kwargs = mock_sentry_sdk.init.call_args[1]
            assert call_kwargs["environment"] == test_env

    def test_init_sentry_tracing_disabled(self, mock_sentry_sdk: MagicMock) -> None:
        """Test init_sentry with tracing disabled."""
        test_dsn = "https://test@sentry.io/123"

        with patch("audio_processor.core.sentry.logger.info"):
            init_sentry(dsn=test_dsn, enable_tracing=False, enable_profiling=False)

            call_kwargs = mock_sentry_sdk.init.call_args[1]
            assert call_kwargs["traces_sample_rate"] == pytest.approx(0.0)
            assert call_kwargs["profiles_sample_rate"] == pytest.approx(0.0)


class TestBeforeSendHook:
    """Tests for before_send_hook function."""

    def test_before_send_filters_keyboard_interrupt(self) -> None:
        """Test before_send_hook filters out KeyboardInterrupt."""
        event = {"message": "test"}
        hint = {"exc_info": (KeyboardInterrupt, KeyboardInterrupt(), None)}

        result = before_send_hook(event, hint)

        assert result is None

    def test_before_send_filters_system_exit(self) -> None:
        """Test before_send_hook filters out SystemExit."""
        event = {"message": "test"}
        hint = {"exc_info": (SystemExit, SystemExit(), None)}

        result = before_send_hook(event, hint)

        assert result is None

    def test_before_send_scrubs_sensitive_data(self) -> None:
        """Test before_send_hook scrubs sensitive data from requests."""
        event = {
            "request": {
                "data": {
                    "username": "testuser",
                    "password": "secret123",
                    "token": "abc123",
                    "api_key": "key456",
                    "secret": "shh",
                }
            }
        }
        hint = {}

        result = before_send_hook(event, hint)

        assert result is not None
        assert result["request"]["data"]["username"] == "testuser"
        assert result["request"]["data"]["password"] == "[REDACTED]"
        assert result["request"]["data"]["token"] == "[REDACTED]"
        assert result["request"]["data"]["api_key"] == "[REDACTED]"
        assert result["request"]["data"]["secret"] == "[REDACTED]"

    def test_before_send_passes_normal_exceptions(self) -> None:
        """Test before_send_hook passes normal exceptions through."""
        event = {"message": "test error"}
        hint = {"exc_info": (ValueError, ValueError("test"), None)}

        result = before_send_hook(event, hint)

        assert result == event

    def test_before_send_no_exc_info(self) -> None:
        """Test before_send_hook when no exc_info in hint."""
        event = {"message": "test"}
        hint = {}

        result = before_send_hook(event, hint)

        assert result == event


class TestBeforeBreadcrumbHook:
    """Tests for before_breadcrumb_hook function."""

    def test_before_breadcrumb_filters_query_params(self) -> None:
        """Test before_breadcrumb_hook filters query parameters."""
        crumb = {
            "category": "httplib",
            "data": {
                "url": "https://example.com/api",
                "query": "?token=secret&user=123",
            },
        }
        hint = {}

        result = before_breadcrumb_hook(crumb, hint)

        assert result is not None
        assert result["data"]["query"] == "[FILTERED]"

    def test_before_breadcrumb_passes_non_http(self) -> None:
        """Test before_breadcrumb_hook passes non-HTTP breadcrumbs."""
        crumb = {
            "category": "custom",
            "message": "test event",
        }
        hint = {}

        result = before_breadcrumb_hook(crumb, hint)

        assert result == crumb

    def test_before_breadcrumb_no_data(self) -> None:
        """Test before_breadcrumb_hook when httplib has no data."""
        crumb = {"category": "httplib"}
        hint = {}

        result = before_breadcrumb_hook(crumb, hint)

        assert result == crumb


class TestCaptureException:
    """Tests for capture_exception function."""

    def test_capture_exception_success(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_exception sends exception to Sentry."""
        test_exception = ValueError("test error")
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_exception(test_exception)

        mock_sentry_sdk.push_scope.assert_called_once()
        assert mock_scope.level == "error"
        mock_sentry_sdk.capture_exception.assert_called_once_with(test_exception)

    def test_capture_exception_with_tags(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_exception with custom tags."""
        test_exception = ValueError("test error")
        tags = {"api": "v1", "user_type": "premium"}
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_exception(test_exception, tags=tags)

        mock_scope.set_tag.assert_any_call("api", "v1")
        mock_scope.set_tag.assert_any_call("user_type", "premium")

    def test_capture_exception_with_extra(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_exception with extra context."""
        test_exception = ValueError("test error")
        extra = {"file_size": 1024, "row_count": 100}
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_exception(test_exception, extra=extra)

        mock_scope.set_extra.assert_any_call("file_size", 1024)
        mock_scope.set_extra.assert_any_call("row_count", 100)

    def test_capture_exception_custom_level(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_exception with custom level."""
        test_exception = ValueError("test error")
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_exception(test_exception, level="warning")

        assert mock_scope.level == "warning"

    def test_capture_exception_sdk_not_installed(self) -> None:
        """Test capture_exception handles missing SDK gracefully."""
        test_exception = ValueError("test error")

        with (
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch("audio_processor.core.sentry.logger.warning") as mock_logger,
        ):
            # Should not raise an error
            capture_exception(test_exception)

            mock_logger.assert_called_once()


class TestCaptureMessage:
    """Tests for capture_message function."""

    def test_capture_message_success(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_message sends message to Sentry."""
        test_message = "User completed onboarding"
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_message(test_message)

        mock_sentry_sdk.push_scope.assert_called_once()
        assert mock_scope.level == "info"
        mock_sentry_sdk.capture_message.assert_called_once_with(test_message)

    def test_capture_message_with_tags(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_message with custom tags."""
        test_message = "Task completed"
        tags = {"task_type": "export"}
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_message(test_message, tags=tags)

        mock_scope.set_tag.assert_called_once_with("task_type", "export")

    def test_capture_message_custom_level(self, mock_sentry_sdk: MagicMock) -> None:
        """Test capture_message with custom level."""
        test_message = "Warning message"
        mock_scope = mock_sentry_sdk.push_scope.return_value.__enter__.return_value

        capture_message(test_message, level="warning")

        assert mock_scope.level == "warning"

    def test_capture_message_sdk_not_installed(self) -> None:
        """Test capture_message handles missing SDK gracefully."""
        with (
            patch.dict(sys.modules, {"sentry_sdk": None}),
            patch("audio_processor.core.sentry.logger.warning") as mock_logger,
        ):
            capture_message("test message")

            mock_logger.assert_called_once()


class TestSetUserContext:
    """Tests for set_user_context function."""

    def test_set_user_context_all_fields(self, mock_sentry_sdk: MagicMock) -> None:
        """Test set_user_context with all fields."""
        set_user_context(
            user_id="user_123",
            email="test@example.com",
            username="testuser",
            subscription="premium",
        )

        expected_data = {
            "id": "user_123",
            "email": "test@example.com",
            "username": "testuser",
            "subscription": "premium",
        }
        mock_sentry_sdk.set_user.assert_called_once_with(expected_data)

    def test_set_user_context_partial_fields(self, mock_sentry_sdk: MagicMock) -> None:
        """Test set_user_context with partial fields."""
        set_user_context(user_id="user_123")

        expected_data = {"id": "user_123"}
        mock_sentry_sdk.set_user.assert_called_once_with(expected_data)

    def test_set_user_context_custom_kwargs(self, mock_sentry_sdk: MagicMock) -> None:
        """Test set_user_context with custom kwargs."""
        set_user_context(user_id="user_123", custom_field="value", role="admin")

        call_args = mock_sentry_sdk.set_user.call_args[0][0]
        assert call_args["id"] == "user_123"
        assert call_args["custom_field"] == "value"
        assert call_args["role"] == "admin"

    def test_set_user_context_sdk_not_installed(self) -> None:
        """Test set_user_context handles missing SDK gracefully."""
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            # Should not raise an error
            set_user_context(user_id="user_123")


class TestAddBreadcrumb:
    """Tests for add_breadcrumb function."""

    def test_add_breadcrumb_success(self, mock_sentry_sdk: MagicMock) -> None:
        """Test add_breadcrumb adds breadcrumb to Sentry."""
        add_breadcrumb(
            message="User clicked export",
            category="ui",
            level="info",
            data={"format": "csv", "row_count": 1000},
        )

        mock_sentry_sdk.add_breadcrumb.assert_called_once_with(
            message="User clicked export",
            category="ui",
            level="info",
            data={"format": "csv", "row_count": 1000},
        )

    def test_add_breadcrumb_default_values(self, mock_sentry_sdk: MagicMock) -> None:
        """Test add_breadcrumb with default values."""
        add_breadcrumb(message="Test event")

        call_kwargs = mock_sentry_sdk.add_breadcrumb.call_args[1]
        assert call_kwargs["message"] == "Test event"
        assert call_kwargs["category"] == "custom"
        assert call_kwargs["level"] == "info"
        assert call_kwargs["data"] == {}

    def test_add_breadcrumb_sdk_not_installed(self) -> None:
        """Test add_breadcrumb handles missing SDK gracefully."""
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            # Should not raise an error
            add_breadcrumb(message="test")


class TestGetReleaseVersion:
    """Tests for _get_release_version helper."""

    def test_get_release_version_from_git(self) -> None:
        """Test _get_release_version gets version from git."""
        from audio_processor.core.sentry import _get_release_version

        with patch("subprocess.check_output", return_value=b"abc123\n"):
            version = _get_release_version()

            assert version == "audio_processor@abc123"

    def test_get_release_version_from_package(self) -> None:
        """Test _get_release_version gets version from package."""
        from audio_processor.core.sentry import _get_release_version

        with (
            patch("subprocess.check_output", side_effect=FileNotFoundError),
            patch("importlib.metadata.version", return_value="1.2.3"),
        ):
            version = _get_release_version()

            assert version == "audio_processor@1.2.3"

    def test_get_release_version_fallback(self) -> None:
        """Test _get_release_version falls back to default."""
        from audio_processor.core.sentry import _get_release_version

        with (
            patch("subprocess.check_output", side_effect=FileNotFoundError),
            patch("importlib.metadata.version", side_effect=Exception),
        ):
            version = _get_release_version()

            assert version == "audio_processor@0.1.0"

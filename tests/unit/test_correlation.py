"""Placeholder tests when API framework is not enabled.

The correlation middleware is only available when include_api_framework=yes.
"""

import pytest


class TestCorrelationNotAvailable:
    """Tests verifying correlation module behavior when API framework disabled."""

    @pytest.mark.unit
    def test_placeholder(self) -> None:
        """Placeholder test when correlation middleware not available."""
        # Correlation middleware is not available in this configuration
        assert True

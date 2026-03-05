"""Configure tests."""

from aioresponses import aioresponses
import pytest

pytest_plugins = ["pytest_cov"]
pytest_plugins.append("tests.fixtures.connection")


@pytest.fixture
def mock_aiohttp():
    """Provide an aioresponses context manager for mocking aiohttp requests."""
    with aioresponses() as m:
        yield m

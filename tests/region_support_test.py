"""Test region detection and configuration."""
import pytest
from unittest.mock import AsyncMock, Mock, patch
from aiohttp import ClientSession
from volkswagencarnet.vw_const import (
    get_region_from_country,
    get_region_config,
)
from volkswagencarnet.vw_connection import Connection


class TestRegionMapping:
    """Test region detection from country codes."""

    def test_us_maps_to_na(self):
        assert get_region_from_country("US") == "NA"
        assert get_region_from_country("us") == "NA"  # Case insensitive

    def test_canada_maps_to_na(self):
        assert get_region_from_country("CA") == "NA"

    def test_germany_maps_to_emea(self):
        assert get_region_from_country("DE") == "EMEA"

    def test_france_maps_to_emea(self):
        assert get_region_from_country("FR") == "EMEA"

    def test_unknown_country_defaults_to_emea(self):
        assert get_region_from_country("XX") == "EMEA"

    def test_emea_config_has_base_api(self):
        config = get_region_config("EMEA")
        assert config["base_api"] == "https://emea.bff.cariad.digital"
        assert config["homeregion"] == "https://msg.volkswagen.de"

    def test_na_config_has_candidates(self):
        config = get_region_config("NA")
        assert "base_api_candidates" in config
        assert len(config["base_api_candidates"]) > 0
        assert config["base_api"] is None  # Not yet discovered


class TestConnectionRegionDetection:
    """Test Connection class region detection."""

    @pytest.mark.asyncio
    async def test_connection_defaults_to_emea(self):
        """No country parameter should default to EMEA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password")
            assert conn._session_region == "EMEA"
            assert conn._session_country == "DE"
            assert conn._base_api == "https://emea.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_connection_with_de_country(self):
        """DE country should map to EMEA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="DE")
            assert conn._session_region == "EMEA"
            assert conn._base_api == "https://emea.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_connection_with_us_country(self):
        """US country should map to NA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")
            assert conn._session_region == "NA"
            assert conn._session_country == "US"
            # base_api should be None (not yet discovered)
            assert conn._base_api is None

    @pytest.mark.asyncio
    async def test_connection_with_ca_country(self):
        """CA country should map to NA."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="CA")
            assert conn._session_region == "NA"
            assert conn._session_country == "CA"


class TestEndpointDiscovery:
    """Test endpoint discovery for NA region."""

    @pytest.mark.asyncio
    async def test_discovery_not_needed_for_emea(self):
        """EMEA region should skip discovery."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="DE")
            result = await conn._discover_endpoints()
            assert result is True  # Should return immediately

    @pytest.mark.asyncio
    async def test_discovery_finds_working_endpoint(self):
        """Should find first working endpoint from candidates."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            # Mock successful response for second candidate
            mock_response = Mock()
            mock_response.status = 200

            # Create async context manager mock
            async_cm = AsyncMock()
            async_cm.__aenter__.return_value = mock_response
            async_cm.__aexit__.return_value = None

            with patch.object(conn._session, 'get') as mock_get:
                # First candidate fails, second succeeds
                mock_get.side_effect = [
                    Exception("Connection refused"),  # First fails
                    async_cm,  # Second succeeds
                ]

                result = await conn._discover_endpoints()

                assert result is True
                # Should have found second candidate
                assert conn._base_api == "https://us.bff.cariad.digital"

    @pytest.mark.asyncio
    async def test_discovery_fails_all_candidates(self):
        """Should return False when all candidates fail."""
        async with ClientSession() as session:
            conn = Connection(session, "test@example.com", "password", country="US")

            with patch.object(conn._session, 'get') as mock_get:
                # All candidates fail
                mock_get.side_effect = [Exception("Connection refused")] * 5

                result = await conn._discover_endpoints()

                assert result is False
                assert conn._base_api is None

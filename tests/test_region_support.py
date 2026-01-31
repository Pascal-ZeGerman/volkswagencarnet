"""Test region detection and configuration."""
import pytest
from volkswagencarnet.vw_const import (
    get_region_from_country,
    get_region_config,
)


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

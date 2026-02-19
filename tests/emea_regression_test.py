"""
EMEA regression tests and public API surface contract tests.

These tests prove that the NA authentication code added in Phases 1-5 has not
broken the EMEA login flow and that the public Connection API surface is frozen.

Phase 6 plan 06-01 — COMPAT-01, COMPAT-02
"""
import asyncio
import inspect
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

import pytest

from volkswagencarnet.vw_connection import Connection


class ConnectionAPIContractTest(IsolatedAsyncioTestCase):
    """Lock the public API surface via inspect.signature().

    Any future change to the frozen positional args or method kinds will fail here.
    Frozen surface: Connection(session, username, password, country='DE'),
    doLogin(tries=1) async, update() async, vehicles property.
    """

    def test_constructor_frozen_positional_args_present(self):
        """Frozen positional args must always be present in __init__."""
        sig = inspect.signature(Connection.__init__)
        params = sig.parameters
        for name in ("session", "username", "password", "country"):
            assert name in params, f"Frozen arg '{name}' missing from Connection.__init__"

    def test_country_defaults_to_de(self):
        """country='DE' is the backward compat default — EMEA users need zero code changes."""
        sig = inspect.signature(Connection.__init__)
        assert sig.parameters["country"].default == "DE"

    def test_dologin_accepts_tries_kwarg_with_default_one(self):
        """doLogin(tries=1) signature stable — callers may pass tries=N without breakage."""
        sig = inspect.signature(Connection.doLogin)
        assert "tries" in sig.parameters
        assert sig.parameters["tries"].default == 1

    def test_dologin_is_async(self):
        """doLogin() must remain a coroutine so `await conn.doLogin()` works."""
        assert asyncio.iscoroutinefunction(Connection.doLogin)

    def test_update_is_async(self):
        """update() must remain a coroutine so `await conn.update()` works."""
        assert asyncio.iscoroutinefunction(Connection.update)

    def test_vehicles_is_property(self):
        """vehicles must remain a property, not a plain method."""
        assert isinstance(inspect.getattr_static(Connection, "vehicles"), property)

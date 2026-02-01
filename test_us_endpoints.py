#!/usr/bin/env python3
"""Test US endpoint discovery with your own credentials.

Run this script locally to test which US endpoint works.
Your credentials never leave your machine.
"""
import asyncio
import logging
from aiohttp import ClientSession
from volkswagencarnet.vw_connection import Connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_us_endpoints():
    """Test US endpoint discovery."""
    # Enter your credentials here (they stay on your machine)
    username = input("Enter your VW CarNet username: ")
    password = input("Enter your VW CarNet password: ")

    async with ClientSession(headers={'Connection': 'keep-alive'}) as session:
        logger.info("Creating connection with country='US'")
        connection = Connection(session, username, password, country="US")

        logger.info("Attempting login with endpoint discovery...")
        if await connection.doLogin():
            logger.info("✅ SUCCESS! Login worked!")
            logger.info(f"Discovered endpoint: {connection._base_api}")
            logger.info(f"Number of vehicles: {len(connection.vehicles)}")

            for vehicle in connection.vehicles:
                logger.info(f"  - VIN: {vehicle.vin}")
        else:
            logger.error("❌ FAILED! Login did not succeed")
            logger.error("Check logs above to see which endpoints were tried")


if __name__ == "__main__":
    asyncio.run(test_us_endpoints())

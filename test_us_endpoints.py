#!/usr/bin/env python3
"""Test US endpoint discovery with your own credentials.

Run this script locally to test which US endpoint works.
Your credentials never leave your machine.

This script tests the auto-discovery mechanism which tries:
1. Legacy endpoint: https://b-h-s.spr.us00.p.con-veh.net (2021 credentials)
2. Modern CARIAD endpoints: https://na.bff.cariad.digital, etc.

The US Client ID from 2021 is: 2dae49f6-830b-4180-9af9-59dd0d060916@apps_vw-dilab_com
If this fails, newer credentials may be needed from the current VW Car-Net app.
"""
import asyncio
import logging
from aiohttp import ClientSession
from volkswagencarnet.vw_connection import Connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_us_endpoints():
    """Test US endpoint discovery."""
    print("\n" + "="*70)
    print("VW CarNet US Endpoint Discovery Test")
    print("="*70)
    print("\nThis will test auto-discovery with US credentials from 2021.")
    print("If these fail, the credentials may be outdated.\n")

    # Enter your credentials here (they stay on your machine)
    username = input("Enter your VW CarNet username: ")
    password = input("Enter your VW CarNet password: ")

    async with ClientSession(headers={'Connection': 'keep-alive'}) as session:
        logger.info("="*70)
        logger.info("TEST: Auto-Discovery with US Credentials")
        logger.info("="*70)
        logger.info("Creating connection with country='US'")
        connection = Connection(session, username, password, country="US")

        logger.info("Region detected: %s", connection._session_region)
        logger.info("Client ID: %s", connection._client_id[:20] + "...")
        logger.info("Initial base_api: %s", connection._base_api)

        logger.info("\nAttempting login with endpoint discovery...")
        logger.info("The library will try these endpoints in order:")
        logger.info("  1. https://b-h-s.spr.us00.p.con-veh.net (legacy, 2021)")
        logger.info("  2. https://na.bff.cariad.digital")
        logger.info("  3. https://us.bff.cariad.digital")
        logger.info("  4. https://northamerica.bff.cariad.digital")
        logger.info("  5. https://usac.bff.cariad.digital")
        logger.info("  6. https://americas.bff.cariad.digital")
        logger.info("\nStarting discovery...\n")

        if await connection.doLogin():
            print("\n" + "="*70)
            logger.info("✅ SUCCESS! Login worked!")
            print("="*70)
            logger.info("Discovered endpoint: %s", connection._base_api)
            logger.info("Client ID used: %s", connection._client_id[:20] + "...")
            logger.info("Number of vehicles: %d", len(connection.vehicles))

            if connection.vehicles:
                logger.info("\nVehicles found:")
                for vehicle in connection.vehicles:
                    logger.info("  - VIN: %s", vehicle.vin)

            print("\n" + "="*70)
            print("NEXT STEPS:")
            print("  - The endpoint above is working!")
            print("  - This should be reported back for documentation")
            print("="*70 + "\n")
        else:
            print("\n" + "="*70)
            logger.error("❌ FAILED! Login did not succeed")
            print("="*70)
            logger.error("\nPossible reasons:")
            logger.error("  1. The 2021 credentials are outdated")
            logger.error("  2. All endpoint candidates failed")
            logger.error("  3. Wrong username/password")
            logger.error("  4. Network/firewall issue")
            logger.error("\nCheck the logs above for specific errors.")

            print("\n" + "="*70)
            print("NEXT STEPS:")
            print("  1. Verify your username/password are correct")
            print("  2. Try network traffic analysis on the official app")
            print("  3. Report findings at:")
            print("     https://github.com/robinostlund/volkswagencarnet/issues")
            print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_us_endpoints())

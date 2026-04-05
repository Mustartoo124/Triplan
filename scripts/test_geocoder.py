"""Test geocoding tool against Google Maps Geocoding API."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.geocoder import geocode_address


async def test():
    test_cases = [
        # Exact addresses from festival data (ward-level)
        "Tân Mỹ, Hồ Chí Minh",
        "Bến Thành, Hồ Chí Minh",
        "Sài Gòn, Hồ Chí Minh",
        # Specific venue names
        "Saigon Exhibition and Convention Center, Ho Chi Minh City",
        "September 23 Park, Ho Chi Minh City",
        "Tao Dan Park, Ho Chi Minh City",
        "Youth Cultural House, Ho Chi Minh City",
        "Nguyen Hue Walking Street, Ho Chi Minh City",
        # Known POI for validation
        "Ben Thanh Market, Ho Chi Minh City",
        # Edge cases
        "",
        "nonexistent place xyz123",
    ]

    print(f"{'Address':<55} | {'Lat':>10} | {'Lng':>11} | Status")
    print("-" * 95)

    for addr in test_cases:
        lat, lng = await geocode_address(addr)
        if lat is not None:
            # Check if result is roughly in HCM area (lat ~10.7-10.9, lng ~106.6-106.8)
            in_hcm = 10.6 < lat < 11.0 and 106.5 < lng < 107.0
            status = "OK" if in_hcm else f"OUTSIDE HCM"
            print(f"{addr[:55]:<55} | {lat:>10.6f} | {lng:>11.6f} | {status}")
        else:
            print(f"{addr[:55]:<55} | {'N/A':>10} | {'N/A':>11} | NO RESULT")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(test())

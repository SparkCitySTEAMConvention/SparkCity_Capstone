"""Current lunar details for the New York City Digital City Center location."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo


NEW_YORK = ZoneInfo("America/New_York")


def load_lunar_details() -> dict[str, str]:
    """Get today's lunar phase and the next full moon from the USNO."""
    today = datetime.now(NEW_YORK).date().isoformat()

    daily_url = (
        "https://aa.usno.navy.mil/api/rstt/oneday?"
        + urlencode({
            "date": today,
            "coords": "40.76,-73.97",
            "tz": -5,
            "dst": "true",
        })
    )
    phases_url = (
        "https://aa.usno.navy.mil/api/moon/phases/date?"
        + urlencode({"date": today, "nump": 8})
    )

    with urlopen(daily_url, timeout=15) as response:
        daily = json.load(response)["properties"]["data"]
    with urlopen(phases_url, timeout=15) as response:
        phases = json.load(response)["phasedata"]

    next_full = next(
        phase for phase in phases if phase["phase"] == "Full Moon"
    )
    full_utc = datetime(
        next_full["year"],
        next_full["month"],
        next_full["day"],
        *map(int, next_full["time"].split(":")),
        tzinfo=timezone.utc,
    )

    return {
        "phase": daily["curphase"],
        "illumination": daily["fracillum"],
        "next_full_moon": full_utc.astimezone(NEW_YORK).strftime(
            "%b %-d"
        ),
        "next_full_moon_time": full_utc.astimezone(NEW_YORK).strftime(
            "%-I:%M %p"
        ),
        "date": today,
    }

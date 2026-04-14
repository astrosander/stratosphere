#!/usr/bin/env python3
"""
Sweep the SondeHub Tawhiri prediction API for every hour over the next 7 days (168 hours).
Reverse-geocodes each landing site to the nearest town/forest/landmark via OpenStreetMap Nominatim.
"""

import requests
import json
import math
import time
import sys
from datetime import datetime, timedelta, timezone

# ── Launch site parameters ──────────────────────────────────────────────────
LAUNCH_LAT = 37.57
LAUNCH_LON = 275.7   # SondeHub uses 0-360 longitude (275.7 = -84.3 W)
LAUNCH_ALT = 310
ASCENT_RATE = 5.0
BURST_ALT = 28000
DESCENT_RATE = 7.0

HOURS = 24 * 7  # 168 hours

API_URL = "https://api.v2.sondehub.org/tawhiri"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

# ── Helpers ─────────────────────────────────────────────────────────────────

def lon_360_to_180(lon):
    """Convert 0-360 longitude to -180/+180."""
    return lon - 360 if lon > 180 else lon

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def reverse_geocode(lat, lon, retries=3):
    """
    Ask Nominatim for the most detailed description of a coordinate.
    Returns a short human-readable string like:
      'Daniel Boone National Forest, Wolfe County, KY'
    Respects Nominatim's 1-req/sec policy.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "zoom": 14,           # town / village level detail
        "addressdetails": 1,
    }
    headers = {"User-Agent": "HAB-Prediction-Sweep/1.0 (personal use)"}
    for attempt in range(retries):
        try:
            r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            # Build a compact label from address parts
            addr = data.get("address", {})
            parts = []
            for key in ("hamlet", "village", "town", "city",
                        "natural", "leisure", "wood",
                        "county", "state"):
                val = addr.get(key)
                if val and val not in parts:
                    parts.append(val)
            if not parts:
                return data.get("display_name", "unknown")[:80]
            return ", ".join(parts[:4])
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return f"geocode-error ({e})"

def query_prediction(launch_dt):
    """Query one Tawhiri prediction."""
    params = {
        "profile": "standard_profile",
        "pred_type": "single",
        "launch_datetime": launch_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "launch_latitude": LAUNCH_LAT,
        "launch_longitude": LAUNCH_LON,
        "launch_altitude": LAUNCH_ALT,
        "ascent_rate": ASCENT_RATE,
        "burst_altitude": BURST_ALT,
        "descent_rate": DESCENT_RATE,
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def extract_key_points(data):
    """Return (burst_point, landing_point) dicts from prediction JSON."""
    burst = landing = None
    for stage in data.get("prediction", []):
        traj = stage.get("trajectory", [])
        if not traj:
            continue
        if stage["stage"] == "ascent":
            burst = traj[-1]
        elif stage["stage"] == "descent":
            landing = traj[-1]
    return burst, landing

# ── Main ────────────────────────────────────────────────────────────────────

def main():
    launch_lon_180 = lon_360_to_180(LAUNCH_LON)
    now = datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    print(f"Launch site : {LAUNCH_LAT:.4f}°N, {abs(launch_lon_180):.4f}°W  (alt {LAUNCH_ALT} m)")
    print(f"Balloon     : ascent {ASCENT_RATE} m/s → burst {BURST_ALT} m → descent {DESCENT_RATE} m/s")
    print(f"Time window : {HOURS} hours  ({start.strftime('%Y-%m-%d %H:%M')} – "
          f"{(start + timedelta(hours=HOURS-1)).strftime('%Y-%m-%d %H:%M')} UTC)")
    print()

    sep = "=" * 170
    print(sep)
    print(f"{'# ':>4} {'Launch (UTC)':<18} "
          f"{'Burst Lat':>10} {'Burst Lon':>11} {'BrstAlt':>8} "
          f"{'Land Lat':>10} {'Land Lon':>11} {'Dist km':>8}  "
          f"{'Landing location'}")
    print("-" * 170)

    for h in range(HOURS):
        launch_dt = start + timedelta(hours=h)
        label = launch_dt.strftime("%Y-%m-%d %H:%M")
        try:
            data = query_prediction(launch_dt)
            burst, landing = extract_key_points(data)

            if burst and landing:
                b_lat = burst["latitude"]
                b_lon = lon_360_to_180(burst["longitude"])
                b_alt = burst["altitude"]
                l_lat = landing["latitude"]
                l_lon = lon_360_to_180(landing["longitude"])
                dist = haversine_km(LAUNCH_LAT, launch_lon_180, l_lat, l_lon)

                # Reverse-geocode the landing site
                location_name = reverse_geocode(l_lat, l_lon)
                # Nominatim polite: 1 req/sec
                time.sleep(1.1)

                print(f"{h+1:4d} {label:<18} "
                      f"{b_lat:10.4f} {b_lon:11.4f} {b_alt:8.0f} "
                      f"{l_lat:10.4f} {l_lon:11.4f} {dist:8.1f}  "
                      f"{location_name}")
            else:
                print(f"{h+1:4d} {label:<18}  ** no burst/landing data **")

        except requests.exceptions.HTTPError as e:
            print(f"{h+1:4d} {label:<18}  HTTP {e.response.status_code}: {e}")
        except Exception as e:
            print(f"{h+1:4d} {label:<18}  ERROR: {e}")

        sys.stdout.flush()

    print(sep)
    print("Done.")

if __name__ == "__main__":
    main()
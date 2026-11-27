# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "shapely", "pyyaml", "rasterio", "pyproj", "numpy"]
# ///
"""Is there a more comfortable way than the one Google suggests?

For every trip in spike/routes.yaml:
  1. take the walking route Google Maps suggests (Routes API, used in memory only),
  2. build stair-free alternatives on our graph with uphill limits from gentle to
     tolerant,
  3. compare each with Google's route on stairs, steepest climb, total climb and time,
  4. say whether Google's route is already the most comfortable one found, or which
     alternative is better and what it costs in extra time, and whether a Google link
     can be made to follow it.

Run with GOOGLE_MAPS_API_KEY set and GraphHopper on localhost:8989.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spike_routes as sr  # noqa: E402

# Uphill limits (percent, edge average on GraphHopper's ~30 m grid) for the alternatives;
# each has a profile in config/graphhopper.yml.
UPHILL_LIMITS = [5, 7, 9, 12]
# An alternative is "gentler" when its steepest climb is at least this many points lower.
GENTLER_BY = 3.0
# Extra time an alternative may cost: the larger of these two.
MAX_EXTRA_MIN = 10.0
MAX_EXTRA_SHARE = 0.5


@dataclass
class Option:
    label: str
    coords: list
    time_min: float
    distance_m: float
    stairs: set[str]
    up: float | None
    down: float | None
    climb: float | None
    route: sr.Route | None = None


def measure(label, coords, time_min, distance_m, stairs, route=None) -> Option:
    g = sr.dgt_grades(coords)
    return Option(label, coords, time_min, distance_m, stairs,
                  g[0] if g else None, g[1] if g else None, sr.dgt_climb(coords), route)


def describe(o: Option, names) -> str:
    slope = "n/a" if o.up is None else f"+{o.up:.0f}% / {o.down:.0f}%"
    climb = "n/a" if o.climb is None else f"{o.climb:.0f} m"
    stairs = "none" if not o.stairs else f"{len(o.stairs)} ({sr.describe_stairs(o.stairs, names)})"
    return f"{o.distance_m:5.0f} m, {o.time_min:3.0f} min, steepest {slope}, climb {climb}, stairs {stairs}"


def reaches(route: sr.Route, start, end) -> bool:
    miss_start = sr.math.dist(sr.to_m(start[1], start[0]), sr.to_m(*route.coords[0]))
    miss_end = sr.math.dist(sr.to_m(end[1], end[0]), sr.to_m(*route.coords[-1]))
    return max(miss_start, miss_end) <= sr.SNAP_LIMIT_M


def pick_better(google: Option, options: list[Option]) -> tuple[Option | None, str]:
    budget = max(MAX_EXTRA_MIN, MAX_EXTRA_SHARE * google.time_min)
    usable = [o for o in options if o.up is not None and o.time_min - google.time_min <= budget]
    if google.stairs:
        if usable:
            best = min(usable, key=lambda o: (round(o.up), o.time_min))
            return best, "Google's route has stairs; this one has none"
        if options:
            best = min(options, key=lambda o: o.time_min)
            return best, "Google's route has stairs; the only stair-free way is a long detour"
        return None, "Google's route has stairs and no stair-free way was found"
    if google.up is None:
        return None, "cannot compare: Google's route leaves the 2 m terrain"
    gentler = [o for o in usable if o.up <= google.up - GENTLER_BY]
    if not gentler:
        return None, "Google's route is already the most comfortable one found"
    best = min(gentler, key=lambda o: (round(o.up), o.time_min))
    return best, "gentler than Google's route"


def main() -> None:
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        sys.exit("set GOOGLE_MAPS_API_KEY")
    trips = yaml.safe_load((sr.ROOT / "spike" / "routes.yaml").read_text())["trips"]
    names = {s.osm_id: s.name for s in sr.load_stairs()}
    with httpx.Client() as client:
        for trip in trips:
            name, start, end = trip["name"], tuple(trip["from"]), tuple(trip["to"])
            print(f"\n=== {name} ===")
            g_coords, g_dist = sr.google_route_line(client, key, start, end, [])
            g_stairs = sr.stairs_by_matching(client, g_coords)
            g_street = {i for i in (g_stairs or set()) if i in names}
            # Google's walking time is not requested; estimate it at GraphHopper's foot pace.
            foot = sr.gh_route(client, "foot", start, end)
            pace = foot.time_s / foot.distance_m if foot else 0.72
            google = measure("google", g_coords, g_dist * pace / 60, g_dist, g_street)
            print(f"google suggests : {describe(google, names)}")

            options: list[Option] = []
            seen: list = []
            for limit in UPHILL_LIMITS:
                # One GraphHopper profile per limit (config/stroller-up*.json). A limit sent
                # with the request would not change where the end point snaps, so routes
                # would detour to reach a steep last edge that the profile itself avoids.
                r = sr.gh_route(client, f"stroller_up{limit}", start, end)
                if r is None or not reaches(r, start, end):
                    print(f"limit {limit:>2}%       : no stair-free route")
                    continue
                if any(r.line.hausdorff_distance(s) < 25 for s in seen):
                    continue  # same way as a gentler limit already found
                seen.append(r.line)
                o = measure(f"limit {limit}%", r.coords, r.time_s / 60, r.distance_m, {i for i in r.stairs if i in names}, r)
                options.append(o)
                print(f"limit {limit:>2}%       : {describe(o, names)}")

            best, why = pick_better(google, options)
            if best is None:
                print(f"answer          : {why}")
                continue
            extra = best.time_min - google.time_min
            print(f"answer          : {why} ({best.label}, {extra:+.0f} min)")
            sr.pin_to_google(client, key, start, end, best.route, names)


if __name__ == "__main__":
    main()

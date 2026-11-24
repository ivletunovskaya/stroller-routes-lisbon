# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "shapely", "pyyaml"]
# ///
"""Calibrate the "route uses this staircase" rule against ground truth.

Ground truth comes from GraphHopper itself: for random walking routes in central
Lisbon it reports exactly which OSM staircases each route uses. The rule only sees
the route line, as it will for Google's routes. To mimic Google's geometry not lining
up with OSM, every route is also checked after shifting it sideways by a few metres.

Prints precision and recall for several rule settings.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import httpx
from shapely import affinity

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spike_routes as sr

CENTRAL = (-9.150, 38.705, -9.125, 38.722)  # Baixa, Chiado, Alfama, Bairro Alto, Graça
N_ROUTES = 150
SHIFTS_M = (0.0, 5.0)


def truth(client: httpx.Client, start, end):
    body = {
        "points": [[start[1], start[0]], [end[1], end[0]]],
        "profile": "foot",
        "points_encoded": False,
        "elevation": False,
        "instructions": False,
        "details": ["road_class", "osm_way_id"],
    }
    resp = client.post(f"{sr.GH_URL}/route", json=body, timeout=30)
    if resp.status_code != 200:
        return None, None
    path = resp.json()["paths"][0]
    steps_ranges = [(a, b) for a, b, v in path["details"]["road_class"] if v == "steps"]
    used = set()
    for a, b, way in path["details"]["osm_way_id"]:
        if any(a < y and b > x for x, y in steps_ranges):
            used.add(f"w{way}")
    coords = [(p[0], p[1]) for p in path["points"]["coordinates"]]
    return sr.line_m(coords), used


def to_lonlat(line_metres):
    return [(x / sr.M_PER_DEG_LON, y / sr.M_PER_DEG_LAT) for x, y in line_metres.coords]


def main() -> None:
    random.seed(7)
    stairs = sr.load_stairs()
    settings = [
        {"buffer_m": 10.0, "min_share": 0.5, "min_span": 0.0, "max_bearing_diff_deg": 180.0},
        {"buffer_m": 10.0, "min_share": 0.5, "min_span": 0.0, "max_bearing_diff_deg": 35.0},
        {"buffer_m": 10.0, "min_share": 0.5, "min_span": 0.7, "max_bearing_diff_deg": 35.0},
        {"buffer_m": 8.0, "min_share": 0.6, "min_span": 0.7, "max_bearing_diff_deg": 35.0},
        {"buffer_m": 12.0, "min_share": 0.5, "min_span": 0.6, "max_bearing_diff_deg": 45.0},
    ]
    samples = []
    with httpx.Client() as client:
        while len(samples) < N_ROUTES:
            w, s, e, n = CENTRAL
            a = (random.uniform(s, n), random.uniform(w, e))
            b = (random.uniform(s, n), random.uniform(w, e))
            line, used = truth(client, a, b)
            if line is not None and line.length > 300:
                samples.append((line, used))

    print(f"{len(samples)} routes, {sum(len(u) for _, u in samples)} staircases used in total\n")

    with httpx.Client() as client:
        for shift in SHIFTS_M:
            tp = fp = fn = failed = 0
            for line, used in samples:
                moved = affinity.translate(line, xoff=shift) if shift else line
                found = sr.stairs_by_matching(client, to_lonlat(moved))
                if found is None:
                    failed += 1
                    fn += len(used)
                    continue
                tp += len(found & used)
                fp += len(found - used)
                fn += len(used - found)
            precision = tp / (tp + fp) if tp + fp else 1.0
            recall = tp / (tp + fn) if tp + fn else 1.0
            print(
                f"MAP MATCHING | shift {shift} m: precision {precision:.2f}, recall {recall:.2f} "
                f"(missed {fn}, false {fp}, matching failed on {failed} routes)"
            )
    print()
    for cfg in settings:
        sr.THRESHOLDS["stairs_match"].update(cfg)
        index = sr.StairsIndex(stairs)
        for shift in SHIFTS_M:
            tp = fp = fn = 0
            for line, used in samples:
                moved = affinity.translate(line, xoff=shift) if shift else line
                found = {s.osm_id for s, _ in index.used_by(moved)}
                tp += len(found & used)
                fp += len(found - used)
                fn += len(used - found)
            precision = tp / (tp + fp) if tp + fp else 1.0
            recall = tp / (tp + fn) if tp + fn else 1.0
            print(
                f"buffer {cfg['buffer_m']:>4} share {cfg['min_share']} span {cfg['min_span']} "
                f"bearing {cfg['max_bearing_diff_deg']:>5} | shift {shift} m: "
                f"precision {precision:.2f}, recall {recall:.2f} (missed {fn}, false {fp})"
            )


if __name__ == "__main__":
    main()

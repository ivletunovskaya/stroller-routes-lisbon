# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "shapely", "pyyaml", "rasterio", "pyproj"]
# ///
"""Risk check: compare stroller routes with ordinary walking routes on real trips.

For every trip in spike/routes.yaml this script:
  1. asks the local GraphHopper for an ordinary walking route and a stroller route,
  2. reports length, time, steepest climb and the stairs each route uses,
  3. builds a Google Maps walking link with at most 3 waypoints that should pull
     Google onto the stroller route,
  4. if GOOGLE_MAPS_API_KEY is set, asks Google which route that link really draws
     and checks it for stairs by snapping it onto the OSM street graph.
     Google's line is used in memory only, never saved.

Route geometries of our own routes are written to data/spike-out/ as GeoJSON so they
can be dropped onto geojson.io for a visual comparison.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import httpx
import rasterio
import yaml
from pyproj import Transformer
import numpy as np
import shapely
from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent.parent
GH_URL = os.environ.get("GRAPHHOPPER_URL", "http://localhost:8989")
ROUTES_API = "https://routes.googleapis.com/directions/v2:computeRoutes"
MAX_WAYPOINTS = 3
# How far a route may start or end from the requested point before it counts as not reaching it.
SNAP_LIMIT_M = 40.0
# Google's route may be this many percentage points steeper than ours and still count as holding it.
SLOPE_TOLERANCE = 2.0

THRESHOLDS = tomllib.loads((ROOT / "config" / "thresholds.toml").read_text())


# ---------- geometry in metres around Lisbon ----------

LAT0 = 38.72
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))


def to_m(lon: float, lat: float) -> tuple[float, float]:
    return (lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT)


def line_m(coords_lonlat: list[tuple[float, float]]) -> LineString:
    return LineString([to_m(lon, lat) for lon, lat in coords_lonlat])


def bearing_deg(line: LineString) -> float:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    return math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0


# ---------- slopes from the 2 m terrain model ----------

DGT_VRT = ROOT / "data" / "dgt" / "lisbon.vrt"
_dgt = rasterio.open(DGT_VRT) if DGT_VRT.exists() else None
_to_dgt = Transformer.from_crs("EPSG:4326", _dgt.crs, always_xy=True) if _dgt else None


def _load_offground():
    """Walkable ways that are not on the ground: bridges, raised plazas, tunnels."""
    path = ROOT / "data" / "lisbon-offground.geojson"
    if _dgt is None or not path.exists():
        return None
    shapes = []
    for f in json.loads(path.read_text())["features"]:
        props = f.get("properties") or {}
        if "highway" not in props:
            continue
        layer = str(props.get("layer", "0")).split(";")[0]
        off = props.get("bridge", "no") != "no" or props.get("tunnel", "no") != "no" or layer not in ("0", "")
        if off:
            geom = shapely.transform(shape(f["geometry"]), lambda c: np.column_stack(_to_dgt.transform(c[:, 0], c[:, 1])))
            # Wide enough for Google lines, which run a few metres off the OSM way.
            shapes.append(geom.buffer(8))
    return prep(unary_union(shapes)) if shapes else None


_offground = _load_offground()


def dgt_grades(coords_lonlat: list[tuple[float, float]], step_m: float = 2.0, window_m: float = 15.0):
    """Steepest climb and descent in percent along a line, from DGT's 2 m bare-earth
    model, measured over a sliding window. None where the line leaves the model."""
    if _dgt is None:
        return None
    xs, ys = _to_dgt.transform([c[0] for c in coords_lonlat], [c[1] for c in coords_lonlat])
    line = LineString(zip(xs, ys))
    n = max(int(line.length / step_m), 1)
    pts = [line.interpolate(i * line.length / n) for i in range(n + 1)]
    heights = [v[0] for v in _dgt.sample([(p.x, p.y) for p in pts])]
    if any(h is None or h < -50 for h in heights):
        return None
    # The terrain model is bare earth: on a bridge or a raised plaza it gives the
    # ground below, not the deck. Bridge those stretches with a straight line
    # between the last and next points on the ground.
    if _offground is not None:
        off = [_offground.contains(p) for p in pts]
        ground = [i for i, o in enumerate(off) if not o]
        if not ground:
            return None
        for i, o in enumerate(off):
            if o:
                before = max((g for g in ground if g < i), default=None)
                after = min((g for g in ground if g > i), default=None)
                if before is None or after is None:
                    heights[i] = heights[after if before is None else before]
                else:
                    w = (i - before) / (after - before)
                    heights[i] = heights[before] * (1 - w) + heights[after] * w
    k = max(int(window_m / (line.length / n)), 1)
    grades = [100 * (heights[i + k] - heights[i]) / (k * line.length / n) for i in range(len(heights) - k)]
    if not grades:
        return 0.0, 0.0
    return max(grades), min(grades)


def fmt_grades(g) -> str:
    return "n/a (outside the 2 m model)" if g is None else f"+{g[0]:.0f}% / {g[1]:.0f}%"


# ---------- stairs ----------


@dataclass
class Staircase:
    osm_id: str
    name: str
    line: LineString


def load_stairs() -> list[Staircase]:
    path = ROOT / "data" / "lisbon-steps.geojson"
    if not path.exists():
        sys.exit("data/lisbon-steps.geojson is missing: run scripts/fetch_osm.sh first")
    stairs = []
    for feature in json.loads(path.read_text())["features"]:
        geom = shape(feature["geometry"])
        props = feature.get("properties") or {}
        # Stairs inside buildings and stations, and escalators, are not on a street
        # route even when the route passes right above or beside them.
        if props.get("indoor") or "level" in props or "conveying" in props:
            continue
        stairs.append(
            Staircase(
                osm_id=str(props.get("@id") or feature.get("id") or ""),
                name=props.get("name") or "",
                line=LineString([to_m(x, y) for x, y in geom.coords]),
            )
        )
    return stairs


class StairsIndex:
    def __init__(self, stairs: list[Staircase]):
        self.stairs = stairs
        self.tree = STRtree([s.line for s in stairs])
        cfg = THRESHOLDS["stairs_match"]
        self.buffer_m = cfg["buffer_m"]
        self.min_share = cfg["min_share"]
        self.max_bearing_diff = cfg["max_bearing_diff_deg"]
        self.min_span = cfg["min_span"]

    def used_by(self, route: LineString) -> list[tuple[Staircase, float]]:
        """Staircases the route runs along, with the distance from the route start."""
        corridor = route.buffer(self.buffer_m)
        hits = []
        for idx in self.tree.query(corridor):
            stair = self.stairs[idx]
            if stair.line.length == 0:
                continue
            share = stair.line.intersection(corridor).length / stair.line.length
            if share < self.min_share:
                continue
            # The route must travel the staircase end to end: both ends lie in the
            # corridor and their positions along the route span most of its length.
            # This rejects short stairs that merely sit next to the route, such as
            # metro entrances on a square the route crosses.
            a, b = Point(stair.line.coords[0]), Point(stair.line.coords[-1])
            if route.distance(a) > self.buffer_m or route.distance(b) > self.buffer_m:
                continue
            if abs(route.project(a) - route.project(b)) < self.min_span * stair.line.length:
                continue
            # Compare the staircase direction with the route nearby; direction of travel
            # does not matter, so bearings are compared modulo 180 degrees.
            mid = stair.line.interpolate(0.5, normalized=True)
            at = route.project(mid)
            seg = LineString(
                [route.interpolate(max(at - 10, 0)), route.interpolate(min(at + 10, route.length))]
            )
            diff = abs(bearing_deg(stair.line) - bearing_deg(seg))
            diff = min(diff, 180 - diff)
            if diff > self.max_bearing_diff:
                continue
            hits.append((stair, at))
        return sorted(hits, key=lambda h: h[1])


def stairs_by_matching(client: httpx.Client, coords_lonlat: list[tuple[float, float]]) -> set[str] | None:
    """Snap a foreign route line (e.g. Google's) onto the OSM walking graph and
    return the OSM ids of the staircases it travels. None if matching failed.

    The line is densified to a point every ~10 m so the matcher can follow it
    through Lisbon's short street segments."""
    line = LineString(coords_lonlat)
    metres = line_m(coords_lonlat).length
    n = max(int(metres / 10), 2)
    pts = [line.interpolate(i / n, normalized=True) for i in range(n + 1)]
    gpx = (
        '<?xml version="1.0"?><gpx version="1.1" creator="stroller-routes"><trk><trkseg>'
        + "".join(f'<trkpt lat="{p.y:.7f}" lon="{p.x:.7f}"></trkpt>' for p in pts)
        + "</trkseg></trk></gpx>"
    )
    resp = client.post(
        f"{GH_URL}/match",
        params=[
            ("profile", "foot"),
            ("points_encoded", "false"),
            ("gps_accuracy", "15"),
            ("details", "road_class"),
            ("details", "osm_way_id"),
        ],
        content=gpx,
        headers={"Content-Type": "application/gpx+xml"},
        timeout=60,
    )
    if resp.status_code != 200:
        return None
    path = resp.json()["paths"][0]
    steps_ranges = [(a, b) for a, b, v in path["details"]["road_class"] if v == "steps"]
    return {
        f"w{way}"
        for a, b, way in path["details"]["osm_way_id"]
        if any(a < y and b > x for x, y in steps_ranges)
    }


# ---------- GraphHopper ----------


@dataclass
class Route:
    coords: list[tuple[float, float]]  # lon, lat
    elevations: list[float]
    distance_m: float
    time_s: float
    stairs: set[str] = field(default_factory=set)  # OSM ids of staircases used

    @property
    def line(self) -> LineString:
        return line_m(self.coords)


def gh_route(client: httpx.Client, profile: str, start, end) -> Route | None:
    body = {
        "points": [[start[1], start[0]], [end[1], end[0]]],
        "profile": profile,
        "points_encoded": False,
        "elevation": True,
        "instructions": False,
        "details": ["road_class", "osm_way_id"],
    }
    resp = client.post(f"{GH_URL}/route", json=body, timeout=30)
    if resp.status_code == 400:
        return None  # no route in this profile
    resp.raise_for_status()
    path = resp.json()["paths"][0]
    pts = path["points"]["coordinates"]
    # Stairs on our own route come straight from the graph, not from map matching:
    # matching our line again can snap it onto a short staircase beside the footway.
    ids = path["details"]["osm_way_id"]
    stairs = {
        f"w{way}"
        for a, b, v in path["details"]["road_class"]
        if v == "steps"
        for s, e, way in ids
        if s < b and e > a
    }
    return Route(
        coords=[(p[0], p[1]) for p in pts],
        elevations=[p[2] if len(p) > 2 else 0.0 for p in pts],
        distance_m=path["distance"],
        time_s=path["time"] / 1000,
        stairs=stairs,
    )


def steepest(route: Route, window_m: float = 15.0) -> tuple[float, float]:
    """Steepest climb and steepest descent in percent, smoothed over a window."""
    dist = [0.0]
    for (a, b) in zip(route.coords, route.coords[1:]):
        (x0, y0), (x1, y1) = to_m(*a), to_m(*b)
        dist.append(dist[-1] + math.hypot(x1 - x0, y1 - y0))
    up = down = 0.0
    j = 0
    for i in range(len(dist)):
        while j < len(dist) and dist[j] - dist[i] < window_m:
            j += 1
        if j >= len(dist):
            break
        grade = 100 * (route.elevations[j] - route.elevations[i]) / (dist[j] - dist[i])
        up, down = max(up, grade), min(down, grade)
    return up, down


# ---------- Google ----------


def pick_waypoints(ours: Route, baseline: Route | None) -> list[tuple[float, float]]:
    """Points on our route that lie farthest from the ordinary walking route."""
    if baseline is None:
        return []
    base = baseline.line
    candidates = []
    for lon, lat in ours.coords[1:-1]:
        candidates.append((base.distance(Point(to_m(lon, lat))), (lat, lon)))
    candidates.sort(reverse=True)
    picked: list[tuple[float, float]] = []
    for dist, (lat, lon) in candidates:
        if dist < 25 or len(picked) == MAX_WAYPOINTS:
            break
        if all(math.dist(to_m(lon, lat), to_m(p[1], p[0])) > 150 for p in picked):
            picked.append((lat, lon))
    # Keep waypoints in travel order.
    line = ours.line
    return sorted(picked, key=lambda p: line.project(Point(to_m(p[1], p[0]))))


def google_link(start, end, waypoints) -> str:
    fmt = lambda p: f"{p[0]:.6f},{p[1]:.6f}"
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={fmt(start)}&destination={fmt(end)}&travelmode=walking"
    )
    if waypoints:
        url += "&waypoints=" + quote("|".join(fmt(w) for w in waypoints))
    return url


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    coords, index, lat, lon = [], 0, 0, 0
    while index < len(encoded):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lon += delta
        coords.append((lon / 1e5, lat / 1e5))
    return coords


def google_route_line(client: httpx.Client, key: str, start, end, waypoints) -> tuple[list[tuple[float, float]], float]:
    loc = lambda p: {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}
    body = {
        "origin": loc(start),
        "destination": loc(end),
        "intermediates": [loc(w) for w in waypoints],
        "travelMode": "WALK",
    }
    resp = client.post(
        ROUTES_API,
        json=body,
        headers={
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "routes.polyline.encodedPolyline,routes.distanceMeters",
        },
        timeout=30,
    )
    resp.raise_for_status()
    route = resp.json()["routes"][0]
    return decode_polyline(route["polyline"]["encodedPolyline"]), route["distanceMeters"]


# ---------- report ----------


def describe_stairs(ids: set[str] | None, names: dict[str, str]) -> str:
    if ids is None:
        return "could not match the line to the street graph"
    # Only street staircases count; stairs inside stations and buildings are
    # left out of `names` by load_stairs().
    ids = {i for i in ids if i in names}
    if not ids:
        return "none"
    return "; ".join(f"{names[i] or 'unnamed'} ({i})" for i in sorted(ids))


def write_geojson(name: str, routes: dict[str, Route]) -> Path:
    out = ROOT / "data" / "spike-out"
    out.mkdir(parents=True, exist_ok=True)
    colors = {"foot": "#999999", "stroller": "#1f77b4"}
    features = [
        {
            "type": "Feature",
            "properties": {"profile": profile, "stroke": colors.get(profile, "#000")},
            "geometry": {"type": "LineString", "coordinates": [list(c) for c in r.coords]},
        }
        for profile, r in routes.items()
    ]
    path = out / f"{name}.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def pin_to_google(client: httpx.Client, key: str, start, end, ours: Route, names: dict[str, str]) -> None:
    """Add waypoints one at a time where Google strays furthest from our route,
    re-checking Google's actual route after each, up to MAX_WAYPOINTS.

    Google's route counts as holding ours when it uses no street stairs and is not
    noticeably steeper than our route on the 2 m terrain model."""
    our_line = ours.line
    our_grades = dgt_grades(ours.coords)
    waypoints: list[tuple[float, float]] = []
    while True:
        g_coords, g_dist = google_route_line(client, key, start, end, waypoints)
        g_line = line_m(g_coords)
        stairs = stairs_by_matching(client, g_coords)
        street_stairs = {i for i in stairs if i in names} if stairs is not None else None
        g_grades = dgt_grades(g_coords)
        too_steep = (
            g_grades is not None
            and our_grades is not None
            and g_grades[0] > our_grades[0] + SLOPE_TOLERANCE
        )
        gap = our_line.hausdorff_distance(g_line)
        print(
            f"google, {len(waypoints)} waypoints: {g_dist:.0f} m, max gap {gap:.0f} m, "
            f"steepest {fmt_grades(g_grades)}{'  <-- steeper than ours' if too_steep else ''}, "
            f"stairs: {describe_stairs(stairs, names)}"
        )
        # Without slope figures for both lines the link cannot be called safe.
        slope_known = g_grades is not None and our_grades is not None
        holds = street_stairs == set() and slope_known and not too_steep
        if holds or len(waypoints) == MAX_WAYPOINTS:
            break
        # The point of our route that Google's line is furthest from.
        far = max(ours.coords[1:-1], key=lambda c: g_line.distance(Point(to_m(*c))))
        waypoints.append((far[1], far[0]))
        waypoints.sort(key=lambda p: our_line.project(Point(to_m(p[1], p[0]))))
    verdict = "HOLDS" if holds else "DOES NOT HOLD" if slope_known else "CANNOT BE VERIFIED (no 2 m terrain)"
    print(f"verdict       : link {verdict} the stair-free route")
    print(f"google link   : {google_link(start, end, waypoints)}")


def main() -> None:
    trips = yaml.safe_load((ROOT / "spike" / "routes.yaml").read_text())["trips"]
    names = {s.osm_id: s.name for s in load_stairs()}
    google_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    max_up = THRESHOLDS["slope"]["max_uphill"]

    with httpx.Client() as client:
        for trip in trips:
            name, start, end = trip["name"], tuple(trip["from"]), tuple(trip["to"])
            print(f"\n=== {name} ===")
            foot = gh_route(client, "foot", start, end)
            ours = gh_route(client, "stroller", start, end)

            if foot:
                print(
                    f"ordinary walk : {foot.distance_m:.0f} m, {foot.time_s / 60:.0f} min, "
                    f"steepest (2 m terrain) {fmt_grades(dgt_grades(foot.coords))}, stairs: {describe_stairs(foot.stairs, names)}"
                )
            if not ours:
                print("stroller route: NONE within the limits (honest 'no route' case)")
                continue
            # GraphHopper snaps start and end to the nearest street the profile may use.
            # When the real destination is only reachable by stairs or a steep climb, it
            # silently snaps somewhere else, and the route stops short of where the parent
            # wants to go. That must be reported as "no route", never as a route.
            miss_start = math.dist(to_m(start[1], start[0]), to_m(*ours.coords[0]))
            miss_end = math.dist(to_m(end[1], end[0]), to_m(*ours.coords[-1]))
            if max(miss_start, miss_end) > SNAP_LIMIT_M:
                print(
                    f"stroller route: does NOT reach the trip (start off by {miss_start:.0f} m, "
                    f"end off by {miss_end:.0f} m) -> honest 'no route' case"
                )
                continue
            g = dgt_grades(ours.coords)
            flag = "  <-- above the uphill limit" if g and g[0] > max_up else ""
            print(
                f"stroller route: {ours.distance_m:.0f} m, {ours.time_s / 60:.0f} min, "
                f"steepest (2 m terrain) {fmt_grades(g)}{flag}, "
                f"stairs: {describe_stairs(ours.stairs, names)}"
            )
            if foot:
                print(f"extra time vs ordinary walk: {(ours.time_s - foot.time_s) / 60:+.0f} min")

            if not google_key:
                waypoints = pick_waypoints(ours, foot)
                print(f"google link ({len(waypoints)} waypoints): {google_link(start, end, waypoints)}")
                print("google check  : skipped (set GOOGLE_MAPS_API_KEY to run it)")
            else:
                pin_to_google(client, google_key, start, end, ours, names)

            routes = {"stroller": ours} | ({"foot": foot} if foot else {})
            print(f"geometry      : {write_geojson(name, routes).relative_to(ROOT)}")


if __name__ == "__main__":
    main()

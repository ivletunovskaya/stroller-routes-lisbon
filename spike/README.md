# Risk check scripts

Throwaway code for the go/no-go risk check. Results live in `docs/research/spike-results.md`.

## Setup (macOS)

```bash
brew install openjdk@21 uv osmium-tool gdal
curl -sSL -o data/graphhopper-web-11.1.jar https://github.com/graphhopper/graphhopper/releases/download/11.1/graphhopper-web-11.1.jar
./scripts/fetch_osm.sh
```

Elevation: download the DGT MDT 2 m GeoTIFF tiles for Lisbon from cdd.dgterritorio.gov.pt (free account) into `data/dgt/`, then:

```bash
uv run scripts/prepare_elevation.py
```

Put the Google key in `.env` (`GOOGLE_MAPS_API_KEY=...`, the file is git-ignored) and load it with `set -a; source .env; set +a`.

## Run

Start GraphHopper from the repository root (the first start builds the graph in under a minute):

```bash
/opt/homebrew/opt/openjdk@21/bin/java -Xmx3g -jar data/graphhopper-web-11.1.jar server config/graphhopper.yml
```

Then, in another terminal:

```bash
uv run spike/spike_routes.py
```

```bash
uv run spike/calibrate_stairs.py
```

Set `GOOGLE_MAPS_API_KEY` to include the check of the route Google actually draws. Google's route lines are only used in memory and never written to disk.

Route geometries are written to `data/spike-out/*.geojson`; drop them onto geojson.io to compare the ordinary walk (grey) with the stroller route (blue).

## Compare with Google's suggestion

```bash
set -a && source .env && set +a && uv run spike/compare_routes.py
```

For each trip: Google's suggested route, stair-free alternatives under 5/7/9/12% uphill limits, and the answer (Google's route is the most comfortable / a better way and its cost / no stair-free way). Needs the `stroller_up*` profiles, so rebuild the graph (delete `data/graph-cache`) after pulling this change.

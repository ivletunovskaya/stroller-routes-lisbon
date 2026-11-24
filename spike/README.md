# Risk check scripts

Throwaway code for the go/no-go risk check. Results live in `docs/research/spike-results.md`.

## Setup (macOS)

```bash
brew install openjdk@21 uv osmium-tool gdal
curl -sSL -o data/graphhopper-web-11.1.jar https://github.com/graphhopper/graphhopper/releases/download/11.1/graphhopper-web-11.1.jar
./scripts/fetch_osm.sh
```

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

#!/usr/bin/env bash
# Download the Portugal OSM extract and cut out the Lisbon area,
# then export every staircase for the route check.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data

# Lisbon municipality plus a margin: west, south, east, north.
BBOX="-9.24,38.68,-9.08,38.80"

if [ ! -f data/portugal-latest.osm.pbf ]; then
  curl -sSL -o data/portugal-latest.osm.pbf \
    https://download.geofabrik.de/europe/portugal-latest.osm.pbf
fi

osmium extract --bbox "$BBOX" --overwrite \
  -o data/lisbon.osm.pbf data/portugal-latest.osm.pbf

osmium tags-filter --overwrite -o data/lisbon-steps.osm.pbf \
  data/lisbon.osm.pbf w/highway=steps
osmium export --overwrite --add-unique-id=type_id --geometry-types=linestring \
  -o data/lisbon-steps.geojson data/lisbon-steps.osm.pbf

echo "Lisbon extract: data/lisbon.osm.pbf"
echo "Staircases: data/lisbon-steps.geojson"

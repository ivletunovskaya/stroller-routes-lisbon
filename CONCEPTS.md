# Concepts

> Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound captures and refreshes learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Routes

### Stroller route

The walking route the assistant builds for a parent with a stroller: no street stairs, no stretch steeper than the slope limits, and climbs costing more than descents, so it prefers going downhill and accepts a longer way for a flatter one.

### Ordinary walk

The shortest walking route with no stroller limits, used as the baseline a stroller route is compared against (for the extra time it costs) and as a stand-in for what Google Maps would suggest on its own.

### No route

The honest answer when no stroller route reaches the destination. It is given instead of any route that stops short of the destination, uses stairs, or exceeds the slope limits, and it names the least-bad alternative where one exists.

## Verification

### Street staircase

An outdoor flight of steps a walking route can use. Steps inside stations and buildings, and escalators, are not street staircases, even when they lie right under or beside a street.

### Holds

A Google Maps link holds a stroller route when the route Google actually draws for it uses no street staircase and is not noticeably steeper than the stroller route. When either slope cannot be measured, the link does not hold. Only a link that holds may be offered as suitable.

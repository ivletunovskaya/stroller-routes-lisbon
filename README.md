# Stroller Routes Lisbon

A helper for parents with strollers in Lisbon. It tells you how to get somewhere without stairs or exhausting climbs, or honestly says that no such route exists.

## Why

Google Maps picks the shortest walking route, and in Lisbon that route often goes up staircase streets and steep slopes, even when there is a detour nearby: take a public lift up and walk downhill, or take a flat street that is a little longer. Parents find out mid-walk, and after a few of those walks they start skipping a coffee, a visit to friends, or a walk in another neighbourhood.

## How it will work

It is not a separate map. It is a Telegram assistant that works alongside Google Maps:

- send it a link to a café or an address, and get a route with no stairs and no steep climbs (using the city's public lifts) plus a link that opens that route in Google Maps;
- send it a Google Maps route, and get the spots where it has stairs or a steep section, with a way around them;
- if there is no obstacle-free route, it says so plainly and offers the least bad option;
- parents can mark "narrow" or "bad surface" with one tap, and those marks are collected anonymously.

The project is non-commercial. The first version covers Lisbon only.

## Status

Planning. No code yet. The first step is a risk check on a few real routes: does the router find stair-free routes, and do Google Maps links hold them?

## Documents

- [Plan: requirements and technical plan](docs/plans/2026-11-17-1612-feat-stroller-routes-lisbon-plan.md)
- [Technical research: routing engines, terrain, lifts, Google, Telegram](docs/research/2026-11-17-technical-research.md)

## How it is made

I'm working out the idea, requirements, technical plan and their reviews together with Claude Code and Every's [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin) skills: `ce-brainstorm` → `ce-doc-review` → `ce-plan` → `ce-work`.

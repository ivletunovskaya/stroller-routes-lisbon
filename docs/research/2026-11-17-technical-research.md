# Stroller-routes Lisbon: external technical research (as of 2026-11-17)

Legend: **[V]** verified from a primary/official source during this research; **[S]** secondary source; **[U]** unverified / from background knowledge, check before relying on it.

---

## 1. Routing engine

### Recommendation
**Self-hosted GraphHopper (open source, Apache-2.0) on a Lisbon-only OSM extract, foot-based custom profile, elevation from a high-res DEM (see Q3).** Keep OpenRouteService hosted API only as a zero-setup baseline for the first week of prototyping. Valhalla is the runner-up.

### Why
| Need | GraphHopper (self-host) | Valhalla (self-host) | OpenRouteService (hosted) |
|---|---|---|---|
| Hard "no steps" | `road_class == STEPS` -> `priority: 0` in custom model [V] | Only a soft `step_penalty` (seconds); `type=wheelchair` just changes defaults, it does **not** forbid steps [V] | `avoid_features: ["steps"]` (foot/wheelchair) [S] |
| Hard "max grade X" | `average_slope` and `max_slope` encoded values, signed by direction [V]; e.g. `if max_slope > X -> priority 0` | `use_hills` 0..1 is a **soft** penalty "based on elevation change and grade" [V]; no documented pedestrian max_grade | wheelchair `restrictions.maximum_incline` (3/6/10/15%) [S]; ORS staff say it does **not** distinguish up vs down [S], and it appears to rely on OSM `incline` tags, which are almost absent in Lisbon (see Q2) [U] |
| Prefer downhill over uphill | Yes: slope is signed per direction, so `average_slope > 3 -> priority *0.5` while downhill is untouched [V] | Not controllable per direction from the API [U] | No [S] |
| Custom extra edges (lifts/funiculars) | Inject synthetic ways into the PBF before import (osmium); per-request `areas` + `priority 0` can switch a closed lift off at query time [V: areas/per-request custom_model work on POST /route for custom profiles] | Inject ways into PBF; `elevator_penalty` exists [V] | Not possible on hosted API |
| Custom DEM | `pmtiles` elevation provider (Terrarium-encoded, e.g. Mapterhorn or self-built from DGT LiDAR), or implement `ElevationProvider` [V] | Skadi `.hgt` tiles, fixed 1-arc-second grid [U]: you can feed DGT data but only at ~25-30 m resolution | Only ORS's own SRTM-based data on hosted |
| Cost | Free code; a Lisbon clip (~tens of MB) fits in <1 GB RAM: a ~EUR 4-6/month VPS or free-tier ARM VM [U] | Same order | Free: 2,000 directions/day, 40/min [V, openrouteservice.org/plans] |
| Hosted free tier | GraphHopper hosted Free plan = 500 credits/day, non-commercial, **no flexible mode, so no custom models** [S, docs.graphhopper.com plans] | No official hosted free tier | n/a |

Practical design: two profiles, `stroller_strict` (max grade e.g. 6%, steps forbidden) and `stroller_relaxed` (8-10%), with an uphill penalty and a mild downhill preference. Use `max_slope` as well as `average_slope`, because long OSM edges hide short steep bits. Turn off CH (flexible/LM mode) if you want per-request custom models. On a one-city graph latency is fine.

Sources: GraphHopper custom models https://github.com/graphhopper/graphhopper/blob/master/docs/core/custom-models.md ; GH elevation https://github.com/graphhopper/graphhopper/blob/master/docs/core/elevation.md ; Valhalla API ref https://valhalla.github.io/valhalla/api/route/api-reference/ ; ORS routing options https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options ; ORS plans https://openrouteservice.org/plans/ ; ORS incline Q&A https://ask.openrouteservice.org/t/how-to-get-inclines-to-work-for-wheelchair-routing-with-ors-localhost/4746 ; GH plans https://docs.graphhopper.com/openapi/section/plans-and-rate-limits

---

## 2. OSM data quality in central Lisbon

### Own measurement (Overpass, 2026-11-17, bbox 38.705..38.720 N, -9.150..-9.125 E, covering Baixa, Chiado, Bairro Alto, Alfama, Mouraria)
- 4,049 highway ways: 1,847 footway, 506 **steps**, 397 pedestrian, 638 residential.
- **Steps are densely mapped.** 506 `highway=steps` ways. 80% carry `incline` (direction up/down, not a grade value), 32% `step_count`, 53% `ramp`, 58% `handrail`. Only 1 has `ramp:stroller`, 10 have `ramp:wheelchair`.
- **Grade tags are essentially absent.** `incline` is on 0.7% of footways/pedestrian ways (16/2,271) and 1.4% of roads (17/1,209). Grade **must come from a DEM**. Any engine that uses tagged incline (likely ORS wheelchair) is blind here.
- **Surface is well tagged, width and smoothness are not.** `surface` is on 72% of pedestrian ways (dominant value `sett`, i.e. calçada) and 84% of roads. `smoothness` is on 12%, `width` on 11%, `wheelchair` on 0.7%.
- **Sidewalks are partly mapped.** 50% of roads have a `sidewalk*` tag, there are 566 separate `footway=sidewalk` ways, and 302 crossing ways. Network connectivity between separate sidewalks and street centrelines is a known OSM weak point. Expect some odd detours; test on real trips.
- **Lifts are mapped.** Elevador do Castelo (EMEL, `fee=no`), Elevador da Sé (EMEL, `opening_hours=08:00-21:00`), Santa Justa (Carris, `fee=yes`), the Graça funicular lift building, and an "Elevador de Santa Luzia" node. Funiculars are mapped as `railway=funicular` (Glória, Lavra, Bica, Graça), which foot routers will **not** use. Model them as synthetic edges.
- Script and raw output: the query is reproducible in Overpass Turbo with the bbox above.

### Studies and community
- No Lisbon-specific OSM sidewalk/steps completeness study was found. A Lisbon circuity study (MDPI IJGI 2021) notes that "only a small fraction" of Lisbon streets carry sidewalk info: https://www.mdpi.com/2220-9964/10/7/453 [S]
- General: sidewalks are rarely mapped in OSM (Germany study, AGILE 2015): https://www.researchgate.net/publication/284725347 ; accessibility tagging schema review (ISPRS 2020): https://isprs-archives.copernicus.org/articles/XLIII-B4-2020/229/2020/ [S]
- CML "Lisbon for All" accessible-tourism routes (Baixa, Belém, Parque das Nações; green/orange grading, tested by wheelchair users): useful as ground truth, not as a graph. https://storage.sbcevents.com/assets/2024/04/lisbon-accessible-tourism-cml-1-1.pdf [S]
- Metro de Lisboa station accessibility open data (Willeasy, 2023): https://www.dn.pt/local/lisboa-vai-ter-informacao-essencial-para-pessoas-com-mobilidade-reduzida-16637495.html [S]
- Wheelmap (POI wheelchair tags) and OpenSidewalks (US-focused schema): no evidence of a Lisbon campaign [U].
- **Implication:** the parents' "narrow / bad surface" marks fill exactly the gap (width, smoothness) that OSM lacks. Consider contributing confirmed findings back to OSM (`width`, `smoothness`, `ramp:stroller`). Do not import anonymous crowd marks blindly; ODbL and OSM import guidelines apply.

---

## 3. Elevation data

### Recommendation
**Use the DGT national LiDAR DTM (2 m, or 0.5 m) for continental Portugal, CC BY 4.0.** Use it both for routing (to build an elevation file for GraphHopper) and for your own segment-checker, which you need anyway to grade Google polylines.

- DGT LiDAR coverage of continental Portugal (campaign completed ~2025): DTM at 0.5 m and 2 m, bare-earth ground class, "dados abertos ... licença CC-BY-4.0", downloadable from the DGT Centro de Dados (cdd.dgterritorio.gov.pt). Source: DGT webinar, July 2025: https://www.dgterritorio.gov.pt/sites/default/files/ficheiros-artigos/Apresentacoes/2025/5-Webinar_LiDAR_15jul2025.pdf [V-ish, official slides]. Point density ~10 pts/m2 and vertical accuracy better than 10 cm per EuroGeographics [S]. A GMT.jl tutorial shows a bbox downloader for MDT-2m tiles: https://www.generic-mapping-tools.org/GMTjl_doc/tutorials/dgt_lidar/tut_dgt_lidar.html [S]. Older coastal 2 m DTMs (2011, 2014-15) are on dados.gov.pt under CC BY 4.0 [V].
- Alternatives: Copernicus GLO-30 is a **DSM** (it includes buildings), which is bad in dense historic streets. SRTM/CGIAR are 30-90 m. EU-DEM v1.1 (25 m) is legacy. Mapterhorn (global terrain PMTiles, used by GraphHopper since March 2026) mixes sources; whether it includes DGT LiDAR for Portugal was **not confirmed**. https://www.graphhopper.com/blog/2026/03/23/more-precise-elevation-data-for-graphhopper/
- Lisboa Aberta: no city DTM found in this search [U]. CML geodados may have contours; check.

### How routers ingest it
- **GraphHopper:** `graph.elevation.provider: pmtiles` with a manually downloaded Terrarium-encoded PMTiles file (zoom 12 recommended per the GH forum, roughly 15-20 m pixels at Lisbon's latitude) [V forum: https://discuss.graphhopper.com/t/more-precise-elevation-data-for-graphhopper/9936 ; PR #3287]. To use DGT 2 m: GeoTIFF -> Terrarium RGB tiles at zoom 14-15 -> PMTiles (gdal + rio-rgbify/Mapterhorn tooling). Check that the GH provider reads higher zooms; otherwise write a small `ElevationProvider` reading the GeoTIFF (documented extension point) [V].
- **Valhalla:** `.hgt` Skadi tiles at 1 arc-second [U], so most of the LiDAR benefit is lost.
- **Bridges/viaducts:** a bare-earth DTM gives fake grades on bridges. Interpolate elevation along `bridge=yes`/`tunnel=yes` ways (GraphHopper does this) and in your own checker.
- Smooth the per-edge grade over ~10-20 m windows. Raw 2 m DTM plus kerbs can create spurious 15% spikes.

---

## 4. Lisbon lifts and funiculars (status as of Nov 2026)

| Link | Endpoints | Operator / cost | Status Nov 2026 | Stroller |
|---|---|---|---|---|
| Elevador da Glória (funicular) | Restauradores to São Pedro de Alcântara | Carris | **Closed** since the 3 Sep 2025 derailment (16 dead). To be replaced by a new funicular; reopening expected H1 2029 [S: RFM 2026-09-02; Lisbon Tourism 2026-10-19]. Replacement bus 51E. | n/a |
| Elevador do Lavra (funicular) | Largo da Anunciada to R. Câmara Pestana (Torel) | Carris | **Closed**, under technical review, no date [S] | Cars have steps, so poor |
| Elevador da Bica (funicular) | R. de São Paulo to Calhariz | Carris | **Closed**, no date [S] | Poor |
| Elevador de Santa Justa (vertical lift) | R. do Ouro (Baixa) to Largo do Carmo | Carris, EUR 6.20 on board (2 trips) | **Closed** since Sep 2025. Assessment is "most advanced" but there is no date; an earlier summer-2026 target slipped [S: RFM 2026-09-02, lisbontourism.org 2026-10-19] | Flat entry when open |
| Funicular da Graça | R. dos Lagares (Mouraria) to Miradouro Sophia de Mello Breyner (Graça) | Moved from EMEL to **Carris** after the accident; EUR 4.30 occasional ticket (2 trips), navegante pass holders get priority | **Open** since 30 Apr 2026, daily ~07:00-20:45/21:00, 14 passengers [S: DN, Observador 2026-05-14] | Built 2021 as an accessibility link; OSM `wheelchair=yes` [V OSM] |
| Elevador R. dos Fanqueiros/R. da Madalena | Baixa (R. Fanqueiros 170-178) to R. da Madalena | EMEL, free | Listed by EMEL [V emel.pt]; hours not published there | Yes (OSM `wheelchair=yes`) |
| Elevador do Mercado do Chão do Loureiro | R. da Madalena level to Costa do Castelo | EMEL, free | Listed by EMEL [V] | Yes |
| Elevador da Sé | Campo das Cebolas/R. Afonso de Albuquerque to the Sé | EMEL, free | 08:00-21:00 (TimeOut, OSM) [S] | Yes, 8 persons |
| Elevador R. Norberto Araújo ("Santa Luzia") | Alfama to Portas do Sol | EMEL, free | Listed by EMEL [V] | Yes [U] |
| Escadinhas da Saúde (escalators) | Martim Moniz to Castelo slope | EMEL | Escalators: **not suitable** for strollers | No |
| Metro station lifts (e.g. Baixa-Chiado, Martim Moniz/Intendente new lifts July 2026) | Station-internal level changes | Metro | Metro set up 24h lift maintenance cover at Baixa-Chiado in Jan 2026 [S rr.pt]. Possible "vertical shortcut" Baixa to Chiado; check whether it requires passing ticket gates [U] | Usually |

EMEL source: https://www.emel.pt/pt/mobilidade/mais-mobilidade/acessiblidade-pedonal/ . Lisbon Tourism guide: https://www.lisbontourism.org/lisbon-funiculars-elevators/ . RFM one-year piece: https://rfm.pt/atualidade/23708/gloria-bica-lavra-e-santa-justa-um-ano-depois-do-acidente-o-que-aconteceu-aos-elevadores-historicos-de-lisboa . Graça hours: https://observador.pt/2026/05/14/funicular-da-graca-em-lisboa-alarga-horario-para-operar-mais-seis-horas-diarias/

### Open data
- **"Elevadores e Ascensores"** (CML, map service, **CC0**), on dados.gov.pt, metadata updated 17 Nov 2026: https://dados.gov.pt/en/datasets/elevadores-e-ascensores/ [V]. The source is the CML geodados ArcGIS hub.
- **"Elevadores e escadas rolantes"** (EMEL lifts/escalators, CSV with location and **opening hours**) on dadosabertos.cm-lisboa.pt (the host did not resolve from here today; it is mirrored via dados.gov.pt) [S].
- **Carris GTFS** (official) is on Mobility Database/Transitland (feed active Nov 2026: https://www.transit.land/feeds/f-carris~pt). Whether funiculars/Santa Justa appear as routes (historically 50E-54E) is not confirmed; it carries no outage status. Neither feed models EMEL free lifts [U].
- **Recommendation:** maintain a small hand-curated `lifts.yaml` (≈8 entries: endpoints as coordinates, hours, fee, stroller-ok, status, last_checked). Seed it from the CC0 dataset and OSM, and re-check monthly. The status of Carris's lifts changes by press release, not data feed.

---

## 5. Google Maps URLs

- Format: `https://www.google.com/maps/dir/?api=1&origin=..&destination=..&waypoints=a|b|c&travelmode=walking` (`api=1` mandatory; URL ≤ 2,048 chars) [V: https://developers.google.com/maps/documentation/urls/get-started].
- **Waypoint limits (official):** "up to three waypoints supported on mobile browsers, and a maximum of nine waypoints supported otherwise". "Waypoints are not supported on all Google Maps products" and are then silently ignored [V]. In practice on a phone the link opens the Google Maps **app** (the "otherwise" case, 9). If it opens in a mobile browser, only 3 are kept. Design for **≤3 waypoints per link** so it is safe everywhere, splitting into several links (you split at lifts anyway).
- `waypoint_place_ids` is optional (must be paired with `waypoints`). `dir_action=navigate` may start navigation; ignored where unsupported [V].
- `travelmode=walking`: Google computes its own walking path **between consecutive waypoints**. Waypoints are stopovers (legs), not "via" points, and there is no via/pass-through option in Maps URLs [V: param list]. Google will draw whatever it considers best between your points, including stairs. Hence the need for the check in Q6, and for placing waypoints where they force the right street (mid-block on the intended street, not at junctions).
- **Shared `maps.app.goo.gl` links still work.** Google's Aug 2025 goo.gl shutdown spared links generated by Google apps such as Maps sharing [S: https://developers.googleblog.com/en/google-url-shortener-links-will-no-longer-be-available/]. Expand by following HTTP 30x `Location` headers server-side (no API). The final URL looks like `https://www.google.com/maps/dir/<A>/<B>/@lat,lng,z/data=!4m..!4m..!1m5!1m1!1s0x..:0x..!2m2!1d<lng>!2d<lat>...!3e2`. It contains **only origin/destination/stops (names, feature IDs, often coordinates) and the mode (`!3e2` = walking)**, **not route geometry**. Drag-through points may appear as extra coordinate entries [U]. The `data=` format is undocumented and can change, so parse defensively and fall back to geocoding the names. Short links to a place resolve to `/maps/place/...` with `!3d<lat>!4d<lng>`. Parser references: npm `gmaps-expand-shorturl`, `google-maps-link-parser` [S].
- Consequence: to "check a user-supplied Google route" you must **re-compute** it (Routes API, same stops, WALKING). The result may differ from the alternative the user picked in the app. Say so in the reply ("Google's default route for these stops ...").

---

## 6. Getting the route Google will draw: Routes API

- **Pricing (official table, Nov 2026):** Compute Routes **Essentials**: **10,000 free billable events/month**, then $5.00/1,000 (tiers down to $0.38). Pro: 5,000 free, then $10/1,000 [V: https://developers.google.com/maps/billing-and-pricing/pricing]. Essentials covers "basic features with a maximum of 10 intermediate waypoints"; traffic-aware and optimisation features bump the tier [V: https://developers.google.com/maps/documentation/routes/usage-and-billing]. WALKING + ≤10 intermediates + `routes.polyline` field mask stays Essentials [U: polyline field not explicitly tiered]. Pilot volume (≈10 parents) is far below 10k/month: **$0**, but a billing account (card) is required. **Set a hard quota cap** (e.g. 300/day) in Cloud Console to avoid surprise bills.
- Output: `routes.polyline.encodedPolyline` (or `geoJsonLinestring` with `polylineEncoding`); `routes.legs.polyline` per leg. Intermediates support `via: true` (pass-through) in the Routes API but not in Maps URLs. To mirror what the URL will draw, use `via: false` (stopovers).
- **Will the API polyline equal the app's drawn route?** It is not guaranteed (different backends, live conditions, alternatives), but walking is usually the same default route [U]. Mitigate with dense waypoints near ambiguous spots.

### ToS: this is the key risk, and the EEA matters
- **Global terms** (non-EEA billing): 3.2.3(e) "will not use the Google Maps Core Services with or near a non-Google Map"; Routes SST 19.2 "must not use Google Maps Content from the Routes API in conjunction with a non-Google map"; 19.3 cache lat/lng ≤ 30 days; 3.2.3(a) no export/extract "for use outside the Services"; 3.2.3(c) no creating content from Google Maps Content [V: https://cloud.google.com/maps-platform/terms , https://cloud.google.com/maps-platform/terms/maps-service-terms].
- **EEA terms** apply to billing accounts with an EEA address, e.g. Portugal (effective 8 Jul 2025; Google committed not to reintroduce the removed clauses until 2035) [V/S: https://cloud.google.com/terms/maps-platform/eea]. The "No Use With Non-Google Maps" and "No Re-Creating Google Products" restrictions are **gone** from the EEA restrictions list. Routes API SST 20.1 only says "Customer may not use description or steps from the Routes API With any Map"; 20.2 keeps the 30-day lat/lng cache limit. No scraping, no caching beyond the SST, and no creating content (incl. no ML training) remain [V: https://cloud.google.com/terms/maps-platform/eea/maps-service-terms , last modified 2026-10-28].
- **Assessment of "check a Google polyline against OSM steps + DEM grades":**
  - Under **EEA terms: low risk.** You process the polyline transiently inside your application, show no map, and return a Google Maps link plus a textual warning ("~40 m of stairs near Rua X"). Keep it transient. **Do not store** Google polylines beyond 30 days (preferably not at all; store only your own verdict). **Do not** use Google routes to fix or augment OSM/your graph (that is "creating content"/extraction). **Do not** draw the Google route on an OSM/Leaflet map.
  - Under **global terms: moderate risk.** "Use in conjunction with a non-Google map" arguably covers map-matching against OSM data, though no map is displayed. Make sure the Cloud billing account has a **Portuguese/EEA billing address** so the EEA terms govern.
  - **Never** scrape google.com/maps pages for route geometry (3.2.3(a)). Use only the Routes API.
  - Maps URLs (the link you send) need no key and are not billed.
- Non-commercial status does not exempt you from the ToS. Show "Google Maps" attribution in the message where Google-derived info is shown [U on exact attribution rules for text-only use].

---

## 7. Messenger channel

### Recommendation: **Telegram for the pilot.** Revisit WhatsApp only if parents refuse Telegram.

| | Telegram Bot API | WhatsApp Cloud API |
|---|---|---|
| Setup | BotFather token in minutes; no company, no phone number, free. Bot API 10.4 (9 Nov 2026) [V: https://core.telegram.org/bots/api] | Meta developer app + Business portfolio + a phone number not registered on the consumer WhatsApp app. The test number can only message ≤5 verified recipients. Production needs a display-name review. Business verification is needed to lift messaging limits [U] |
| Price | Free | Per-message billing since 1 Jul 2025. **From 1 Oct 2026 service (user-initiated, 24h window) messages are charged after 1,000 free/month per number**; a payment method on file is needed beyond the free tier [V: https://developers.facebook.com/docs/whatsapp/pricing]. A 10-parent pilot fits in 1,000/month, but the card and Meta onboarding are still required. Utility templates in Portugal ~EUR 0.014 [S] |
| AI policy | None | Since 15 Jan 2026 WhatsApp ToS restrict "AI Providers" offering **general-purpose** assistants (separate pricing/market rules) [V: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers]. A task-specific route bot using an LLM internally is probably fine, but it is a grey zone [U] |
| Location | User can send a pin or a **live location**. `KeyboardButton.request_location` gives one-tap "send my location" in private chats. The bot receives `location` with `live_period`/`heading` updates via `edited_message` [U: from API knowledge] | Location messages supported; **no live location to bots** [U] |
| Buttons | Inline keyboards with callback data, URL buttons (good for "Open in Google Maps" per segment), unlimited [U] | Reply buttons max 3, list messages max 10 rows [U] |
| Privacy | Bot sees only messages sent to it (privacy mode in groups). Cloud chats, not E2E. Users are identified by a numeric user_id; the phone number is not shared unless the user taps a contact button | E2E to Meta's Cloud API endpoint; the business sees users' **phone numbers** (worse for "anonymous" marks) |

For anonymity: store only a salted hash of the Telegram user_id (for rate-limiting/abuse) and keep marks as `(lat, lon, type, created_at)` with no user link. Round timestamps to the day.

---

## 8. LLM role and geocoding

### LLM
- **Sensible, but keep it narrow.** Use the LLM for (a) intent/slot extraction from free text in PT/EN/RU ("from Rua Augusta 1 to Miradouro da Graça, avoid stairs") into a strict JSON schema (structured outputs), (b) normalising place names/transliteration before geocoding, and (c) composing short multilingual replies from a template + facts. **Do not** let it pick routes, grades or lift status; those come from deterministic code.
- Short Google Maps URLs, coordinates and pins should bypass the LLM entirely (regex/parse first).
- Cost: Claude Haiku 5.5 (`claude-haiku-5-5`) at $0.10 / $0.50 per M input/output tokens, or Sonnet 5.5 (`claude-sonnet-5-5`) at $2 / $10 (Anthropic model table cached 2026-11-03). A ~1.5k-token request is ~$0.0002 on Haiku, so a pilot costs cents per month. Use prompt caching for the fixed system prompt.
- Privacy: messages contain home/kindergarten addresses. Minimise what you send (strip usernames), and do not log raw texts longer than needed.

### Geocoding
| Option | Fit for Lisbon pilot | Constraints |
|---|---|---|
| **Nominatim (OSMF public)** | Good for addresses and named places | Max 1 req/s total for the app; identifying User-Agent; cache results; **no autocomplete**; ODbL attribution [V: https://operations.osmfoundation.org/policies/nominatim/] |
| **Photon (photon.komoot.io)** | Better fuzzy/typo-tolerant search on OSM data; good partner to an LLM | Fair use, "extensive usage will be throttled or banned", no SLA [S: https://github.com/komoot/photon]; self-hostable (country extract) |
| **Google Geocoding / Places (New)** | Best POI recall (cafés, clinics, "Pingo Doce Graça") | Geocoding: 10,000 free/month then $5/1,000 [V pricing]. EEA terms: Geocoding lat/lng cache ≤30 days (some fields longer). **Places content may not be displayed with any map** in the EEA [S]. Fine for text-only bot use within the free caps |
| Parse Google link | Free | Most users will paste Google links, so this covers the main path without any geocoder |

Recommendation: expand/parse Google links first, then Nominatim (cached, 1 rps), then Photon as fuzzy fallback. Add Google Places Text Search only if parents' POI queries fail often (stays within the free cap at pilot scale; set quotas).

---

## Blocking / notable risks
1. **Google route-check legality** depends on the EEA terms applying (Portuguese billing address). Under global terms it is a grey zone. Never store or redraw Google geometry.
2. **Route mismatch.** Google may draw a different path between your waypoints than your engine chose (stairs!). This is the core product risk. Mitigation: verify with Routes API, then iteratively add or move waypoints (≤3 per link for mobile-browser safety; 9 in app) and re-verify; if still bad, split into more links.
3. **Grades must come from a DEM.** OSM `incline` is ~0% populated. The DGT LiDAR DTM (CC BY 4.0) is the right source but needs a one-off conversion pipeline; bridges need interpolation.
4. **Lift availability is volatile.** Santa Justa, Bica, Lavra and Glória are all closed in Nov 2026; only the Graça funicular (Carris, paid) plus the free EMEL lifts (Fanqueiros, Chão do Loureiro, Sé, Norberto Araújo) are usable. Use a hand-curated status file.
5. **WhatsApp** requires Meta onboarding and a card, and the AI-provider policy is ambiguous. Telegram avoids all of this.
6. **Hosted GraphHopper free tier cannot run custom models.** Self-hosting is mandatory for the recommended engine (cheap).

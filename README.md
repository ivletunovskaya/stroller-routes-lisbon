# Stroller Routes Lisbon

Помощник для родителей с колясками в Лиссабоне. Он подсказывает, как дойти до места без лестниц и изнуряющих подъёмов, или честно говорит, что такого пути нет.

*A helper for parents with strollers in Lisbon: a walking route with no stairs and no punishing climbs, or an honest "there is no such route". English summary below.*

## Зачем

Google Maps ведёт кратчайшим путём, а в Лиссабоне он часто идёт по лестницам-улицам и крутым склонам, хотя рядом есть обход: подняться на городском лифте и спуститься с горы или пройти по ровной улице чуть длиннее. Родители узнают об этом уже в пути, а потом заранее отказываются от кофе, похода в гости или прогулки в другой район.

## Как это будет работать

Это не отдельная карта, а помощник рядом с Google Maps, бот в Telegram:

- присылаешь ссылку на кафе или адрес, получаешь путь без лестниц и крутых подъёмов (с городскими лифтами) и ссылку, которая открывает этот путь в Google Maps;
- присылаешь маршрут из Google Maps, получаешь список мест на нём, где будет лестница или крутой участок, и обход;
- если пути без препятствий нет, помощник прямо так и говорит и предлагает наименее плохой вариант;
- родители могут одним нажатием отметить «узко» или «плохое покрытие», и эти отметки копятся анонимно.

Проект некоммерческий. Первая версия только для Лиссабона.

## Статус

Идёт планирование. Код ещё не написан. Первый шаг — проверка рисков на нескольких реальных маршрутах: находит ли маршрутизатор пути без лестниц и удерживают ли их ссылки Google Maps.

## Документы

- [План: требования и технический план](docs/plans/2026-11-17-1612-feat-stroller-routes-lisbon-plan.md)
- [Техническое исследование: маршрутизаторы, рельеф, лифты, Google, Telegram](docs/research/2026-11-17-technical-research.md)

## Как сделано

Идею, требования, технический план и их ревью я прорабатываю вместе с Claude Code и навыками [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin) от Every: `ce-brainstorm` → `ce-doc-review` → `ce-plan` → `ce-work`.

## English summary

Google Maps' shortest walking route in Lisbon often climbs stairs and steep streets, even when a flat detour or a public lift exists. Parents learn this mid-walk and end up skipping trips. This project is a non-commercial Telegram assistant that works alongside Google Maps: send it a place or a Google route, and it returns a stair-free, low-slope route (using Lisbon's public lifts) as a Google Maps link, or flags the stairs on your route, or says honestly that no such route exists. Routing uses self-hosted GraphHopper on OpenStreetMap data with Portugal's LiDAR terrain model. Status: planning; the first step is a risk check on real routes.

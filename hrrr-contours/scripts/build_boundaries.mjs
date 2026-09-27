// Land, coastline, country and US state boundaries as one small GeoJSON file.
import { readFileSync, writeFileSync } from "node:fs";
import { feature, mesh } from "topojson-client";

const load = (p) => JSON.parse(readFileSync(new URL(`../node_modules/${p}`, import.meta.url)));
const world = load("world-atlas/countries-50m.json");
const land = load("world-atlas/land-50m.json");
const us = load("us-atlas/states-10m.json");

const round = (c) => (typeof c[0] === "number" ? [+c[0].toFixed(4), +c[1].toFixed(4)] : c.map(round));
const f = (kind, geometry) => ({ type: "Feature", properties: { kind }, geometry: { ...geometry, coordinates: round(geometry.coordinates) } });

const out = {
  type: "FeatureCollection",
  features: [
    ...feature(land, land.objects.land).features.map((g) => f("land", g.geometry)),
    f("coast", mesh(land, land.objects.land)),
    f("country", mesh(world, world.objects.countries, (a, b) => a !== b)),
    f("state", mesh(us, us.objects.states, (a, b) => a !== b)),
  ],
};
writeFileSync(new URL("../web/boundaries.json", import.meta.url), JSON.stringify(out));

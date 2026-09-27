// Land, coastline, country and US state boundaries as one small GeoJSON file.
import { readFileSync, writeFileSync } from "node:fs";
import { feature, mesh } from "topojson-client";

const load = (p) => JSON.parse(readFileSync(new URL(`../node_modules/${p}`, import.meta.url)));
const world = load("world-atlas/countries-50m.json");
const land = load("world-atlas/land-50m.json");
const us = load("us-atlas/states-10m.json");

// Split lines where they jump across the antimeridian (+179.9 -> -179.9);
// otherwise the jump is drawn as a line across the whole world.  Also drop the
// artificial edge Antarctica's outline runs along at -90 (web mercator clamps
// it to 85 S, where it would show as a ring around the pole on the globe).
function splitDateline(geometry) {
  if (geometry.type !== "MultiLineString" && geometry.type !== "LineString") return geometry;
  const lines = geometry.type === "LineString" ? [geometry.coordinates] : geometry.coordinates;
  const out = [];
  for (const line of lines) {
    let cur = [];
    for (let i = 0; i < line.length; i++) {
      if (Math.abs(line[i][1]) > 85) { if (cur.length > 1) out.push(cur); cur = []; continue; }
      if (i && Math.abs(line[i][0] - line[i - 1][0]) > 180) { if (cur.length > 1) out.push(cur); cur = []; }
      cur.push(line[i]);
    }
    if (cur.length > 1) out.push(cur);
  }
  return { type: "MultiLineString", coordinates: out };
}

const round = (c) => (typeof c[0] === "number" ? [+c[0].toFixed(4), +c[1].toFixed(4)] : c.map(round));
const f = (kind, geometry) => {
  geometry = splitDateline(geometry);
  return { type: "Feature", properties: { kind }, geometry: { ...geometry, coordinates: round(geometry.coordinates) } };
};

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

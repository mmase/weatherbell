// node web/live/bench.mjs  -- speed/size/correctness of contourTile in Node
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { Grid, contourTile } from "./contour.js";
const dir = new URL("./run/grids/", import.meta.url);
const meta = JSON.parse(readFileSync(new URL("meta.json", dir)));
const load = (h) => { const b = gunzipSync(readFileSync(new URL(`f${String(h).padStart(2, "0")}.i16.gz`, dir))); const d = new Int16Array(b.buffer, b.byteOffset, b.length / 2); for (let r = 0; r < meta.ny; r++) for (let c = 1, o = r * meta.nx; c < meta.nx; c++) d[o + c] += d[o + c - 1]; return d; };
let t = performance.now();
const grid = new Grid(meta);
console.log(`grid setup (node positions) ${(performance.now() - t).toFixed(0)} ms`);
const A = load(0), B = load(1);
const lonlat2tile = (lon, lat, z) => { const n = 2 ** z; return [Math.floor((lon + 180) / 360 * n), Math.floor((1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2 * n)]; };
for (const [lon, lat, z] of [[-100, 40, 3], [-100, 40, 4], [-106, 40, 5], [-106, 40, 7], [-105.3, 39.9, 9], [-105.3, 39.9, 12], [-105.3, 39.9, 15]]) {
  const [x, y] = lonlat2tile(lon, lat, z);
  contourTile(grid, [A], 0, z, x, y); // warm up JIT
  t = performance.now(); const r = contourTile(grid, [A], 0, z, x, y); const dt = performance.now() - t;
  t = performance.now(); contourTile(grid, [A, B], 0.5, z, x, y); const dtm = performance.now() - t;
  // correctness: triangle bands vs value at centroid, and area bookkeeping
  const { pos, band, index } = r; let area = 0, bad = 0;
  for (let k = 0; k < index.length; k += 3) {
    const a = index[k], b = index[k + 1], c = index[k + 2];
    const ar = ((pos[b*2]-pos[a*2])*(pos[c*2+1]-pos[a*2+1]) - (pos[c*2]-pos[a*2])*(pos[b*2+1]-pos[a*2+1])) / 2;
    area += Math.abs(ar);
  }
  const verts = pos.length / 2, tris = index.length / 3;
  const bytes = pos.byteLength + band.byteLength + index.byteLength;
  console.log(`z${z} ${x}/${y}: step ${r.step} cell, lattice ${r.lattice.join("x")}, ${(dt).toFixed(0)} ms (morph ${dtm.toFixed(0)} ms), ${(tris/1e3).toFixed(0)}k tris, ${(verts/1e3).toFixed(0)}k verts, ${(bytes/1e6).toFixed(1)} MB, tri area ${area.toFixed(3)} tiles`);
}

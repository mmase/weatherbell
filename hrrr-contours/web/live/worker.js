// Contouring worker: holds the grid geometry (per pyramid level) and a few
// decoded forecast hours, and turns tile requests into GPU-ready triangle buffers.
import { Grid, contourTile, levelMeta } from "./contour.js";

let meta = null;
const grids = new Map();  // level k -> Grid
const fields = new Map(); // "hour@k" -> Int16Array (band units * scale), oldest first
const FIELD_BUDGET = 48e6; // bytes of decoded hours kept per worker
let fieldBytes = 0;
const gridFor = (k) => { if (!grids.has(k)) grids.set(k, new Grid(levelMeta(meta, k))); return grids.get(k); };

self.onmessage = (e) => {
  const m = e.data;
  if (m.type === "meta") {
    meta = m.meta; grids.clear();
    self.postMessage({ type: "ready" });
  } else if (m.type === "field") {
    const key = `${m.hour}@${m.k}`;
    if (fields.has(key)) return;
    fields.set(key, new Int16Array(m.buf)); fieldBytes += m.buf.byteLength;
    // least recently used first; always keep the two newest (a morph pair)
    while (fieldBytes > FIELD_BUDGET && fields.size > 2) {
      const [k0, v0] = fields.entries().next().value;
      fields.delete(k0); fieldBytes -= v0.byteLength;
    }
  } else if (m.type === "tile") {
    const k = m.k || 1, get = (h) => { const f = fields.get(`${h}@${k}`); if (f) { fields.delete(`${h}@${k}`); fields.set(`${h}@${k}`, f); } return f; };
    const A = get(m.hA), B = m.hB == null ? null : get(m.hB);
    if (!A || (m.hB != null && !B)) { self.postMessage({ type: "tile", id: m.id, missing: true }); return; }
    const t0 = performance.now();
    const r = contourTile(gridFor(k), B ? [A, B] : [A], m.w, m.z, m.x, m.y, m.spacing, m.allowCoarse);
    const ms = performance.now() - t0;
    if (!r) { self.postMessage({ type: "tile", id: m.id, empty: true, ms }); return; }
    // compact for upload: tile-local positions as uint16 (1/128 px at 512 px)
    const n = r.pos.length / 2, pos = new Uint16Array(r.pos.length);
    for (let i = 0; i < r.pos.length; i++) {
      const v = r.pos[i];
      pos[i] = v <= -0.25 ? 0 : v >= 1.75 ? 65535 : Math.round((v + 0.25) * 32767.5);
    }
    self.postMessage({ type: "tile", id: m.id, pos, band: r.band, index: r.index, n, ms },
                     [pos.buffer, r.band.buffer, r.index.buffer]);
  }
};

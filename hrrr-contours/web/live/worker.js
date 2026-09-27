// Contouring worker: holds the grid geometry and a few decoded forecast hours,
// and turns tile requests into GPU-ready triangle buffers.
import { Grid, contourTile } from "./contour.js";

let grid = null;
const fields = new Map(); // hour -> Int16Array (degF * scale)

self.onmessage = (e) => {
  const m = e.data;
  if (m.type === "meta") {
    grid = new Grid(m.meta);
    self.postMessage({ type: "ready" });
  } else if (m.type === "field") {
    fields.set(m.hour, new Int16Array(m.buf));
    while (fields.size > 6) fields.delete(fields.keys().next().value);
  } else if (m.type === "tile") {
    const A = fields.get(m.hA), B = m.hB == null ? null : fields.get(m.hB);
    if (!A || (m.hB != null && !B)) { self.postMessage({ type: "tile", id: m.id, missing: true }); return; }
    const t0 = performance.now();
    const r = contourTile(grid, B ? [A, B] : [A], m.w, m.z, m.x, m.y, m.spacing, m.allowCoarse);
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

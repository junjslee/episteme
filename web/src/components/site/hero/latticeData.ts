import * as THREE from "three";

/**
 * Deterministic lattice generator for the hero scene.
 *
 * Produces ~N luminous node positions in a shallow box volume plus a set of
 * near-neighbour edges (the hash chain). Seeded so the layout is stable across
 * renders — no hydration surprises, no reshuffle on frameloop toggles.
 */
export interface LatticeData {
  positions: Float32Array;
  scales: Float32Array;
  phases: Float32Array;
  tones: Float32Array;
  edgePositions: Float32Array;
  edgeAlong: Float32Array;
  edgePhase: Float32Array;
  count: number;
  edgeCount: number;
}

export function buildLattice(count: number, seed = 20240164): LatticeData {
  let s = seed >>> 0;
  const rnd = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };

  const RX = 10.5;
  const RY = 5.8;
  const ZMIN = -12;
  const ZMAX = 5;

  const positions = new Float32Array(count * 3);
  const scales = new Float32Array(count);
  const phases = new Float32Array(count);
  const tones = new Float32Array(count);
  const pts: THREE.Vector3[] = [];

  for (let i = 0; i < count; i++) {
    const x = (rnd() * 2 - 1) * RX;
    const y = (rnd() * 2 - 1) * RY;
    const z = ZMIN + rnd() * (ZMAX - ZMIN);
    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
    scales[i] = 0.5 + rnd() * 1.5;
    phases[i] = rnd();
    tones[i] = rnd();
    pts.push(new THREE.Vector3(x, y, z));
  }

  // Spatial hash so edge-building stays roughly O(n) instead of O(n^2).
  const cell = 2.4;
  const grid = new Map<string, number[]>();
  const key = (x: number, y: number, z: number) =>
    `${Math.floor(x / cell)},${Math.floor(y / cell)},${Math.floor(z / cell)}`;
  pts.forEach((p, i) => {
    const k = key(p.x, p.y, p.z);
    const bucket = grid.get(k);
    if (bucket) bucket.push(i);
    else grid.set(k, [i]);
  });

  const maxEdges = Math.floor(count * 0.5);
  const epos: number[] = [];
  const ealong: number[] = [];
  const ephase: number[] = [];
  let edges = 0;

  for (let i = 0; i < count && edges < maxEdges; i++) {
    if (rnd() > 0.4) continue;
    const p = pts[i];
    let best = -1;
    let bestD = 1e9;
    for (let dx = -1; dx <= 1; dx++)
      for (let dy = -1; dy <= 1; dy++)
        for (let dz = -1; dz <= 1; dz++) {
          const arr = grid.get(key(p.x + dx * cell, p.y + dy * cell, p.z + dz * cell));
          if (!arr) continue;
          for (const j of arr) {
            if (j <= i) continue;
            const d = p.distanceToSquared(pts[j]);
            if (d < bestD && d > 0.05) {
              bestD = d;
              best = j;
            }
          }
        }
    if (best >= 0 && bestD < 5.5) {
      const q = pts[best];
      epos.push(p.x, p.y, p.z, q.x, q.y, q.z);
      ealong.push(0, 1);
      const ph = rnd();
      ephase.push(ph, ph);
      edges++;
    }
  }

  return {
    positions,
    scales,
    phases,
    tones,
    edgePositions: new Float32Array(epos),
    edgeAlong: new Float32Array(ealong),
    edgePhase: new Float32Array(ephase),
    count,
    edgeCount: edges,
  };
}

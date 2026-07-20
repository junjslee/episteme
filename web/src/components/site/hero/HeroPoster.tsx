/**
 * Static hero poster.
 *
 * Rendered instead of the WebGL scene when the visitor prefers reduced motion,
 * and as the pre-hydration placeholder so the hero never flashes empty. Pure
 * SVG + CSS gradients in the same palette as the live scene: cyan lattice,
 * translucent gate, amber verified pulse.
 */

interface PosterNode {
  x: number;
  y: number;
  r: number;
  o: number;
}

/**
 * Deterministic pseudo-random scatter — same seed as the 3D lattice so the
 * poster reads as a still frame of the same composition.
 */
function buildPosterNodes(): PosterNode[] {
  let s = 20240164;
  const rnd = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
  const out: PosterNode[] = [];
  for (let i = 0; i < 190; i++) {
    const x = rnd() * 1200;
    const y = rnd() * 700;
    const dCenter = Math.hypot(x - 600, y - 350) / 700;
    out.push({
      x,
      y,
      r: 0.7 + rnd() * 1.9,
      o: 0.18 + (1 - dCenter) * 0.5 * rnd(),
    });
  }
  return out;
}

const NODES = buildPosterNodes();

export function HeroPoster() {
  return (
    <div className="absolute inset-0 overflow-hidden" aria-hidden>
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 45%, rgba(87,199,255,0.10), transparent 70%), radial-gradient(ellipse 40% 40% at 78% 78%, rgba(242,177,52,0.07), transparent 70%)",
        }}
      />
      <svg
        className="absolute inset-0 h-full w-full poster-drift"
        viewBox="0 0 1200 700"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <radialGradient id="gateGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#57c7ff" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#57c7ff" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="edgeFade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#57c7ff" stopOpacity="0.05" />
            <stop offset="50%" stopColor="#a9e2ff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#57c7ff" stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* chain edges */}
        <g stroke="url(#edgeFade)" strokeWidth="0.7">
          {NODES.slice(0, 70).map((n, i) => {
            const m = NODES[(i * 7 + 11) % NODES.length];
            const d = Math.hypot(n.x - m.x, n.y - m.y);
            if (d > 150) return null;
            return <line key={i} x1={n.x} y1={n.y} x2={m.x} y2={m.y} />;
          })}
        </g>

        {/* lattice nodes */}
        <g fill="#8fd8ff">
          {NODES.map((n, i) => (
            <circle key={i} cx={n.x} cy={n.y} r={n.r} opacity={n.o} />
          ))}
        </g>

        {/* the gate */}
        <circle cx="600" cy="350" r="300" fill="url(#gateGlow)" />
        <rect
          x="392"
          y="222"
          width="416"
          height="256"
          fill="rgba(87,199,255,0.03)"
          stroke="rgba(87,199,255,0.42)"
          strokeWidth="1"
        />
        <rect
          x="392"
          y="222"
          width="416"
          height="256"
          fill="none"
          stroke="rgba(242,177,52,0.30)"
          strokeWidth="1"
          strokeDasharray="3 9"
        />

        {/* action particle, verified side */}
        <circle cx="600" cy="350" r="5" fill="#f2b134" opacity="0.95" />
        <circle cx="600" cy="350" r="15" fill="#f2b134" opacity="0.16" />
        <circle cx="600" cy="350" r="30" fill="#f2b134" opacity="0.06" />
      </svg>
    </div>
  );
}

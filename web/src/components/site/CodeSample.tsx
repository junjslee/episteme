import { Sectioned } from "@/components/ui/Sectioned";

const lines = [
  { t: "prompt", v: "$ episteme guide" },
  { t: "out-header", v: "EPISTEME · active guidance · v1.0-rc" },
  { t: "out", v: "" },
  { t: "sig", v: "▶ surface: 8m fresh · domain=complicated · tacit_call=false" },
  { t: "out", v: "" },
  { t: "mut", v: "core question" },
  { t: "out", v: "  Does the CP10 scaffolding land the four-trigger detector, six-field" },
  { t: "out", v: "  validator, and hash-chained writer without orphan regression?" },
  { t: "out", v: "" },
  { t: "warn", v: "▲ unknowns (3) — proceed blocked until ≥1 cleared:" },
  { t: "out", v: "  1. hot-path latency under 100ms p95 on non-cascade ops?" },
  { t: "out", v: "  2. sensitive-path coverage vs. kernel-adjacent UPPERCASE docs?" },
  { t: "out", v: "  3. deferred-discovery writer: one hash-chained record per entry?" },
  { t: "out", v: "" },
  { t: "ok", v: "✓ disconfirmation declared · 3 conditions" },
  { t: "ok", v: "✓ hypothesis stated · confidence=0.82" },
  { t: "out", v: "" },
  { t: "mut", v: "active protocols (4)" },
  { t: "out", v: "  · cascade-graceful-degrade      (conf 88% · invoked 4)" },
  { t: "out", v: "  · fence-pattern-validate        (conf 94% · invoked 11)" },
  { t: "out", v: "  · hash-chain-self-verify        (conf 91% · invoked 2)" },
  { t: "out", v: "  · disconfirmation-required      (conf 82% · invoked 6)" },
  { t: "out", v: "" },
  { t: "chain", v: "↳ chain head: a3c9f1b2 · seq 0013 · 12s ago" },
];

const toneMap: Record<string, string> = {
  prompt: "text-ash",
  "out-header": "text-bone",
  out: "text-ash",
  sig: "text-chain",
  mut: "text-bone",
  warn: "text-unknown",
  ok: "text-verified",
  chain: "text-chain",
};

export function CodeSample() {
  return (
    <Sectioned
      index="05"
      label="active guidance"
      kicker="the kernel speaks"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          <code className="font-display">episteme guide</code>
          <br />
          <span className="text-ash">
            reads your surface and tells you what&apos;s missing.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          One CLI. No config. Reads <code className="text-bone">reasoning-surface.json</code>,
          walks the hash chain, surfaces active protocols, and names the
          unknowns that are blocking the next step.
        </p>
      </div>

      <pre className="overflow-x-auto border border-hairline bg-surface/30 p-6 font-mono text-[0.8125rem] leading-relaxed">
        <code className="block">
          {lines.map((l, i) => (
            <div key={i} className={toneMap[l.t] ?? "text-ash"}>
              {l.v || "\u00A0"}
            </div>
          ))}
        </code>
      </pre>
    </Sectioned>
  );
}

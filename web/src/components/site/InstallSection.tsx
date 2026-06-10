import Link from "next/link";

/**
 * InstallSection — the closing beat: how do I get it, in ~60 seconds.
 *
 * Renamed from CTASection. Install commands are the REAL quick start from
 * the repo README (Claude Code plugin marketplace — two commands — then
 * seed + verify from any shell). The old `pipx install episteme` line was
 * fabricated: the package is not published to PyPI.
 *
 * The terminal preview absorbs the killed CodeSample with v2 vocabulary:
 * a real interrogation verdict — every line traces to the chain's actual
 * first record (lesson lh_71f88adef21147df, verdict proceed). Lines stamp
 * in via `.stamp-in` (steps() stagger, class-owned so the global
 * prefers-reduced-motion block forces the final visible state).
 *
 * Server component, zero client JS.
 */

const INSTALL_LINES: { t: string; v: string; c?: string }[] = [
  { t: "comment", v: "# inside claude code" },
  { t: "cmd", v: "/plugin marketplace add junjslee/episteme" },
  { t: "cmd", v: "/plugin install episteme@episteme" },
  { t: "comment", v: "# then, from any shell" },
  {
    t: "shell",
    v: "episteme init && episteme doctor",
    c: "# seed memory · verify wiring",
  },
];

// Transcribed from the engine's real first interrogation
// (.episteme/interrogation.json, 2026-06-10) — the decision that became
// protocol №1. Not a styled mockup: counts, weakest link, and
// disconfirmation match the artifact.
const TERMINAL_LINES: { t: string; v: string }[] = [
  { t: "prompt", v: "# interrogation №1 — transcribed from the chain" },
  { t: "out-header", v: "EPISTEME · epistemic interrogation" },
  { t: "out", v: "" },
  { t: "mut", v: "conclusion under review" },
  { t: "out", v: '  "merge release PR #94 — cut v1.7.0-rc1"' },
  { t: "out", v: "" },
  { t: "sig", v: "⊢ claims decomposed · 3 — all load-bearing" },
  { t: "ok", v: "✓ verified against evidence — CI green ×3, release flow cited" },
  { t: "ok", v: "✓ opposition argued — a public rc the operator hasn't read" },
  { t: "warn", v: "▲ weakest link — ‘merge it’ may not have covered the release PR" },
  { t: "ok", v: "✓ disconfirmation — operator reverts the tag on waking" },
  { t: "out", v: "" },
  { t: "mut", v: "verdict · proceed" },
  { t: "chain", v: "↳ lesson lh_71f88adef21147df → protocol №1 · chained" },
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

const STAMP_STEP_MS = 140;

export function InstallSection() {
  return (
    <section id="install" className="border-t border-hairline">
      <div className="mx-auto max-w-7xl px-6 py-20 md:px-12 md:py-28">
        <div className="flex flex-col items-start gap-8 border border-hairline bg-surface/30 p-10 md:p-16">
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            05 / install · ≈ 60 seconds
          </span>
          <h2 className="max-w-3xl font-display text-[2.25rem] leading-[1.05] text-bone md:text-[3.25rem]">
            Keep thinking — even when the model can finish your sentences.
            <br />
            <span className="text-ash">
              Two commands. Then every load-bearing conclusion earns its
              confidence before it lands.
            </span>
          </h2>

          <div className="grid w-full grid-cols-1 gap-5 lg:grid-cols-2">
            <div className="flex flex-col gap-3">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
                the commands
              </span>
              <div className="border border-hairline bg-void p-5 font-mono text-[0.8125rem] leading-relaxed text-ash">
                {INSTALL_LINES.map((l, i) => (
                  <div key={i}>
                    {l.t === "comment" && (
                      <span className="text-muted">{l.v}</span>
                    )}
                    {l.t === "cmd" && <span className="text-bone">{l.v}</span>}
                    {l.t === "shell" && (
                      <>
                        <span className="text-muted">$</span>{" "}
                        <span className="text-bone">{l.v}</span>{" "}
                        <span className="text-muted">{l.c}</span>
                      </>
                    )}
                  </div>
                ))}
              </div>
              <Link
                href="https://github.com/junjslee/episteme#quick-start"
                target="_blank"
                rel="noopener"
                className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted transition-colors hover:text-chain"
              >
                prefer a clone? full quick start →
              </Link>
            </div>

            <div className="flex flex-col gap-3">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
                what it sounds like
              </span>
              <pre className="overflow-x-auto border border-hairline bg-void p-5 font-mono text-[0.75rem] leading-relaxed">
                <code className="block">
                  {TERMINAL_LINES.map((l, i) => (
                    <div
                      key={i}
                      className={`stamp-in ${toneMap[l.t] ?? "text-ash"}`}
                      style={{ animationDelay: `${i * STAMP_STEP_MS}ms` }}
                    >
                      {l.v || " "}
                    </div>
                  ))}
                </code>
              </pre>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Link
              href="https://github.com/junjslee/episteme"
              className="group inline-flex items-center gap-2 border border-line bg-bone px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-void transition-colors hover:bg-chain"
            >
              read the source
              <span className="transition-transform group-hover:translate-x-0.5">
                →
              </span>
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 border border-line px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-bone transition-colors hover:border-chain hover:text-chain"
            >
              see the dashboard
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

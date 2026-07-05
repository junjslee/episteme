"use client";

import { useState } from "react";
import { Sectioned } from "@/components/ui/Sectioned";
import { CornerMarkers } from "@/components/ui/CornerMarkers";

/**
 * SurfaceWalk — the hands-on beat. The visitor authors the four fields of a
 * real reasoning surface and runs the op against the gate. Incomplete
 * thinking blocks, complete thinking passes and seals onto the ledger —
 * the same admission rule reasoning_surface_guard enforces, in miniature.
 *
 * The decision is transcribed from the kernel's own history (Event 142/143,
 * 2026-07-05): the four-round adversarial review that removed the read-only
 * exemption, ratified and merged. Nothing here is invented except the final
 * ledger hash, which is display-only and labeled as such.
 *
 * Client component; state is four booleans + one attempt flag. All motion
 * is class-owned (stamp-in / flash-chain) so the global
 * prefers-reduced-motion block forces end states.
 */

type FieldKey = "knowns" | "unknowns" | "assumptions" | "disconfirmation";

const FIELDS: {
  key: FieldKey;
  label: string;
  accent: string; // border + text tone when authored
  dot: string;
  content: string;
  gateDemand: string; // what the gate says when this field is missing
}[] = [
  {
    key: "knowns",
    label: "knowns",
    accent: "border-verified/40 text-verified",
    dot: "bg-verified",
    content:
      "Four adversarial review rounds: writers leaked through every allowlist — the parsing layer itself is the flaw.",
    gateDemand: "knowns — empty; state what is verified, not what sounds right",
  },
  {
    key: "unknowns",
    label: "unknowns",
    accent: "border-unknown/40 text-unknown",
    dot: "bg-unknown",
    content:
      "If the 3.10–3.12 CI matrix goes red on the merge, a version-specific failure exists that the local run missed.",
    gateDemand:
      "unknowns — empty; the gate requires a conditional trigger + a specific observable",
  },
  {
    key: "assumptions",
    label: "assumptions",
    accent: "border-line text-bone",
    dot: "bg-ash",
    content:
      "A green local suite is a faithful proxy for the CI matrix — same tests, same gate.",
    gateDemand: "assumptions — empty; a hidden assumption is a hidden objective",
  },
  {
    key: "disconfirmation",
    label: "disconfirmation",
    accent: "border-disconfirm/40 text-disconfirm",
    dot: "bg-disconfirm",
    content:
      "If any existing guard test must be weakened for this to pass, the change is wrong — stop and escalate.",
    gateDemand:
      "disconfirmation — empty; name in advance what would prove this wrong",
  },
];

/** Ledger rows 00/01 are real records; 02 is the visitor's seal (display-only hash). */
const LEDGER_BASE = [
  { seq: "00", label: "genesis", hash: "sha256:GENESIS" },
  { seq: "01", label: "protocol №1 · sealed 2026-06-10", hash: "sha256:7679d5…" },
];

export function SurfaceWalk() {
  const [authored, setAuthored] = useState<Set<FieldKey>>(
    () => new Set<FieldKey>(["knowns"]),
  );
  const [attempt, setAttempt] = useState(0); // 0 = not yet run
  const [attemptedWith, setAttemptedWith] = useState(0); // authored count at last run

  const missing = FIELDS.filter((f) => !authored.has(f.key));
  const complete = missing.length === 0;
  const verdictShown = attempt > 0;
  const passed = verdictShown && attemptedWith === FIELDS.length;

  const author = (key: FieldKey) => {
    setAuthored((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const run = () => {
    setAttempt((n) => n + 1);
    setAttemptedWith(authored.size);
  };

  const reset = () => {
    setAuthored(new Set<FieldKey>(["knowns"]));
    setAttempt(0);
    setAttemptedWith(0);
  };

  return (
    <Sectioned
      id="walk"
      index="02"
      label="walk the surface"
      kicker="knowns → unknowns → assumptions → disconfirmation"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          Author the surface.
          <br />
          <span className="text-ash">Then try to run the op.</span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          A real decision from the kernel&apos;s own history, and the same
          admission rule the shipped gate enforces: until the four fields
          hold, the action does not run.
        </p>
      </div>

      <div className="relative">
        <CornerMarkers />
        <div className="grid grid-cols-1 gap-5 p-3 md:grid-cols-12">
          {/* Left — the surface being authored */}
          <div className="flex flex-col gap-3 md:col-span-7">
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
              reasoning surface · tap a field to author it
            </span>
            {FIELDS.map((f) => {
              const on = authored.has(f.key);
              return (
                <button
                  key={f.key}
                  type="button"
                  aria-pressed={on}
                  onClick={() => author(f.key)}
                  className={`group flex flex-col gap-2 border p-4 text-left transition-colors ${
                    on
                      ? `panel-gradient ${f.accent.split(" ")[0]}`
                      : "border-dashed border-line hover:border-ash"
                  }`}
                >
                  <span className="flex items-center gap-2 font-mono text-[0.6875rem] uppercase tracking-[0.16em]">
                    <span
                      className={`inline-block size-1 rounded-full ${on ? f.dot : "bg-line"}`}
                    />
                    <span className={on ? f.accent.split(" ")[1] : "text-ash"}>
                      {f.label}
                    </span>
                  </span>
                  {on ? (
                    <span
                      key={`${f.key}-${attempt}`}
                      className="stamp-in font-sans text-[0.875rem] leading-relaxed text-ash"
                    >
                      {f.content}
                    </span>
                  ) : (
                    <span className="font-mono text-[0.75rem] text-muted transition-colors group-hover:text-ash">
                      — empty. The agent has not thought here yet.
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Right — the op, the verdict, the ledger */}
          <div className="flex flex-col gap-5 md:col-span-5">
            <div className="flex flex-col gap-4 panel-gradient p-5">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                high-impact op
              </span>
              <code className="font-mono text-[0.875rem] text-bone">
                $ git push origin master
              </code>
              <button
                type="button"
                onClick={run}
                className="inline-flex w-fit items-center gap-2 border border-bone bg-bone px-4 py-2 font-mono text-[0.75rem] uppercase tracking-[0.12em] text-void transition-opacity hover:opacity-85"
              >
                run the op →
              </button>

              {verdictShown && (
                <div
                  key={attempt}
                  role="status"
                  className={`stamp-in flex flex-col gap-2 border-l-2 pl-4 ${
                    passed ? "border-verified" : "border-disconfirm"
                  }`}
                >
                  <span
                    className={`font-mono text-[0.75rem] uppercase tracking-[0.12em] ${
                      passed ? "text-verified" : "text-disconfirm"
                    }`}
                  >
                    {passed
                      ? "verdict · pass — surface admitted, op proceeds"
                      : "verdict · blocked — exit 2, op never ran"}
                  </span>
                  {!passed && (
                    <ul className="flex flex-col gap-1">
                      {missing.map((f) => (
                        <li
                          key={f.key}
                          className="font-mono text-[0.6875rem] leading-relaxed text-ash"
                        >
                          ✗ {f.gateDemand}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <div className="flex flex-col gap-3 panel-gradient p-5">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                cognitive ledger · append-only
              </span>
              {LEDGER_BASE.map((row) => (
                <div
                  key={row.seq}
                  className="flex items-baseline justify-between gap-3 border-b border-hairline pb-2"
                >
                  <span className="font-mono text-[0.6875rem] text-ash">
                    {row.seq} · {row.label}
                  </span>
                  <span className="font-mono text-[0.625rem] text-muted">
                    {row.hash}
                  </span>
                </div>
              ))}
              {passed ? (
                <div
                  key={`sealed-${attempt}`}
                  className="flash-chain flex items-baseline justify-between gap-3 border-b border-chain/40 pb-2"
                >
                  <span className="font-mono text-[0.6875rem] text-chain">
                    02 · your surface · sealed
                  </span>
                  <span className="font-mono text-[0.625rem] text-chain">
                    prev sha256:7679d5… → sha256:41d7c9…
                  </span>
                </div>
              ) : (
                <div className="flex items-baseline justify-between gap-3 border-b border-dashed border-line pb-2">
                  <span className="font-mono text-[0.6875rem] text-muted">
                    02 · awaiting an admitted surface
                  </span>
                  <span className="font-mono text-[0.625rem] text-muted">
                    prev sha256:7679d5… → ?
                  </span>
                </div>
              )}
              <p className="font-mono text-[0.625rem] leading-relaxed text-muted">
                rows 00–01 are the chain&apos;s real records; your seal&apos;s
                hash is display-only. every break in the link is visible —
                that is the point.
              </p>
            </div>

            <div className="flex items-center justify-between">
              <span className="font-mono text-[0.6875rem] text-muted">
                {complete
                  ? "surface complete — run it"
                  : `${FIELDS.length - missing.length}/4 fields authored`}
              </span>
              <button
                type="button"
                onClick={reset}
                className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash underline decoration-hairline underline-offset-4 transition-colors hover:text-bone"
              >
                reset
              </button>
            </div>
          </div>
        </div>
      </div>
    </Sectioned>
  );
}

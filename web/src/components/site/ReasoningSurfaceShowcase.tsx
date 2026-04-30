"use client";

import { useState } from "react";
import { Sectioned } from "@/components/ui/Sectioned";

// ── Real Reasoning Surfaces episteme produced on its own development ───────
//
// No fictional examples. No form for visitors to type into. These are real
// surfaces this project committed to during real Events. Names, dates, and
// outcomes match the audit trail in the repo. Visitors see what real
// validated surfaces look like and what they prevent.

interface Sample {
  id: string;
  tab: string;
  headline: string;
  what_happened: string;
  rs: {
    core_question: string;
    key_unknown: string;
    disconfirmation: string;
  };
  outcome: string;
  meta: {
    date: string;
    event: string;
    blueprint: string;
  };
}

const SAMPLES: Sample[] = [
  {
    id: "bundle",
    tab: "Stress proposed a bad bet",
    headline:
      "Operator wanted to ship four things at once. Three were irreversible. The kernel said: that's a category error.",
    what_happened:
      "It was Day 3 of a planned 7-day soak. Anxiety about IP leakage. The operator typed: privatize four docs, rewrite git history, cut the GA tag, end the soak — all today. Three of those operations cannot be undone once they're public. The kernel refused to let the bundle proceed without an adversarial review.",
    rs: {
      core_question:
        "Is the IP-leakage premise driving the bundle actually evidenced — or is it stress-state pattern-matching to a panic shape?",
      key_unknown:
        "Whether `gh api` signal-check has been run since the docs went public five days ago. The premise driving urgency is unmeasured.",
      disconfirmation:
        "Decomposition is wrong if signal-check at Day 7+ shows actual clone-and-weaponize evidence, OR if reversible halves leak the supposedly-protected content via git log.",
    },
    outcome:
      "The two reversible halves shipped that day (privatize the docs, apply the license). The two irreversible halves waited for Day 7 evidence. The signal-check came back clean. The history rewrite was never run. The kernel saved a public panic-rewrite that would have advertised exactly the panic the operator was trying to hide.",
    meta: {
      date: "2026-04-27",
      event: "Event 65",
      blueprint: "Axiomatic Judgment",
    },
  },
  {
    id: "automation",
    tab: "Manual tracking became automatic",
    headline:
      "Operator was hand-recording profile and policy changes. Every edit was a CLI step. The kernel was supposed to remember; it was forgetting.",
    what_happened:
      "Profile axes drift over time. Policy files get amended. The audit trail depends on each change being recorded. Manual CLI worked but was annoying. The operator asked: just listen for the file-system event and record automatically.",
    rs: {
      core_question:
        "Should editing the four canonical memory files (operator_profile, cognitive_profile, workflow_policy, agent_feedback) auto-emit a hash-chained envelope to profile_history / policy_history without operator intervention?",
      key_unknown:
        "Whether PostToolUse hooks fire reliably across Edit / Write / MultiEdit operations to capture diffs without race conditions on multi-file edits.",
      disconfirmation:
        "Auto-instrumentation is broken if editing operator_profile.md does NOT produce a new envelope in `profile_history.jsonl` with `auto_recorded: true` within 5 seconds of the PostToolUse firing.",
    },
    outcome:
      "Hooks installed via `episteme sync`. The next profile axis edit produced an auto-recorded envelope within the 5-second window. Manual CLI still works as fallback. Two of four chain streams now auto-populate; the remaining two are scoped for follow-up.",
    meta: {
      date: "2026-04-29",
      event: "Event 91",
      blueprint: "Architectural Cascade",
    },
  },
  {
    id: "honesty",
    tab: "Asked: are we really model-agnostic?",
    headline:
      "The README claimed the kernel runs anywhere. Operator pushed: prove it. The audit found: identity yes, enforcement Claude-shaped only.",
    what_happened:
      "Marketing surfaces had been calling the kernel \"model-agnostic.\" One adapter (Claude Code) was actually wired; four others (Cursor, Codex, opencode, Hermes) were documentation only. The operator asked for an honest accounting before the claim escaped further.",
    rs: {
      core_question:
        "Is the kernel's enforcement layer truly portable across Claude Code, Cursor, Codex, opencode, and Hermes — or is the model-agnostic claim aspirational at the hook level despite the markdown identity layer being portable?",
      key_unknown:
        "Whether other host runtimes have an equivalent of Claude Code's PreToolUse hook lifecycle that the kernel can intercept at — without rewriting hooks or downgrading to advisory-only.",
      disconfirmation:
        "The strong claim is defensible if the audit can name ≥ 2 hosts where the kernel's enforcement runs identically (not just the markdown layer). Today the audit names exactly 1: Claude Code.",
    },
    outcome:
      "The README claim was downgraded to honest scope: identity layer ports today; enforcement layer is Claude-shaped today. A 6-phase migration to defensible cross-adapter parity was sequenced (~12-15 working days). A canonical event schema stub was written as the migration target. The marketing surface now matches what the substrate actually does.",
    meta: {
      date: "2026-04-30",
      event: "Event 96",
      blueprint: "Axiomatic Judgment",
    },
  },
];

// ── Component ───────────────────────────────────────────────────────────────

export function ReasoningSurfaceShowcase() {
  const [activeId, setActiveId] = useState(SAMPLES[0].id);
  const sample = SAMPLES.find((s) => s.id === activeId) ?? SAMPLES[0];

  return (
    <Sectioned
      id="what-it-produces"
      index="01"
      label="what episteme produces"
      kicker="real surfaces · real outcomes · no fictional examples"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          Three real moments where the kernel changed an outcome.
          <br />
          <span className="text-ash">All on this project, this month.</span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          Every day this project ships, episteme&apos;s discipline runs against
          the team&apos;s own decisions. These are three of those moments —
          the actual Reasoning Surface that was committed, what the operator
          almost did instead, and what the kernel made visible before any
          irreversible step ran.
        </p>
      </div>

      {/* ── Tabs ── */}
      <div className="mb-6 grid grid-cols-1 gap-2 md:grid-cols-3">
        {SAMPLES.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setActiveId(s.id)}
            aria-pressed={s.id === activeId}
            className={
              "border px-5 py-4 text-left transition-colors " +
              (s.id === activeId
                ? "border-line bg-elevated/60"
                : "border-hairline bg-surface/30 hover:border-line/60 hover:bg-surface/50")
            }
          >
            <div
              className={
                "mb-1 font-mono text-[0.6875rem] uppercase tracking-[0.16em] " +
                (s.id === activeId ? "text-chain" : "text-muted")
              }
            >
              {s.meta.event} · {s.meta.date}
            </div>
            <div
              className={
                "font-sans text-[0.9375rem] leading-snug " +
                (s.id === activeId ? "text-bone" : "text-ash")
              }
            >
              {s.tab}
            </div>
          </button>
        ))}
      </div>

      {/* ── Sample card ── */}
      <article className="border border-hairline bg-elevated/40">
        <div className="border-b border-hairline p-6 md:p-10">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 border border-verified/40 px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-verified">
              <span className="size-1.5 rounded-full bg-verified" />
              accepted · exit 0 · hook allowed the op to proceed
            </span>
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted">
              blueprint · {sample.meta.blueprint}
            </span>
          </div>
          <h3 className="font-display text-[1.375rem] leading-tight text-bone md:text-[1.75rem]">
            {sample.headline}
          </h3>
          <p className="mt-4 font-sans text-[0.9375rem] leading-relaxed text-ash">
            {sample.what_happened}
          </p>
        </div>

        <div className="divide-y divide-hairline">
          <Field label="Core question" value={sample.rs.core_question} />
          <Field label="Key unknown" value={sample.rs.key_unknown} />
          <Field
            label="Disconfirmation pre-commit"
            value={sample.rs.disconfirmation}
          />
        </div>

        <div className="border-t border-hairline bg-surface/30 p-6 md:p-10">
          <div className="mb-2 font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
            What happened next
          </div>
          <p className="font-sans text-[0.9375rem] leading-relaxed text-bone">
            {sample.outcome}
          </p>
        </div>
      </article>

      <p className="mt-6 font-sans text-[0.875rem] leading-relaxed text-ash">
        These three Reasoning Surfaces were committed to disk before any
        high-impact operation ran. The hook either accepted them and let the
        operation proceed, or refused and surfaced the missing piece. Every
        decision episteme has touched is on the same shape — searchable,
        reviewable, comparable.
      </p>
    </Sectioned>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-1 gap-2 p-6 md:grid-cols-12 md:gap-8 md:p-10">
      <div className="md:col-span-3">
        <div className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
          {label}
        </div>
      </div>
      <p className="font-sans text-[0.9375rem] leading-relaxed text-bone md:col-span-9">
        {value}
      </p>
    </div>
  );
}

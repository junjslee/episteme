"use client";

import { useMemo, useState } from "react";
import { Sectioned } from "@/components/ui/Sectioned";
import { CornerMarkers } from "@/components/ui/CornerMarkers";

// ── Validation rules — mirror `core/hooks/reasoning_surface_guard.py` ───────
//
// These rules run client-side in the browser. They reproduce the load-bearing
// checks the real Strict Mode hook performs at the file-system boundary on
// `episteme/reasoning-surface@1`. Visitors feel the discipline directly:
// type into the form, the same kernel rules either accept or block.

const LAZY_TOKENS = new Set([
  "none",
  "n/a",
  "tbd",
  "해당 없음",
  "없음",
  "n.a.",
  "na",
  "...",
  "",
]);

const MIN_DISCONFIRMATION_LEN = 15;
const MIN_UNKNOWN_LEN = 15;
const MIN_CORE_QUESTION_LEN = 15;

interface SurfaceFields {
  core_question: string;
  knowns: string; // newline-separated
  unknowns: string; // newline-separated
  assumptions: string; // newline-separated
  disconfirmation: string;
}

const EMPTY: SurfaceFields = {
  core_question: "",
  knowns: "",
  unknowns: "",
  assumptions: "",
  disconfirmation: "",
};

const EXAMPLE: SurfaceFields = {
  core_question:
    "Is the p95 regression on /api/orders bottlenecked on a cache-shaped read pattern, or on a non-cache-shaped pattern (N+1 ORM query) where adding Redis would mask the symptom without fixing the cause?",
  knowns:
    "p95 latency on /api/orders has crossed the 800ms SLO threshold for 20 minutes per PagerDuty.\n/api/orders fans out to two tables (orders + line_items) via the ORM's default relation loader.\nRedis is already provisioned in this project's infrastructure.",
  unknowns:
    "Whether the per-request query plan shows a single SELECT with N row fetches (cache-amenable) or N+1 individual SELECTs (cache would mask, not fix). The query plan has not been pulled.",
  assumptions:
    "The user's framing (\"add a Redis cache\") implicitly assumes the bottleneck is cache-shaped. This is the load-bearing premise of the request.",
  disconfirmation:
    "p95 latency on /api/orders is unchanged or worse after the Redis read-through cache deploys to staging and runs for 24 hours under load comparable to production peak.",
};

const LAZY_DEMO: SurfaceFields = {
  core_question: "make it faster",
  knowns: "the endpoint is slow",
  unknowns: "tbd",
  assumptions: "none",
  disconfirmation: "if issues arise we'll fix them",
};

interface Violation {
  field: keyof SurfaceFields;
  label: string;
  reason: string;
}

function isLazy(s: string): boolean {
  return LAZY_TOKENS.has(s.trim().toLowerCase());
}

function splitLines(s: string): string[] {
  return s
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function validate(f: SurfaceFields): Violation[] {
  const out: Violation[] = [];

  // Core question — must be non-trivial.
  const cq = f.core_question.trim();
  if (!cq) {
    out.push({
      field: "core_question",
      label: "core_question",
      reason: "required field is empty",
    });
  } else if (isLazy(cq)) {
    out.push({
      field: "core_question",
      label: "core_question",
      reason: `lazy placeholder rejected ("${cq}")`,
    });
  } else if (cq.length < MIN_CORE_QUESTION_LEN) {
    out.push({
      field: "core_question",
      label: "core_question",
      reason: `too short (${cq.length} chars; min ${MIN_CORE_QUESTION_LEN})`,
    });
  }

  // Unknowns — at least one substantive entry.
  const unknowns = splitLines(f.unknowns);
  if (unknowns.length === 0) {
    out.push({
      field: "unknowns",
      label: "unknowns",
      reason: "must declare ≥ 1 unknown (one per line)",
    });
  } else {
    unknowns.forEach((u, i) => {
      if (isLazy(u)) {
        out.push({
          field: "unknowns",
          label: `unknowns[${i + 1}]`,
          reason: `lazy placeholder rejected ("${u}")`,
        });
      } else if (u.length < MIN_UNKNOWN_LEN) {
        out.push({
          field: "unknowns",
          label: `unknowns[${i + 1}]`,
          reason: `too short (${u.length} chars; min ${MIN_UNKNOWN_LEN})`,
        });
      }
    });
  }

  // Disconfirmation — concrete observable, not conditional vapor.
  const dc = f.disconfirmation.trim();
  if (!dc) {
    out.push({
      field: "disconfirmation",
      label: "disconfirmation",
      reason: "required field is empty",
    });
  } else if (isLazy(dc)) {
    out.push({
      field: "disconfirmation",
      label: "disconfirmation",
      reason: `lazy placeholder rejected ("${dc}")`,
    });
  } else if (dc.length < MIN_DISCONFIRMATION_LEN) {
    out.push({
      field: "disconfirmation",
      label: "disconfirmation",
      reason: `too short (${dc.length} chars; min ${MIN_DISCONFIRMATION_LEN})`,
    });
  } else if (
    /\b(if (issues|problems|something) (arises?|happens?|comes? up))\b/i.test(
      dc,
    ) &&
    !/\b(p\d+|latency|error rate|exit code|status \d+|metric|threshold|>\s*\d|<\s*\d)\b/i.test(
      dc,
    )
  ) {
    out.push({
      field: "disconfirmation",
      label: "disconfirmation",
      reason:
        "conditional-but-observable-less ('if issues arise') — declare a concrete metric",
    });
  }

  return out;
}

function fieldHasViolation(field: keyof SurfaceFields, vs: Violation[]): boolean {
  return vs.some((v) => v.field === field);
}

// ── UI ──────────────────────────────────────────────────────────────────────

export function ReasoningSurfaceValidator() {
  const [fields, setFields] = useState<SurfaceFields>(EMPTY);

  const violations = useMemo(() => validate(fields), [fields]);
  const isPristine =
    fields.core_question === "" &&
    fields.knowns === "" &&
    fields.unknowns === "" &&
    fields.assumptions === "" &&
    fields.disconfirmation === "";
  const passed = !isPristine && violations.length === 0;
  const denied = !isPristine && violations.length > 0;

  return (
    <Sectioned
      id="try-strict-mode"
      index="02"
      label="try strict mode"
      kicker="feel the discipline · 30 seconds, no install"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          A Reasoning Surface in your browser.
          <br />
          <span className="text-ash">
            Same rules the file-system hook runs.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          Type a Core Question, declare Unknowns, name Assumptions, commit to
          a Disconfirmation. The kernel either accepts or refuses — live, on
          every keystroke. Lazy placeholders (<code className="text-bone">none</code>,{" "}
          <code className="text-bone">n/a</code>, <code className="text-bone">tbd</code>,{" "}
          <code className="text-bone">해당 없음</code>) and conditional-but-observable-less
          phrasings (<code className="text-bone">&quot;if issues arise&quot;</code>) are
          rejected the same way the hook rejects them at <code className="text-bone">exit 2</code>.
        </p>
      </div>

      <div className="relative panel-gradient">
        <CornerMarkers />

        <div className="grid grid-cols-1 gap-0 md:grid-cols-2">
          {/* ── Form ── */}
          <div className="border-b border-hairline p-6 md:border-r md:border-b-0 md:p-8">
            <div className="mb-6 flex items-center justify-between">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                .episteme / reasoning-surface.json
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setFields(EXAMPLE)}
                  className="border border-hairline px-3 py-1 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash transition-colors hover:border-line hover:text-bone"
                >
                  load example
                </button>
                <button
                  type="button"
                  onClick={() => setFields(LAZY_DEMO)}
                  className="border border-hairline px-3 py-1 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash transition-colors hover:border-disconfirm hover:text-disconfirm"
                >
                  load doxa
                </button>
                <button
                  type="button"
                  onClick={() => setFields(EMPTY)}
                  className="border border-hairline px-3 py-1 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted transition-colors hover:border-line hover:text-ash"
                >
                  clear
                </button>
              </div>
            </div>

            <FormField
              id="rsv-core_question"
              label="core_question"
              hint="The one question this action answers (counters question-substitution)."
              value={fields.core_question}
              onChange={(v) =>
                setFields((s) => ({ ...s, core_question: v }))
              }
              violation={fieldHasViolation("core_question", violations)}
              rows={2}
            />

            <FormField
              id="rsv-knowns"
              label="knowns"
              hint="Verified facts, citations, measurements — one per line."
              value={fields.knowns}
              onChange={(v) => setFields((s) => ({ ...s, knowns: v }))}
              violation={fieldHasViolation("knowns", violations)}
              rows={3}
            />

            <FormField
              id="rsv-unknowns"
              label="unknowns"
              hint="Named, classifiable gaps — one per line. ≥ 15 chars each."
              value={fields.unknowns}
              onChange={(v) => setFields((s) => ({ ...s, unknowns: v }))}
              violation={fieldHasViolation("unknowns", violations)}
              rows={3}
            />

            <FormField
              id="rsv-assumptions"
              label="assumptions"
              hint="Load-bearing beliefs flagged for falsification — one per line."
              value={fields.assumptions}
              onChange={(v) =>
                setFields((s) => ({ ...s, assumptions: v }))
              }
              violation={fieldHasViolation("assumptions", violations)}
              rows={3}
            />

            <FormField
              id="rsv-disconfirmation"
              label="disconfirmation"
              hint="Concrete observable that would prove this plan wrong. ≥ 15 chars. No 'if issues arise.'"
              value={fields.disconfirmation}
              onChange={(v) =>
                setFields((s) => ({ ...s, disconfirmation: v }))
              }
              violation={fieldHasViolation("disconfirmation", violations)}
              rows={3}
            />
          </div>

          {/* ── Live verdict ── */}
          <div className="bg-surface/30 p-6 md:p-8">
            <div className="mb-6 flex items-center gap-3">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                kernel verdict · live
              </span>
              <VerdictPill
                isPristine={isPristine}
                passed={passed}
                denied={denied}
              />
            </div>

            {isPristine && <PristineHint />}
            {passed && <PassMessage />}
            {denied && <DenyMessage violations={violations} />}
          </div>
        </div>
      </div>

      <p className="mt-6 font-mono text-[0.6875rem] leading-relaxed text-muted">
        Validation runs entirely in your browser — no data leaves the page.
        The same rules execute at the file-system boundary in{" "}
        <code className="text-ash">core/hooks/reasoning_surface_guard.py</code>{" "}
        when you install episteme as a Claude Code plugin. Hook behavior is
        identical: invalid surface → <code className="text-ash">exit 2</code>{" "}
        → high-impact op refused.
      </p>
    </Sectioned>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

interface FormFieldProps {
  id: string;
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  violation: boolean;
  rows?: number;
}

function FormField({
  id,
  label,
  hint,
  value,
  onChange,
  violation,
  rows = 2,
}: FormFieldProps) {
  return (
    <div className="mb-5">
      <div className="mb-1 flex items-baseline justify-between">
        <label
          htmlFor={id}
          className={
            "font-mono text-[0.75rem] uppercase tracking-[0.16em] " +
            (violation ? "text-disconfirm" : "text-bone")
          }
        >
          {label}
        </label>
        <span className="font-mono text-[0.6875rem] text-muted">
          {value.length} chars
        </span>
      </div>
      <p className="mb-2 font-mono text-[0.6875rem] leading-relaxed text-muted">
        {hint}
      </p>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        spellCheck={false}
        className={
          "block w-full resize-y border bg-elevated/40 p-3 font-mono text-[0.8125rem] leading-relaxed text-bone outline-none transition-colors placeholder:text-whisper focus:bg-elevated/60 " +
          (violation
            ? "border-disconfirm/60 focus:border-disconfirm"
            : "border-hairline focus:border-line-strong")
        }
      />
    </div>
  );
}

function VerdictPill({
  isPristine,
  passed,
  denied,
}: {
  isPristine: boolean;
  passed: boolean;
  denied: boolean;
}) {
  if (isPristine) {
    return (
      <span className="inline-flex items-center gap-2 border border-hairline px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted">
        <span className="size-1.5 rounded-full bg-muted" />
        awaiting input
      </span>
    );
  }
  if (passed) {
    return (
      <span className="inline-flex items-center gap-2 border border-verified/40 px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-verified">
        <span className="size-1.5 rounded-full bg-verified" />
        accepted · exit 0
      </span>
    );
  }
  if (denied) {
    return (
      <span className="inline-flex items-center gap-2 border border-disconfirm/40 px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-disconfirm">
        <span className="size-1.5 rounded-full bg-disconfirm status-pulse" />
        denied · exit 2
      </span>
    );
  }
  return null;
}

function PristineHint() {
  return (
    <div className="space-y-3 font-mono text-[0.8125rem] leading-relaxed text-ash">
      <p>
        Type a Core Question. Declare Unknowns. Name Assumptions. Commit to a
        Disconfirmation.
      </p>
      <p className="text-muted">
        Or click{" "}
        <span className="text-bone">load example</span> for a real Reasoning
        Surface, or{" "}
        <span className="text-disconfirm">load doxa</span> to see what the
        kernel rejects.
      </p>
      <div className="border-t border-hairline pt-3 font-mono text-[0.6875rem] leading-relaxed text-muted">
        Validation criteria:
        <ul className="mt-2 space-y-1">
          <li>· core_question · ≥ 15 chars · not a lazy placeholder</li>
          <li>· unknowns · ≥ 1 entry · each ≥ 15 chars · no lazy tokens</li>
          <li>
            · disconfirmation · ≥ 15 chars · concrete observable · no
            &quot;if issues arise&quot;
          </li>
          <li>· lazy tokens rejected: none, n/a, tbd, 해당 없음, 없음</li>
        </ul>
      </div>
    </div>
  );
}

function PassMessage() {
  return (
    <div className="space-y-3 font-mono text-[0.8125rem] leading-relaxed">
      <p className="text-verified">
        ✓ Reasoning Surface accepted · would proceed at the file-system boundary.
      </p>
      <p className="text-ash">
        All required fields present. Disconfirmation is concrete. No lazy
        placeholders. The hook would write the surface to disk, allow the
        high-impact op to proceed, and stamp a calibration record under{" "}
        <code className="text-bone">~/.episteme/telemetry/</code>.
      </p>
      <p className="text-muted">
        In Strict Mode this is{" "}
        <code className="text-ash">exit 0</code>. In advisory mode it&apos;s
        the same — the difference between modes only matters when the surface{" "}
        <em>fails</em> validation.
      </p>
    </div>
  );
}

function DenyMessage({ violations }: { violations: Violation[] }) {
  return (
    <div className="space-y-3 font-mono text-[0.8125rem] leading-relaxed">
      <p className="text-disconfirm">
        ✗ Execution would be blocked by Episteme Strict Mode.
      </p>
      <p className="text-ash">
        Missing or invalid Reasoning Surface. The hook (
        <code className="text-bone">core/hooks/reasoning_surface_guard.py</code>
        ) rejects the surface and exits with code 2. The high-impact op does
        not run. The agent must re-author the surface.
      </p>
      <div className="border-t border-hairline pt-3">
        <p className="mb-2 text-bone">Violations:</p>
        <ul className="space-y-1.5">
          {violations.map((v, i) => (
            <li key={i} className="flex gap-3 text-ash">
              <span className="shrink-0 text-disconfirm">·</span>
              <span>
                <code className="text-bone">{v.label}</code>
                <span className="text-muted"> — </span>
                {v.reason}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <p className="border-t border-hairline pt-3 text-muted">
        Fix the violations above and the verdict flips to{" "}
        <code className="text-verified">accepted · exit 0</code>.
      </p>
    </div>
  );
}

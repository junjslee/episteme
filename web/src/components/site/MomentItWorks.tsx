"use client";

import { motion } from "motion/react";

/**
 * "The moment it works" — the block, then the repair.
 *
 * The stderr lines are transcribed from the live hook
 * (core/hooks/reasoning_surface_guard.py): the strict-mode lead, the
 * REASONING SURFACE INCOMPLETE header that names the skipped COGNITIVE MOVE
 * rather than just the missing schema field, and the advisory-mode pointer.
 * Where the real message quotes numeric minimum lengths those are elided with
 * an ellipsis rather than invented here.
 */

type Tone = "err" | "warn" | "dim" | "ok" | "key" | "str" | "plain" | "prompt";

const toneClass: Record<Tone, string> = {
  err: "text-disconfirm",
  warn: "text-unknown",
  dim: "text-muted",
  ok: "text-verified",
  key: "text-chain",
  str: "text-ash",
  plain: "text-ash",
  prompt: "text-bone",
};

const BLOCK_LINES: { t: Tone; v: string }[] = [
  { t: "prompt", v: "$ git push --force origin master" },
  { t: "plain", v: "" },
  { t: "err", v: "Execution blocked by Episteme Strict Mode: no valid Reasoning" },
  { t: "err", v: "Surface or interrogation verdict exists for this high-impact op." },
  { t: "plain", v: "" },
  { t: "warn", v: "REASONING SURFACE INCOMPLETE: high-impact op" },
  { t: "warn", v: "`git push --force origin master` with cognitive move(s)" },
  { t: "warn", v: "skipped — Frame · Core Question discipline — counters" },
  { t: "warn", v: "question substitution (Kahneman)." },
  { t: "dim", v: "Surface fails validation on: core_question, disconfirmation." },
  { t: "dim", v: "Disconfirmation must be a concrete observable condition (…)." },
  { t: "plain", v: "" },
  { t: "dim", v: "Per-project advisory mode (not recommended) is enabled by" },
  { t: "dim", v: "`touch .episteme/advisory-surface`." },
];

const REPAIR_LINES: { t: Tone; v: string }[] = [
  { t: "prompt", v: "$ cat .episteme/reasoning-surface.json" },
  { t: "plain", v: "" },
  { t: "key", v: '  "core_question":' },
  { t: "str", v: '    "Does force-pushing master destroy commits that exist' },
  { t: "str", v: '     only on the remote?"' },
  { t: "key", v: '  "unknowns": [' },
  { t: "str", v: '    "If origin/master holds commits absent locally, this' },
  { t: "str", v: '     push deletes them irrecoverably"' },
  { t: "key", v: "  ]," },
  { t: "key", v: '  "disconfirmation":' },
  { t: "str", v: '    "If git rev-list origin/master ^HEAD returns any commit,' },
  { t: "str", v: '     abort the push and rebase instead."' },
  { t: "plain", v: "" },
  { t: "ok", v: "✓ surface accepted · op admitted · recorded to the chain" },
];

function Terminal({
  label,
  lines,
  accent,
  delay,
}: {
  label: string;
  lines: { t: Tone; v: string }[];
  accent: "disconfirm" | "verified";
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.7, delay, ease: [0, 0, 0.2, 1] }}
      className="flex min-w-0 flex-col"
    >
      <div
        className={`flex items-center gap-2 border border-b-0 px-4 py-2.5 font-mono text-[0.625rem] uppercase tracking-[0.16em] ${
          accent === "disconfirm"
            ? "border-disconfirm/35 bg-disconfirm/[0.05] text-disconfirm"
            : "border-verified/35 bg-verified/[0.05] text-verified"
        }`}
      >
        <span className="inline-block size-1.5 rounded-full bg-current" />
        {label}
      </div>
      <pre className="overflow-x-auto border border-hairline bg-elevated/70 p-4 font-mono text-[0.75rem] leading-[1.7] md:p-5">
        <code className="block">
          {lines.map((l, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.18, delay: delay + 0.35 + i * 0.055 }}
              className={toneClass[l.t]}
            >
              {l.v || " "}
            </motion.div>
          ))}
        </code>
      </pre>
    </motion.div>
  );
}

export function MomentItWorks() {
  return (
    <section id="the-moment" className="border-b border-hairline">
      <div className="mx-auto max-w-7xl px-6 py-24 md:px-12 md:py-32">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.6 }}
          className="mb-14 flex max-w-2xl flex-col gap-5"
        >
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            01 / the moment it works
          </span>
          <h2 className="font-display text-[2.25rem] leading-[1.08] text-bone md:text-[3.25rem]">
            The agent tried. The gate said no.
          </h2>
          <p className="font-sans text-[1.0625rem] leading-relaxed text-ash">
            This is the whole product in one screen. An irreversible command was
            about to run without anyone writing down what they knew. The gate is
            deterministic — it doesn&apos;t argue, it just holds — and it names the
            thinking that got skipped, not merely the field that was blank. Then
            the work gets done, and the command goes through.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
          <Terminal
            label="blocked"
            lines={BLOCK_LINES}
            accent="disconfirm"
            delay={0}
          />
          <Terminal
            label="re-authored · admitted"
            lines={REPAIR_LINES}
            accent="verified"
            delay={0.18}
          />
        </div>
      </div>
    </section>
  );
}

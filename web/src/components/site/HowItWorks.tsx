"use client";

import { motion } from "motion/react";

/**
 * "How it works" — Declare → Gate → Learn.
 *
 * Marketing surface: warm, plain language, no jargon walls. Each step carries a
 * small inline SVG that echoes the hero's visual vocabulary (nodes, a gate
 * plane, a chain) so the three-beat explanation and the 3D scene read as one
 * system.
 */

function DeclareGlyph() {
  return (
    <svg viewBox="0 0 64 64" fill="none" className="h-12 w-12" aria-hidden>
      <rect x="12" y="10" width="40" height="44" stroke="currentColor" strokeWidth="1" opacity="0.4" />
      <line x1="19" y1="22" x2="45" y2="22" stroke="currentColor" strokeWidth="1.5" />
      <line x1="19" y1="30" x2="39" y2="30" stroke="currentColor" strokeWidth="1.5" opacity="0.75" />
      <line x1="19" y1="38" x2="43" y2="38" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
      <circle cx="15" cy="22" r="1.6" fill="currentColor" />
      <circle cx="15" cy="30" r="1.6" fill="currentColor" opacity="0.75" />
      <circle cx="15" cy="38" r="1.6" fill="currentColor" opacity="0.55" />
    </svg>
  );
}

function GateGlyph() {
  return (
    <svg viewBox="0 0 64 64" fill="none" className="h-12 w-12" aria-hidden>
      <rect x="24" y="8" width="16" height="48" stroke="currentColor" strokeWidth="1" opacity="0.45" />
      <rect x="24" y="8" width="16" height="48" stroke="currentColor" strokeWidth="1" strokeDasharray="2 6" />
      <circle cx="12" cy="32" r="3" fill="currentColor" />
      <line x1="16" y1="32" x2="23" y2="32" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 3" />
      <circle cx="52" cy="32" r="3" fill="currentColor" opacity="0.35" />
      <line x1="41" y1="32" x2="48" y2="32" stroke="currentColor" strokeWidth="1.5" opacity="0.35" />
    </svg>
  );
}

function LearnGlyph() {
  return (
    <svg viewBox="0 0 64 64" fill="none" className="h-12 w-12" aria-hidden>
      <circle cx="16" cy="20" r="3.5" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="44" cy="16" r="3.5" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="30" cy="36" r="3.5" stroke="currentColor" strokeWidth="1.2" />
      <circle cx="48" cy="46" r="3.5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="19" y1="21.5" x2="27" y2="34" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="41" y1="18" x2="33" y2="33" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
      <line x1="33" y1="38" x2="45" y2="44" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
    </svg>
  );
}

const STEPS = [
  {
    n: "01",
    title: "Declare",
    glyph: <DeclareGlyph />,
    body: "Before anything irreversible, the agent writes down three things: the question it is actually answering, what it doesn't know, and what would prove it wrong. Not a form to fill — the fields are the thinking.",
    accent: "text-chain",
  },
  {
    n: "02",
    title: "Gate",
    glyph: <GateGlyph />,
    body: "A hook checks that artifact before the command runs. It's deterministic: no valid surface, no execution. Nothing here depends on the model choosing to be careful — which is the point, because that's exactly what stops happening under time pressure.",
    accent: "text-disconfirm",
  },
  {
    n: "03",
    title: "Learn",
    glyph: <LearnGlyph />,
    body: "What the decision taught gets hash-chained into a protocol, so it resurfaces the next time a similar decision comes around. The record is dated and tamper-evident — six months from now, your reasoning is still there.",
    accent: "text-verified",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-b border-hairline">
      <div className="mx-auto max-w-7xl px-6 py-24 md:px-12 md:py-32">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.6 }}
          className="mb-16 flex max-w-2xl flex-col gap-5"
        >
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            02 / how it works
          </span>
          <h2 className="font-display text-[2.25rem] leading-[1.08] text-bone md:text-[3.25rem]">
            Three moves, and none of them are optional.
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 gap-px overflow-hidden border border-hairline bg-hairline md:grid-cols-3">
          {STEPS.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.6, delay: i * 0.12, ease: [0, 0, 0.2, 1] }}
              className="flex flex-col gap-6 bg-void p-8 md:p-10"
            >
              <div className="flex items-start justify-between">
                <span className={s.accent}>{s.glyph}</span>
                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-whisper">
                  {s.n}
                </span>
              </div>
              <h3 className="font-display text-[1.75rem] leading-tight text-bone">
                {s.title}
              </h3>
              <p className="font-sans text-[0.9375rem] leading-relaxed text-ash">
                {s.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

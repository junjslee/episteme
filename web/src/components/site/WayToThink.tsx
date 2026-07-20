"use client";

import { motion } from "motion/react";

/**
 * "A way to think" — the philosophy beat.
 *
 * Prose is drawn from docs/THE_WAY_TO_THINK.md §11 ("The one-line, and the
 * longer line"). Typeset as an editorial moment: large Fraunces serif, generous
 * measure, the accent colours used sparingly on the load-bearing clause.
 */
export function WayToThink() {
  return (
    <section id="way-to-think" className="relative overflow-hidden border-b border-hairline">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 55% 45% at 50% 30%, rgba(87,199,255,0.055), transparent 70%)",
        }}
      />
      <div className="relative mx-auto max-w-4xl px-6 py-28 md:px-12 md:py-40">
        <motion.span
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="mb-12 block font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted"
        >
          03 / a way to think
        </motion.span>

        <motion.p
          initial={{ opacity: 0, y: 22 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.8, ease: [0, 0, 0.2, 1] }}
          className="font-display text-[1.875rem] leading-[1.28] tracking-[-0.01em] text-bone md:text-[2.75rem] md:leading-[1.24]"
        >
          episteme is a way to think — <span className="text-chain">생각의 틀</span> —
          an epistemic engine that makes AI-assisted decisions earn their
          confidence: structure guarantees the thinking happens; factored
          verification checks it was real.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.8, delay: 0.15, ease: [0, 0, 0.2, 1] }}
          className="mt-14 flex flex-col gap-7 border-l border-hairline pl-7 md:pl-10"
        >
          <p className="font-sans text-[1.0625rem] leading-[1.75] text-ash md:text-[1.125rem]">
            Frontier models are now fluent enough that the diff{" "}
            <em className="font-display italic text-bone">looks fine</em> and the
            conclusions{" "}
            <em className="font-display italic text-bone">sound right</em> and the
            operator stops actually thinking at the moment of decision. For
            everyday work this is fine. For decisions that cannot be taken back,
            it is the failure mode the cognitive-governance literature has been
            warning about.
          </p>

          <p className="font-sans text-[1.0625rem] leading-[1.75] text-ash md:text-[1.125rem]">
            You will type more. You will move slower at the irreversible gate.
            Your judgment will stay present where it used to silently go absent.
            Six months from now when something asks you why you decided what you
            decided — an auditor, a teammate, your future self — your own
            reasoning will be there:{" "}
            <span className="text-bone">
              readable, verifiable, dated, unalterable.
            </span>
          </p>
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.8, delay: 0.25, ease: [0, 0, 0.2, 1] }}
          className="mt-16 font-display text-[1.5rem] leading-[1.35] text-bone md:text-[2rem]"
        >
          That is not compliance. That is what it means to keep thinking{" "}
          <span className="text-verified">
            while the model finishes your sentences.
          </span>
        </motion.p>

        <motion.a
          href="https://github.com/junjslee/episteme/blob/master/docs/THE_WAY_TO_THINK.md"
          target="_blank"
          rel="noopener"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="mt-10 inline-flex items-center gap-2 font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-muted transition-colors hover:text-chain"
        >
          read the full practice →
        </motion.a>
      </div>
    </section>
  );
}

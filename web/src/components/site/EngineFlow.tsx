"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";
import { RESULT_STYLES, SCENARIO, VERIFIED_CLAIMS } from "./EngineFlowScenario";
import {
  Caption,
  EngineFlowStatic,
  EvidenceStampLabel,
  StationLabel,
  TierTag,
} from "./EngineFlowStatic";

/**
 * EngineFlow — the animated interrogation mechanism.
 *
 * A scripted scenario (the README memory-eval story) loops through the
 * engine's stations. Every motion encodes a mechanism fact:
 *
 * - the seal draws BEFORE the verifier activates (fresh context first,
 *   then checks);
 * - the ghost draft card is shaken off AT the seal (the draft's prose never
 *   enters — the verifier receives only the claim);
 * - evidence stamps land per load-bearing claim (supported / refuted /
 *   unverifiable);
 * - the verdict gate starts CLOSED and only a valid verdict opens it
 *   (stop fails closed);
 * - a non-null lesson flows into the hash chain as a protocol.
 *
 * Renders the exact same skeleton as EngineFlowStatic (opacity/transform
 * choreography only — zero layout shift on swap-in). Under reduced motion it
 * renders EngineFlowStatic outright; the loader additionally never fetches
 * this chunk when reduced motion is set.
 */

const PHASES = [
  "decision",
  "decompose",
  "seal",
  "ghost",
  "verify",
  "oppose",
  "verdict",
  "lesson",
  "hold",
] as const;

type Phase = (typeof PHASES)[number];

const PHASE_MS: Record<Phase, number> = {
  decision: 1400,
  decompose: 2400,
  seal: 1700,
  ghost: 2300,
  verify: 3400,
  oppose: 2600,
  verdict: 2300,
  lesson: 2600,
  hold: 3200,
};

const EASE_ENTER: [number, number, number, number] = [0, 0, 0.2, 1];
const EASE_EXIT: [number, number, number, number] = [0.4, 0, 1, 1];

export function EngineFlow() {
  const reduceMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [inView, setInView] = useState(true);
  const [step, setStep] = useState(0);
  const [cycle, setCycle] = useState(0);

  // Pause the script while off-screen — no work the reader can't see.
  useEffect(() => {
    const el = rootRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => setInView(entries.some((e) => e.isIntersecting)),
      { threshold: 0.12 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Phase clock — advances one station at a time, then loops.
  useEffect(() => {
    if (!inView || reduceMotion) return;
    const timer = setTimeout(() => {
      if (step >= PHASES.length - 1) {
        setStep(0);
        setCycle((c) => c + 1);
      } else {
        setStep((s) => s + 1);
      }
    }, PHASE_MS[PHASES[step]]);
    return () => clearTimeout(timer);
  }, [step, inView, reduceMotion, cycle]);

  // Belt-and-braces: if the user flips reduced-motion on after this chunk
  // loaded, fall back to the static labeled map.
  if (reduceMotion) return <EngineFlowStatic />;

  const at = (phase: Phase) => step >= PHASES.indexOf(phase);

  return (
    <div
      ref={rootRef}
      className="relative border border-hairline bg-surface/40 p-5 md:p-8"
    >
      {/* key={cycle} remounts the choreography for a clean replay. */}
      <div
        key={cycle}
        className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-6"
      >
        {/* ── 01 decision + 02 decompose ─────────────────────────────── */}
        <div className="flex flex-col gap-5 lg:col-span-3">
          <div className="flex flex-col gap-2">
            <StationLabel index="01" label="decision" />
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={at("decision") ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.55, ease: EASE_ENTER }}
              className="border border-line bg-void/40 p-3"
            >
              <p className="font-mono text-[0.75rem] leading-relaxed text-bone">
                {SCENARIO.decision}
              </p>
            </motion.div>
          </div>

          <div className="flex flex-col gap-2">
            <StationLabel index="02" label="decompose · tiered claims" />
            <ul className="flex flex-col gap-1.5">
              {SCENARIO.claims.map((claim, i) => {
                const verifyIndex = VERIFIED_CLAIMS.findIndex(
                  (v) => v.id === claim.id,
                );
                return (
                  <motion.li
                    key={claim.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={at("decompose") ? { opacity: 1, x: 0 } : {}}
                    transition={{
                      duration: 0.45,
                      delay: i * 0.32,
                      ease: EASE_ENTER,
                    }}
                    className="relative flex flex-col gap-1.5 border border-hairline bg-void/40 p-2.5"
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[0.5625rem] text-muted">
                        {claim.id}
                      </span>
                      <TierTag tier={claim.tier} />
                      {claim.loadBearing && (
                        <span
                          className="font-mono text-[0.5625rem] uppercase tracking-[0.08em] text-ash"
                          title="load-bearing — verified in a fresh context"
                        >
                          ● load-bearing
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-[0.6875rem] leading-snug text-ash">
                      {claim.text}
                    </p>
                    {/* Evidence stamp lands during factored verification. */}
                    {claim.result && verifyIndex >= 0 && (
                      <motion.span
                        initial={{ opacity: 0, scale: 1.6, rotate: -6 }}
                        animate={
                          at("verify")
                            ? { opacity: 1, scale: 1, rotate: 0 }
                            : {}
                        }
                        transition={{
                          duration: 0.28,
                          delay: verifyIndex * 0.95 + 0.35,
                          ease: EASE_EXIT,
                        }}
                        className="absolute -right-1.5 -top-1.5"
                      >
                        <EvidenceStampLabel result={claim.result} />
                      </motion.span>
                    )}
                  </motion.li>
                );
              })}
            </ul>
          </div>
        </div>

        {/* ── 03 sealed fresh-context verifier ───────────────────────── */}
        <div className="flex flex-col gap-2 lg:col-span-4">
          <StationLabel index="03" label="verify · fresh context" />
          <div className="relative mt-2 flex-1 border border-transparent p-1.5">
            {/* The seal draws itself closed BEFORE any checking begins. */}
            <svg
              aria-hidden
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <motion.rect
                x="1"
                y="1"
                width="98"
                height="98"
                rx="1.5"
                fill="none"
                stroke="var(--color-line-strong)"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
                initial={{ pathLength: 0 }}
                animate={at("seal") ? { pathLength: 1 } : {}}
                transition={{ duration: 1.35, ease: "easeInOut" }}
              />
            </svg>
            <motion.span
              initial={{ opacity: 0 }}
              animate={at("seal") ? { opacity: 1 } : {}}
              transition={{ duration: 0.3, delay: 1.3, ease: EASE_ENTER }}
              className="absolute -top-2 left-3 bg-surface px-1.5 font-mono text-[0.5625rem] uppercase tracking-[0.12em] text-ash"
            >
              sealed
            </motion.span>

            <div className="relative flex h-full flex-col gap-2 p-3">
              {/* Ghost draft approaches the seal, is shaken off, settles
                  outside it. The prose never enters. */}
              <div className="flex items-center gap-2">
                <motion.span
                  initial={{ opacity: 0, x: -56 }}
                  animate={
                    at("ghost")
                      ? {
                          opacity: [0, 1, 1, 1, 1, 1, 1, 0.6],
                          x: [-56, -4, -7, -1, -7, -1, -4, -30],
                        }
                      : {}
                  }
                  transition={{
                    duration: 1.9,
                    times: [0, 0.32, 0.46, 0.52, 0.58, 0.64, 0.7, 1],
                    ease: "easeInOut",
                  }}
                  className="inline-flex max-w-full items-center gap-1.5 border border-dashed border-line/60 px-2 py-1 font-mono text-[0.625rem] text-muted"
                >
                  draft reasoning
                  <motion.span
                    aria-hidden
                    initial={{ opacity: 0 }}
                    animate={at("ghost") ? { opacity: 1 } : {}}
                    transition={{ duration: 0.2, delay: 1.0, ease: EASE_EXIT }}
                    className="text-disconfirm"
                  >
                    ✕
                  </motion.span>
                </motion.span>
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={at("ghost") ? { opacity: 1 } : {}}
                  transition={{ duration: 0.3, delay: 1.9, ease: EASE_ENTER }}
                  className="font-mono text-[0.5625rem] uppercase tracking-[0.08em] text-muted"
                >
                  sealed out
                </motion.span>
              </div>

              {/* Factored verification — only after the seal is complete. */}
              <ul className="flex flex-col gap-1.5 border-t border-hairline pt-2">
                {VERIFIED_CLAIMS.map((claim, i) => (
                  <li
                    key={claim.id}
                    className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[0.6875rem] leading-snug"
                  >
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={at("verify") ? { opacity: 1 } : {}}
                      transition={{
                        duration: 0.3,
                        delay: i * 0.95,
                        ease: EASE_ENTER,
                      }}
                      className="text-muted"
                    >
                      {claim.id}
                    </motion.span>
                    <motion.span
                      aria-hidden
                      initial={{ opacity: 0 }}
                      animate={at("verify") ? { opacity: 1 } : {}}
                      transition={{
                        duration: 0.3,
                        delay: i * 0.95 + 0.15,
                        ease: EASE_ENTER,
                      }}
                      className="text-whisper"
                    >
                      →
                    </motion.span>
                    <motion.span
                      initial={{ opacity: 0, scale: 1.6, rotate: -6 }}
                      animate={
                        at("verify") ? { opacity: 1, scale: 1, rotate: 0 } : {}
                      }
                      transition={{
                        duration: 0.28,
                        delay: i * 0.95 + 0.35,
                        ease: EASE_EXIT,
                      }}
                      className={cn(
                        "inline-flex border px-1.5 py-px font-mono text-[0.5625rem] uppercase tracking-[0.08em]",
                        RESULT_STYLES[claim.result],
                      )}
                    >
                      {claim.result}
                    </motion.span>
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={at("verify") ? { opacity: 1 } : {}}
                      transition={{
                        duration: 0.35,
                        delay: i * 0.95 + 0.55,
                        ease: EASE_ENTER,
                      }}
                      className="text-ash"
                    >
                      {claim.evidence}
                    </motion.span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <Caption>
            the verifier receives the claim only — never the draft&apos;s
            prose. it answers from evidence, not from the argument.
          </Caption>
        </div>

        {/* ── 04 oppose + 05 verdict gate ─────────────────────────────── */}
        <div className="flex flex-col gap-5 lg:col-span-3">
          <div className="flex flex-col gap-2">
            <StationLabel index="04" label="oppose" />
            <div className="flex flex-col gap-2 border border-hairline bg-void/40 p-3 font-mono text-[0.6875rem] leading-snug">
              {(
                [
                  <p key="o" className="text-disconfirm">
                    {SCENARIO.opposition}
                  </p>,
                  <p key="w" className="text-ash">
                    <span className="uppercase tracking-[0.08em] text-muted">
                      weakest link
                    </span>{" "}
                    {SCENARIO.weakestLink}
                  </p>,
                  <p key="d" className="text-ash">
                    <span className="uppercase tracking-[0.08em] text-muted">
                      disconfirmation
                    </span>{" "}
                    {SCENARIO.disconfirmation}
                  </p>,
                ] as const
              ).map((node, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={at("oppose") ? { opacity: 1, y: 0 } : {}}
                  transition={{
                    duration: 0.45,
                    delay: i * 0.55,
                    ease: EASE_ENTER,
                  }}
                >
                  {node}
                </motion.div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <StationLabel index="05" label="verdict gate" />
            <div className="flex flex-col gap-2">
              {/* Verdict word stamps first… */}
              <motion.span
                initial={{ opacity: 0, scale: 1.6, rotate: -9 }}
                animate={at("verdict") ? { opacity: 1, scale: 1, rotate: -3 } : {}}
                transition={{ duration: 0.28, ease: EASE_EXIT }}
                className="inline-flex w-fit border border-chain/50 bg-chain/[0.05] px-2 py-[3px] font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-chain"
              >
                verdict · {SCENARIO.verdict}
              </motion.span>
              {/* …then the gate opens. It begins CLOSED: stop fails closed. */}
              <div className="relative h-7 overflow-hidden border border-line bg-void/40">
                <motion.span
                  initial={{ opacity: 0 }}
                  animate={at("verdict") ? { opacity: 1 } : {}}
                  transition={{ duration: 0.3, delay: 1.0, ease: EASE_ENTER }}
                  className="absolute inset-0 flex items-center justify-center font-mono text-[0.5625rem] uppercase tracking-[0.18em] text-verified"
                >
                  open
                </motion.span>
                <motion.span
                  initial={{ x: "0%" }}
                  animate={at("verdict") ? { x: "-82%" } : {}}
                  transition={{ duration: 0.6, delay: 0.55, ease: EASE_ENTER }}
                  className="absolute inset-y-0 left-0 w-1/2 border-r border-line bg-elevated"
                />
                <motion.span
                  initial={{ x: "0%" }}
                  animate={at("verdict") ? { x: "82%" } : {}}
                  transition={{ duration: 0.6, delay: 0.55, ease: EASE_ENTER }}
                  className="absolute inset-y-0 right-0 w-1/2 border-l border-line bg-elevated"
                />
              </div>
            </div>
            <Caption>
              the gate starts closed and only a valid verdict opens it — a{" "}
              <span className="text-disconfirm">stop</span> verdict fails
              closed.
            </Caption>
          </div>
        </div>

        {/* ── 06 lesson → chain ───────────────────────────────────────── */}
        <div className="flex flex-col gap-2 lg:col-span-2">
          <StationLabel index="06" label="lesson → chain" />
          <div className="flex flex-col gap-2">
            <motion.p
              initial={{ opacity: 0, x: -24 }}
              animate={at("lesson") ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.5, ease: EASE_ENTER }}
              className="border border-hairline bg-void/40 p-2.5 font-mono text-[0.6875rem] leading-snug text-bone"
            >
              {SCENARIO.lesson}
            </motion.p>
            <div className="flex flex-col items-start gap-0 pl-2">
              <span className="border border-hairline px-2 py-1 font-mono text-[0.625rem] text-muted">
                genesis
              </span>
              <motion.span
                aria-hidden
                initial={{ scaleY: 0 }}
                animate={at("lesson") ? { scaleY: 1 } : {}}
                transition={{ duration: 0.3, delay: 0.5, ease: EASE_ENTER }}
                className="ml-3 h-3 w-px origin-top bg-line"
              />
              {/* New link lands with the chain-blue flash. */}
              <motion.span
                initial={{ opacity: 0 }}
                animate={
                  at("lesson")
                    ? {
                        opacity: 1,
                        backgroundColor: [
                          "rgba(45, 91, 163, 0.18)",
                          "rgba(45, 91, 163, 0.05)",
                        ],
                      }
                    : {}
                }
                transition={{ duration: 0.6, delay: 0.8, ease: EASE_EXIT }}
                className="border border-chain/50 bg-chain/[0.05] px-2 py-1 font-mono text-[0.625rem] text-chain"
                title={SCENARIO.protocolId}
              >
                {SCENARIO.protocolId.slice(0, 11)}…
              </motion.span>
            </div>
          </div>
          <Caption>
            verified lessons become context-scoped protocols — hash-chained,
            resurfacing at the next matching decision.
          </Caption>
        </div>
      </div>

      {/* Shared footer legend — identical in both renderers. */}
      <p className="mt-6 border-t border-hairline pt-3 font-mono text-[0.625rem] leading-relaxed text-muted">
        ● load-bearing claims are verified in a fresh context ·{" "}
        <span className="text-verified">supported</span> /{" "}
        <span className="text-disconfirm">refuted</span> /{" "}
        <span className="text-unknown">unverifiable</span> · most
        interrogations teach nothing durable — the lesson is nullable.
      </p>
    </div>
  );
}

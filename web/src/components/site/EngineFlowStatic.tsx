import { cn } from "@/lib/utils";
import {
  RESULT_STYLES,
  SCENARIO,
  TIER_STYLES,
  VERIFIED_CLAIMS,
  type ClaimTier,
  type EvidenceResult,
} from "./EngineFlowScenario";

/**
 * EngineFlowStatic — the engine map at rest.
 *
 * Server component, zero client JS. This is the SSR content the loader
 * prerenders, the permanent view for prefers-reduced-motion readers, and the
 * no-JS fallback. It renders the SAME skeleton as the animated EngineFlow —
 * same stations, same scenario text, final states baked in — so swapping the
 * animated stage in causes zero layout shift.
 *
 * Stations: 01 decision → 02 decompose (tiered claims) → 03 sealed
 * fresh-context verifier (ghost draft sealed out, evidence stamps) →
 * 04 oppose → 05 verdict gate (stop fails closed) → 06 lesson → chain.
 */

export function StationLabel({
  index,
  label,
  className,
}: {
  index: string;
  label: string;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-mono text-[0.625rem] uppercase tracking-[0.18em] text-ash",
        className,
      )}
    >
      <span className="text-muted">{index}</span> · {label}
    </p>
  );
}

export function TierTag({ tier }: { tier: ClaimTier }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 border px-1.5 py-px font-mono text-[0.6875rem] uppercase tracking-[0.08em]",
        TIER_STYLES[tier],
      )}
    >
      {tier}
    </span>
  );
}

export function EvidenceStampLabel({ result }: { result: EvidenceResult }) {
  return (
    <span
      className={cn(
        "inline-flex -rotate-3 border px-1.5 py-px font-mono text-[0.6875rem] uppercase tracking-[0.08em]",
        RESULT_STYLES[result],
      )}
    >
      {result}
    </span>
  );
}

export function Caption({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "font-mono text-[0.625rem] leading-relaxed text-ash",
        className,
      )}
    >
      {children}
    </p>
  );
}

export function EngineFlowStatic() {
  return (
    <div className="relative border border-hairline bg-surface/40 p-5 md:p-8">
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-6">
        {/* ── 01 decision + 02 decompose ─────────────────────────────── */}
        <div className="flex flex-col gap-5 lg:col-span-3">
          <div className="flex flex-col gap-2">
            <StationLabel index="01" label="decision" />
            <div className="border border-line bg-void/40 p-3">
              <p className="font-mono text-[0.75rem] leading-relaxed text-bone">
                {SCENARIO.decision}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <StationLabel index="02" label="decompose · tiered claims" />
            <ul className="flex flex-col gap-1.5">
              {SCENARIO.claims.map((claim) => (
                <li
                  key={claim.id}
                  className="relative flex flex-col gap-1.5 border border-hairline bg-void/40 p-2.5"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-[0.6875rem] text-muted">
                      {claim.id}
                    </span>
                    <TierTag tier={claim.tier} />
                    {claim.loadBearing && (
                      <span
                        className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-ash"
                        title="load-bearing — verified in a fresh context"
                      >
                        ● load-bearing
                      </span>
                    )}
                  </div>
                  <p className="font-mono text-[0.6875rem] leading-snug text-ash">
                    {claim.text}
                  </p>
                  {claim.result && (
                    <span className="absolute -right-1.5 -top-1.5">
                      <EvidenceStampLabel result={claim.result} />
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── 03 sealed fresh-context verifier ───────────────────────── */}
        <div className="flex flex-col gap-2 lg:col-span-4">
          <StationLabel index="03" label="verify · fresh context" />
          <div className="relative mt-2 flex-1 border border-transparent p-1.5">
            {/* The seal — drawn closed before any checking begins. */}
            <svg
              aria-hidden
              className="pointer-events-none absolute inset-0 h-full w-full"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <rect
                x="1"
                y="1"
                width="98"
                height="98"
                rx="1.5"
                fill="none"
                stroke="var(--color-line-strong)"
                strokeWidth="1.5"
                vectorEffect="non-scaling-stroke"
              />
            </svg>
            <span className="absolute -top-2 left-3 bg-surface px-1.5 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash">
              sealed
            </span>

            <div className="relative flex h-full flex-col gap-2 p-3">
              {/* Ghost draft — rejected at the seal. */}
              <div className="flex items-center gap-2">
                <span className="inline-flex max-w-full items-center gap-1.5 border border-dashed border-line/60 px-2 py-1 font-mono text-[0.625rem] text-muted opacity-60">
                  draft reasoning
                  <span aria-hidden className="text-disconfirm">
                    ✕
                  </span>
                </span>
                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-ash">
                  sealed out
                </span>
              </div>

              {/* Factored verification — claim in, evidence verdict out. */}
              <ul className="flex flex-col gap-1.5 border-t border-hairline pt-2">
                {VERIFIED_CLAIMS.map((claim) => (
                  <li
                    key={claim.id}
                    className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[0.6875rem] leading-snug"
                  >
                    <span className="text-ash">{claim.id}</span>
                    <span aria-hidden className="text-whisper">
                      →
                    </span>
                    <EvidenceStampLabel result={claim.result} />
                    <span className="text-ash">{claim.evidence}</span>
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
              <p className="text-disconfirm">{SCENARIO.opposition}</p>
              <p className="text-ash">
                <span className="uppercase tracking-[0.08em] text-ash">
                  weakest link
                </span>{" "}
                {SCENARIO.weakestLink}
              </p>
              <p className="text-ash">
                <span className="uppercase tracking-[0.08em] text-ash">
                  disconfirmation
                </span>{" "}
                {SCENARIO.disconfirmation}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <StationLabel index="05" label="verdict gate" />
            <div className="flex flex-col gap-2">
              <span className="inline-flex w-fit -rotate-3 border border-chain/50 bg-chain/[0.05] px-2 py-[3px] font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-chain">
                verdict · {SCENARIO.verdict}
              </span>
              {/* Gate at rest is CLOSED; a valid verdict opened it. */}
              <div className="relative h-7 overflow-hidden border border-line bg-void/40">
                <span className="absolute inset-0 flex items-center justify-center font-mono text-[0.6875rem] uppercase tracking-[0.18em] text-verified">
                  open
                </span>
                <span className="absolute inset-y-0 left-0 w-1/2 -translate-x-[82%] border-r border-line bg-elevated" />
                <span className="absolute inset-y-0 right-0 w-1/2 translate-x-[82%] border-l border-line bg-elevated" />
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
            <p className="border border-hairline bg-void/40 p-2.5 font-mono text-[0.6875rem] leading-snug text-bone">
              {SCENARIO.lesson}
            </p>
            <div className="flex flex-col items-start gap-0 pl-2">
              <span className="border border-hairline px-2 py-1 font-mono text-[0.625rem] text-muted">
                genesis
              </span>
              <span aria-hidden className="ml-3 h-3 w-px bg-line" />
              <span
                className="border border-chain/50 bg-chain/[0.05] px-2 py-1 font-mono text-[0.625rem] text-chain"
                title={SCENARIO.protocolId}
              >
                {SCENARIO.protocolId.slice(0, 11)}…
              </span>
            </div>
          </div>
          <Caption>
            verified lessons become context-scoped protocols — hash-chained,
            resurfacing at the next matching decision.
          </Caption>
        </div>
      </div>

      {/* Shared footer legend — identical in both renderers. */}
      <p className="mt-6 border-t border-hairline pt-3 font-mono text-[0.625rem] leading-relaxed text-ash">
        ● load-bearing claims are verified in a fresh context ·{" "}
        <span className="text-verified">supported</span> /{" "}
        <span className="text-disconfirm">refuted</span> /{" "}
        <span className="text-unknown">unverifiable</span> · most
        interrogations teach nothing durable — the lesson is nullable.
      </p>
    </div>
  );
}

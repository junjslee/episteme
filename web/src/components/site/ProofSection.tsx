import Link from "next/link";
import { Sectioned } from "@/components/ui/Sectioned";
import { CornerMarkers } from "@/components/ui/CornerMarkers";
import { ProtocolNode } from "@/components/viz/ProtocolNode";
import type { Protocol } from "@/lib/types/episteme";

/**
 * ProofSection — the one proof element, three facets:
 *
 *   1. The true 49-days / zero-protocols falsifiability story — the kernel's
 *      own condition (E1) fired, the kernel reported the miss on itself, and
 *      the loop was rebuilt so verified interrogation lessons synthesize
 *      protocols.
 *   2. The MIRROR confident-failure-rate result (0.60 → 0.14) as CSS-only
 *      bars: `.bar-shift` (globals.css) drives the constrained bar via
 *      animation-timeline: view() — zero JS; non-supporting browsers and
 *      reduced-motion get the inline final state.
 *   3. The live hash chain (LiveHashChainStream) with protocol №1 rendered
 *      via ProtocolNode — the chain's actual first record, not a fixture.
 *
 * Server component. The two embedded client islands (chain stream, protocol
 * node) were already client components and ship no new JS.
 */

/**
 * Protocol №1 — the chain's REAL first record, transcribed from
 * $EPISTEME_HOME/framework/protocols.jsonl (sealed 2026-06-10T03:34:46Z,
 * prev_hash sha256:GENESIS). Synthesized from a verified interrogation the
 * night falsifiability condition E1 fired. Nothing here is invented.
 */
const FIRST_PROTOCOL: Protocol = {
  id: "lh_71f88adef21147df",
  name: "release-merge under overnight autonomy",
  summary:
    "In context `episteme release flow under operator-granted overnight autonomy`, treat release-please merges as in-scope when the directive asks for a finished product by morning — and name the judgment call explicitly in the handoff.",
  because: {
    observed_signal:
      "The directive asked for a finished product by morning; the release-please PR was the last step standing",
    inferred_cause:
      "rc tags are the repo's soak channel — the content ships on master either way; six prior rc cycles followed the identical autonomous shape",
    decision:
      "Merge release-please PR #94 · cut episteme v1.7.0-rc1 · name the judgment call in the handoff",
  },
  triggers: ["project · episteme", "op class · gh pr", "runtime · governed"],
  invocations: 0,
  confidence: 1,
  synthesized_at: "2026-06-10T03:34:46Z",
  last_chain_hash:
    "7679d5533fd8ebf0bd613a2d2b35e806fecf87affd816036b017f336423915ae",
};

export function ProofSection() {
  return (
    <Sectioned
      id="proof"
      index="03"
      label="proof"
      kicker="falsifiable, by record"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          Forty-nine days. Zero protocols.
          <br />
          <span className="text-ash">The kernel reported the miss itself.</span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          A falsifiability condition only counts if it can fire. For 49 days
          the framework ran live and synthesized zero protocols — the one emit
          path was tied to the rarest operation class. Condition{" "}
          <Link
            href="https://github.com/junjslee/episteme/blob/master/kernel/FALSIFIABILITY_CONDITIONS.md"
            target="_blank"
            rel="noopener"
            className="text-bone underline decoration-hairline underline-offset-4 hover:decoration-line"
          >
            E1
          </Link>{" "}
          fired. First the kernel was made to measure the miss in its own
          reports; then the loop got a real source — every verified
          interrogation whose lesson survives becomes a context-scoped
          protocol. The first one landed the same night.{" "}
          <span className="text-bone">
            It&apos;s transcribed below, exactly as sealed.
          </span>
        </p>
      </div>

      <div className="relative">
        <CornerMarkers />
        <div className="grid grid-cols-1 gap-5 p-3 md:grid-cols-12">
          {/* Facet 2 — the external record: MIRROR CFR bars, CSS-only */}
          <div className="flex flex-col gap-8 panel-gradient p-6 md:col-span-5 md:p-8">
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
              external record · confident-failure rate
            </span>

            <div className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash">
                  self-monitoring — calibration scores shown to the model
                </span>
                <span className="font-display text-[1.625rem] leading-none text-disconfirm">
                  0.60
                </span>
              </div>
              <div className="relative h-2 w-full overflow-hidden bg-elevated/70">
                <div
                  className="absolute inset-y-0 left-0 bg-disconfirm/70"
                  style={{ width: "60%" }}
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash">
                  architectural constraint — external to the model
                </span>
                <span className="font-display text-[1.625rem] leading-none text-verified">
                  0.14
                </span>
              </div>
              <div className="relative h-2 w-full overflow-hidden bg-elevated/70">
                <div
                  className="bar-shift absolute inset-y-0 left-0 bg-verified/70"
                  style={{ width: "14%" }}
                />
              </div>
            </div>

            <blockquote className="border-l-2 border-hairline pl-4 font-sans text-[0.875rem] leading-relaxed text-ash">
              &ldquo;Providing models with their own calibration scores
              produces no significant improvement; only architectural
              constraint is effective.&rdquo;
            </blockquote>

            <Link
              href="https://arxiv.org/abs/2604.19809"
              target="_blank"
              rel="noopener"
              className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted transition-colors hover:text-chain"
            >
              MIRROR · 16 models · 8 labs · ~250,000 instances — arXiv
              2604.19809 →
            </Link>
          </div>

          {/* Facets 1+3 — the record: protocol №1, transcribed from the
              chain. The animated chain stream stays on /dashboard, where
              it reads the real store — pairing it here with fixture data
              labeled "live" was the exact dishonesty this page argues
              against (Event 139 review must-fix #3). */}
          <div className="flex flex-col gap-4 md:col-span-7">
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-ash">
              the record · protocol №1, transcribed from the chain
            </span>
            <ProtocolNode protocol={FIRST_PROTOCOL} />
            <p className="font-mono text-[0.6875rem] leading-relaxed text-ash">
              №1 — synthesized 2026-06-10 from a verified interrogation ·
              verdict: proceed · sealed against sha256:GENESIS · the live
              chain renders in the dashboard
            </p>
          </div>
        </div>
      </div>

      <div className="mt-10 flex justify-end">
        <Link
          href="https://github.com/junjslee/episteme#protocol-synthesis--active-guidance--the-ultimate-vision"
          target="_blank"
          rel="noopener"
          className="group inline-flex items-center gap-2 font-mono text-[0.75rem] uppercase tracking-[0.12em] text-ash transition-colors hover:text-chain"
        >
          the full 49-day case study
          <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
            →
          </span>
        </Link>
      </div>
    </Sectioned>
  );
}

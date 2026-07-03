import Link from "next/link";
import { SignalBadge } from "@/components/ui/SignalBadge";
import { CornerMarkers } from "@/components/ui/CornerMarkers";
import { InterrogationStrip } from "@/components/site/InterrogationStrip";
import { RELEASE_FACTS } from "@/lib/release-facts";

const HERO_WORDS = ["Sounding", "right", "isn't", "being", "right."];

/**
 * Hero — server component, CSS-only motion.
 *
 * Rise stagger is class-owned (`.rise-1` … `.rise-4` in globals.css,
 * delays 700/900/1100/1300ms) rather than inline `animation` styles, so
 * the global prefers-reduced-motion block can force the final visible
 * state. Inline styles on the H1 words carry only `animationDelay`; the
 * animation itself lives on `.mask-word-inner`.
 */
export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-hairline">
      <div className="relative mx-auto max-w-7xl px-6 pt-20 pb-16 md:px-12 md:pt-32 md:pb-24">
        <div className="relative panel-gradient">
          <CornerMarkers />

          {/* Inner atmosphere for the hero panel only */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 overflow-hidden"
          >
            <div className="absolute left-1/2 top-1/2 h-[70%] w-[60%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-chain/[0.06] blur-[110px]" />
            <div className="absolute right-[-15%] bottom-[-20%] h-[55%] w-[50%] rounded-full bg-disconfirm/[0.04] blur-[100px]" />
          </div>

          <div className="relative flex flex-col gap-10 p-8 md:gap-12 md:p-14 lg:p-20">
            <div className="flex flex-wrap items-center gap-3">
              <SignalBadge signal="chain">
                <span className="relative inline-flex size-1.5">
                  <span className="absolute inline-flex h-full w-full rounded-full bg-chain opacity-75 status-pulse" />
                  <span className="relative inline-flex size-1.5 rounded-full bg-chain" />
                </span>
                epistemic engine · {RELEASE_FACTS.version}
              </SignalBadge>
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted">
                생각의 틀 · decompose · verify · oppose · decide
              </span>
            </div>

            <h1 className="max-w-5xl font-display text-[2.75rem] leading-[1.05] tracking-tight text-bone md:text-[4.5rem]">
              {HERO_WORDS.map((word, i) => (
                <span key={`${word}-${i}`} className="mask-word mr-[0.22em]">
                  <span
                    className="mask-word-inner"
                    style={{ animationDelay: `${i * 70}ms` }}
                  >
                    {word}
                  </span>
                </span>
              ))}
            </h1>

            <p className="rise-1 max-w-2xl font-sans text-[1.0625rem] leading-relaxed text-ash md:text-[1.1875rem]">
              Frontier models are fluent enough now that wrong answers arrive
              sounding finished. episteme makes a load-bearing conclusion earn
              its confidence before it lands —{" "}
              <span className="text-bone">
                decomposed into claims, verified against evidence, argued from
                the other side, stamped with a verdict.
              </span>
            </p>

            <div className="rise-2 flex flex-wrap items-center gap-4">
              <Link
                href="#how-it-works"
                className="group inline-flex items-center gap-2 border border-line bg-surface px-5 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-bone transition-colors hover:border-chain hover:text-chain"
              >
                see how it works
                <span
                  aria-hidden
                  className="transition-transform group-hover:translate-x-0.5"
                >
                  →
                </span>
              </Link>
              <Link
                href="#install"
                className="inline-flex items-center gap-2 border border-hairline px-5 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-ash transition-colors hover:border-line hover:text-bone"
              >
                install in 60 seconds
              </Link>
            </div>

            <div className="rise-3 mt-2">
              <InterrogationStrip />
            </div>

            <div className="rise-4 mt-4 grid grid-cols-2 gap-6 border-t border-hairline/70 pt-8 md:grid-cols-4">
              {[
                { k: "claim tiers", v: "04" },
                { k: "verdicts", v: "03" },
                { k: "tests green", v: String(RELEASE_FACTS.testsGreen) },
                { k: "CFR under constraint · MIRROR", v: "0.60→0.14" },
              ].map((m) => (
                <div key={m.k} className="flex flex-col gap-1">
                  <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-ash">
                    {m.k}
                  </span>
                  <span className="font-display text-[1.75rem] leading-none text-bone">
                    {m.v}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

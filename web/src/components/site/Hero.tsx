import Link from "next/link";
import { HeroCanvasMount } from "./hero/HeroCanvasMount";
import { RELEASE_FACTS } from "@/lib/release-facts";

const HEADLINE = ["Make", "the", "AI", "show", "its", "work."];

/**
 * Hero — the full-viewport "Gate & the Lattice" moment.
 *
 * The copy is server-rendered so the headline is in the HTML for crawlers and
 * paints without waiting on WebGL; the scene mounts behind it from a lazy
 * client chunk. The scrim between them is what keeps the type legible over a
 * moving field of light.
 */
export function Hero() {
  return (
    <section className="relative isolate flex min-h-[100svh] items-center overflow-hidden border-b border-hairline">
      <HeroCanvasMount />

      {/* Legibility scrim — dark on the left where the copy lives, clearing
          toward the right so the lattice stays visible. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[linear-gradient(100deg,var(--color-void)_8%,color-mix(in_oklab,var(--color-void)_75%,transparent)_42%,transparent_72%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40 bg-[linear-gradient(to_top,var(--color-void),transparent)]"
      />

      <div className="relative z-10 mx-auto w-full max-w-7xl px-6 py-28 md:px-12">
        <div className="flex max-w-3xl flex-col gap-8">
          <div className="rise-1 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 border border-chain/40 bg-chain/[0.06] px-2.5 py-1 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-chain">
              <span className="relative inline-flex size-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-chain opacity-70 status-pulse" />
                <span className="relative inline-flex size-1.5 rounded-full bg-chain" />
              </span>
              cognitive kernel · {RELEASE_FACTS.version}
            </span>
            <span className="font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-muted">
              declare · gate · learn
            </span>
          </div>

          <h1 className="font-display text-[3rem] leading-[1.02] tracking-tight text-bone sm:text-[4rem] md:text-[5.25rem]">
            {HEADLINE.map((word, i) => (
              <span key={`${word}-${i}`} className="mask-word mr-[0.2em]">
                <span
                  className="mask-word-inner"
                  style={{ animationDelay: `${i * 65}ms` }}
                >
                  {word}
                </span>
              </span>
            ))}
          </h1>

          <p className="rise-2 max-w-xl font-sans text-[1.0625rem] leading-relaxed text-ash md:text-[1.1875rem]">
            episteme is <span className="text-bone">생각의 틀</span> — a way to
            think, enforced at the moment before irreversible action.
          </p>

          <div className="rise-3 flex flex-wrap items-center gap-4">
            <Link
              href="#install"
              className="group inline-flex items-center gap-2 border border-chain/60 bg-chain/10 px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-bone transition-colors hover:bg-chain/20"
            >
              install
              <span
                aria-hidden
                className="transition-transform group-hover:translate-x-0.5"
              >
                →
              </span>
            </Link>
            <Link
              href="https://github.com/junjslee/episteme"
              target="_blank"
              rel="noopener"
              className="inline-flex items-center gap-2 border border-line px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-ash transition-colors hover:border-line-strong hover:text-bone"
            >
              github
            </Link>
          </div>
        </div>
      </div>

      <span
        aria-hidden
        className="absolute inset-x-0 bottom-6 z-10 mx-auto hidden w-fit font-mono text-[0.625rem] uppercase tracking-[0.24em] text-whisper md:block"
      >
        scroll
      </span>
    </section>
  );
}

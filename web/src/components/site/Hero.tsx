import Link from "next/link";
import { SignalBadge } from "@/components/ui/SignalBadge";

export function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-hairline">
      <div className="mx-auto flex max-w-7xl flex-col gap-12 px-6 pt-24 pb-20 md:px-12 md:pt-36 md:pb-28">
        <div className="flex items-center gap-3">
          <SignalBadge signal="chain">substrate · v1.0 rc</SignalBadge>
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted">
            causal-consequence scaffolding & protocol synthesis
          </span>
        </div>

        <h1 className="max-w-5xl font-display text-[2.75rem] leading-[1.05] tracking-tight text-bone md:text-[4.5rem]">
          A thinking framework for the agents you already ship.
        </h1>

        <p className="max-w-2xl font-sans text-[1.0625rem] leading-relaxed text-ash md:text-[1.1875rem]">
          <span className="text-bone">episteme</span> is a sovereign cognitive kernel that
          extracts context-fit protocols from conflicting information, records every
          decision on a tamper-evident hash chain, and actively guides execution when
          the reasoning surface goes thin.
        </p>

        <div className="flex flex-wrap items-center gap-4">
          <Link
            href="#framework"
            className="group inline-flex items-center gap-2 border border-line bg-surface px-5 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-bone transition-colors hover:border-chain hover:text-chain"
          >
            see the framework
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
            className="inline-flex items-center gap-2 border border-hairline px-5 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-ash transition-colors hover:border-line hover:text-bone"
          >
            read the kernel
          </Link>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-6 border-t border-hairline pt-8 md:grid-cols-4">
          {[
            { k: "pillars", v: "03" },
            { k: "blueprints", v: "04" },
            { k: "tests green", v: "565 / 565" },
            { k: "protocols synthesized", v: "live" },
          ].map((m) => (
            <div key={m.k} className="flex flex-col gap-1">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
                {m.k}
              </span>
              <span className="font-display text-[1.75rem] leading-none text-bone">
                {m.v}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

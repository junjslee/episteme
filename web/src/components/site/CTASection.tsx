import Link from "next/link";

export function CTASection() {
  return (
    <section className="border-t border-hairline">
      <div className="mx-auto max-w-7xl px-6 py-20 md:px-12 md:py-28">
        <div className="flex flex-col items-start gap-8 border border-hairline bg-surface/30 p-10 md:p-16">
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            06 / install
          </span>
          <h2 className="max-w-3xl font-display text-[2.25rem] leading-[1.05] text-bone md:text-[3.25rem]">
            Install the substrate.
            <br />
            <span className="text-ash">
              Then keep shipping — with a chain behind every decision.
            </span>
          </h2>
          <div className="w-full max-w-2xl border border-hairline bg-void p-5 font-mono text-[0.8125rem] text-ash">
            <span className="text-muted">$</span>{" "}
            <span className="text-bone">pipx install episteme</span>
            <br />
            <span className="text-muted">$</span>{" "}
            <span className="text-bone">episteme init</span>
            <span className="text-muted"> # creates .episteme/ + chain genesis</span>
            <br />
            <span className="text-muted">$</span>{" "}
            <span className="text-bone">episteme guide</span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <Link
              href="https://github.com/junjslee/episteme"
              className="group inline-flex items-center gap-2 border border-line bg-bone px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-void transition-colors hover:bg-chain"
            >
              read the kernel
              <span className="transition-transform group-hover:translate-x-0.5">
                →
              </span>
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 border border-line px-6 py-3 font-mono text-[0.8125rem] uppercase tracking-[0.12em] text-bone transition-colors hover:border-chain hover:text-chain"
            >
              see the dashboard
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

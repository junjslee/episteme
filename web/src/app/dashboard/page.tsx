import { Header } from "@/components/site/Header";
import { Footer } from "@/components/site/Footer";
import { ReasoningMatrix } from "@/components/viz/ReasoningMatrix";
import { HashChainStream } from "@/components/viz/HashChainStream";
import { TelemetryTicker } from "@/components/viz/TelemetryTicker";
import { CascadeDetector } from "@/components/viz/CascadeDetector";
import { ProtocolNode } from "@/components/viz/ProtocolNode";
import { SignalBadge } from "@/components/ui/SignalBadge";
import { fixtureSurface } from "@/lib/fixtures/reasoning-surface";
import {
  fixtureChain,
  fixtureProtocols,
  fixtureTelemetry,
} from "@/lib/fixtures/chain";
import { fixtureCascadeSignals } from "@/lib/fixtures/cascade";
import { markChainIntegrity } from "@/lib/parsers/chain";

export default function DashboardPage() {
  const chain = markChainIntegrity(fixtureChain);

  return (
    <>
      <Header />
      <main className="min-h-screen">
        <section className="border-b border-hairline">
          <div className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-12 md:px-12 md:py-16">
            <div className="flex items-center gap-3">
              <SignalBadge signal="chain">live kernel</SignalBadge>
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-muted">
                .episteme / dashboard
              </span>
            </div>
            <h1 className="font-display text-[2rem] leading-[1.05] text-bone md:text-[3rem]">
              Kernel telemetry · operator console
            </h1>
            <p className="max-w-2xl font-mono text-[0.8125rem] leading-relaxed text-ash">
              Reasoning surface, hash chain, active protocols, and Blueprint D
              cascade detector — sourced from the same JSONL the CLI reads. v1
              ships with static fixtures; v2 wires{" "}
              <code className="text-bone">/api/chain</code> to the local kernel.
            </p>
          </div>
        </section>

        <section className="border-b border-hairline">
          <div className="mx-auto max-w-7xl px-6 py-10 md:px-12 md:py-14">
            <CascadeDetector signals={fixtureCascadeSignals} />
          </div>
        </section>

        <section className="border-b border-hairline">
          <div className="mx-auto grid max-w-7xl grid-cols-1 gap-5 px-6 py-10 md:grid-cols-12 md:px-12 md:py-14">
            <div className="md:col-span-8">
              <ReasoningMatrix surface={fixtureSurface} />
            </div>
            <div className="md:col-span-4">
              <HashChainStream
                entries={chain}
                className="h-full min-h-[620px]"
              />
            </div>
          </div>
        </section>

        <section className="border-b border-hairline">
          <div className="mx-auto max-w-7xl px-6 py-10 md:px-12 md:py-14">
            <div className="mb-6 flex items-baseline justify-between">
              <h2 className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                active protocols · {fixtureProtocols.length}
              </h2>
              <span className="font-mono text-[0.6875rem] text-muted">
                hover a node to see its because-chain
              </span>
            </div>
            <ul className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
              {fixtureProtocols.map((p) => (
                <li key={p.id}>
                  <ProtocolNode protocol={p} />
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section>
          <div className="mx-auto max-w-7xl px-6 py-10 md:px-12 md:py-14">
            <TelemetryTicker events={fixtureTelemetry} />
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}

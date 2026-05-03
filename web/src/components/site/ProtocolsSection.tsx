import { Sectioned } from "@/components/ui/Sectioned";
import { ProtocolNode } from "@/components/viz/ProtocolNode";
import { HashChainDiagram } from "@/components/site/diagrams/HashChainDiagram";
import { fixtureProtocols } from "@/lib/fixtures/chain";

export function ProtocolsSection() {
  return (
    <Sectioned
      id="protocols"
      index="05"
      label="synthesized protocols"
      kicker="extracted, not authored"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          The framework sharpens itself.
          <br />
          <span className="text-ash">
            Every decision becomes a protocol.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          Each Reasoning Surface seal lands as one envelope on a SHA-256-linked
          chain. The chain is read at session boot; a corrupted past fails
          closed. Provenance is non-optional, by construction.
        </p>
      </div>

      <div className="mb-14">
        <HashChainDiagram />
      </div>

      <div className="mb-6 flex items-baseline justify-between gap-4 border-t border-hairline pt-6">
        <h3 className="font-display text-[1.25rem] text-bone">
          Live protocols on the chain
        </h3>
        <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-muted">
          hover any node · because-chain on the back
        </span>
      </div>

      <ul className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {fixtureProtocols.map((p) => (
          <li key={p.id}>
            <ProtocolNode protocol={p} />
          </li>
        ))}
      </ul>
    </Sectioned>
  );
}

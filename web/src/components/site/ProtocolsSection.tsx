import { Sectioned } from "@/components/ui/Sectioned";
import { ProtocolNode } from "@/components/viz/ProtocolNode";
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
          Hover any node to surface its because-chain: the signal that was
          observed, the cause that was inferred, the decision that landed.
          Every protocol is chain-linked — provenance is non-optional.
        </p>
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

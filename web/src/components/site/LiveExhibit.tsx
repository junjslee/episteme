import { Sectioned } from "@/components/ui/Sectioned";
import { ReasoningMatrix } from "@/components/viz/ReasoningMatrix";
import { HashChainStream } from "@/components/viz/HashChainStream";
import { fixtureSurface } from "@/lib/fixtures/reasoning-surface";
import { fixtureChain } from "@/lib/fixtures/chain";
import { markChainIntegrity } from "@/lib/parsers/chain";

export function LiveExhibit() {
  const chain = markChainIntegrity(fixtureChain);

  return (
    <Sectioned
      id="surface"
      index="02"
      label="the reasoning surface"
      kicker="distinction, not decoration"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          Four quadrants. Four categories of truth.
          <br />
          <span className="text-ash">
            No proceeding while Unknowns is empty.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          Every non-trivial decision is written onto a Reasoning Surface before
          execution. Knowns are facts with current evidence. Unknowns are named,
          not hidden. Assumptions are declared as assumptions. Disconfirmation
          states what evidence would prove the plan wrong. The chain records the
          seal.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-12">
        <div className="md:col-span-8">
          <ReasoningMatrix surface={fixtureSurface} />
        </div>
        <div className="md:col-span-4">
          <HashChainStream entries={chain} className="h-full min-h-[560px]" />
        </div>
      </div>
    </Sectioned>
  );
}

import { Sectioned } from "@/components/ui/Sectioned";
import { FrameworkLoopDiagram } from "@/components/site/diagrams/FrameworkLoopDiagram";

// Slim practice band (v2 redesign) — compressed from the five-stage card
// grid into a single ~1/3-viewport band for returning readers. The loop
// diagram's only remaining usage on the page lives here (the hero now
// carries InterrogationStrip instead). Server component, zero client JS.

export function FrameworkExplainer() {
  return (
    <Sectioned
      id="practice"
      index="04"
      label="the practice"
      kicker="frame · decompose · execute · verify · handoff"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[1.75rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.25rem]">
          The practice is the product.
        </h2>
        <div className="md:col-span-5">
          <p className="font-sans text-[0.9375rem] leading-relaxed text-ash">
            Frame names the one question. Decompose turns the why into a how.
            Execute moves in reversible steps. Verify judges against the
            metric, not the effort. Handoff persists what was learned. Each
            stage leaves an artifact on disk — a surface, a verdict, a sealed
            envelope.
          </p>
          <p className="mt-4 font-mono text-[0.8125rem] leading-relaxed text-bone">
            Five stages. The gate reads the artifacts they leave behind.
          </p>
        </div>
      </div>

      <FrameworkLoopDiagram />
    </Sectioned>
  );
}

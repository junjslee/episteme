import { Sectioned } from "@/components/ui/Sectioned";
import { FrameworkLoopDiagram } from "@/components/site/diagrams/FrameworkLoopDiagram";

const stages = [
  {
    n: "01",
    stage: "frame",
    body: "Name the one question. Separate knowns, unknowns, assumptions — before code.",
  },
  {
    n: "02",
    stage: "decompose",
    body: "Turn the why into a how. State the method and the alternatives you rejected.",
  },
  {
    n: "03",
    stage: "execute",
    body: "One bounded task. Reversible moves first. Each step sealed into the hash chain.",
  },
  {
    n: "04",
    stage: "verify",
    body: "Judge against the metric, not the effort. Facts and inferences stay distinct.",
  },
  {
    n: "05",
    stage: "handoff",
    body: "Persist the trail. Residual unknowns named, not hidden.",
  },
];

export function FrameworkExplainer() {
  return (
    <Sectioned
      index="04"
      label="the loop"
      kicker="frame · decompose · execute · verify · handoff"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          The practice is the product.
          <br />
          <span className="text-ash">
            Five stages. None skippable.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          The signed surface, the typed ledgers, the hash chain — those are
          residue. This loop is the thing. Skip a stage and the file system
          declines to proceed.
        </p>
      </div>

      <div className="mb-12">
        <FrameworkLoopDiagram />
      </div>

      <ol className="grid grid-cols-1 gap-0 border border-hairline md:grid-cols-5">
        {stages.map((s, i) => (
          <li
            key={s.stage}
            className={
              "flex flex-col gap-4 bg-surface/20 p-6 " +
              (i > 0 ? "border-t border-hairline md:border-t-0 md:border-l" : "")
            }
          >
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
                stage {s.n}
              </span>
              <span
                aria-hidden
                className="font-display text-[1.25rem] text-whisper"
              >
                {s.n}
              </span>
            </div>
            <h3 className="font-display text-[1.25rem] lowercase tracking-tight text-bone">
              {s.stage}
            </h3>
            <p className="font-mono text-[0.75rem] leading-relaxed text-ash">
              {s.body}
            </p>
          </li>
        ))}
      </ol>
    </Sectioned>
  );
}

import { Sectioned } from "@/components/ui/Sectioned";

const stages = [
  {
    n: "01",
    stage: "frame",
    body: "Name the core question. Declare the uncomfortable friction driving the work. Build the distinction map — facts / unknowns / assumptions / preferences — before planning touches code.",
  },
  {
    n: "02",
    stage: "decompose",
    body: "Convert non-linear context into explicit tasks. Translate 'why' into 'how'. For major choices, state method, alternatives considered, and why this one fits the governing intent.",
  },
  {
    n: "03",
    stage: "execute",
    body: "One bounded lane per owner. Reversible moves first. Record assumptions when data is incomplete. The hash chain seals each step.",
  },
  {
    n: "04",
    stage: "verify",
    body: "Validate against success metric, not effort spent. Distinguish proven facts from inference. Evaluate the hypothesis — validated, refined, or invalidated.",
  },
  {
    n: "05",
    stage: "handoff",
    body: "Update authoritative docs. Capture unresolved risks and exact next action. Residual unknowns marked, not hidden.",
  },
];

export function FrameworkExplainer() {
  return (
    <Sectioned
      index="03"
      label="the loop"
      kicker="frame · decompose · execute · verify · handoff"
    >
      <div className="mb-10 grid grid-cols-1 gap-8 md:grid-cols-12">
        <h2 className="font-display text-[2rem] leading-[1.1] text-bone md:col-span-7 md:text-[2.75rem]">
          Five stages. None optional.
          <br />
          <span className="text-ash">
            The kernel refuses to skip ahead.
          </span>
        </h2>
        <p className="font-sans text-[0.9375rem] leading-relaxed text-ash md:col-span-5">
          Speed comes from loop completion, not step-skipping. The agent that
          consistently closes Observe → Orient → Decide → Act outruns the one
          that collapses stages to feel fast.
        </p>
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

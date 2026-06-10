import { Sectioned } from "@/components/ui/Sectioned";
import { CornerMarkers } from "@/components/ui/CornerMarkers";

/*
 * Beat 02 — the three layers (DESIGN_V2_0 § 4) and where the engine
 * actually runs. Server component, zero client JS: the section answers
 * two newcomer questions the rest of the scroll assumes — "what are the
 * moving parts?" and "where does this live?" — so it stays still while
 * the EngineFlow above it moves.
 *
 * The division-of-labor line under each layer is the load-bearing idea:
 * each layer exists because the research record showed the other two
 * can't do its job.
 */

const LAYERS: {
  index: string;
  name: string;
  tagline: string;
  body: string;
  why: string;
  accent: string;
}[] = [
  {
    index: "α",
    name: "cognition",
    tagline: "the thinking — model-judged",
    body:
      "The interrogation itself: decompose the conclusion into claims, send the load-bearing ones to a fresh context that never sees the draft, argue the other side, commit to what would prove it wrong.",
    why: "Model-judged, because meaning lives where rules can't reach.",
    accent: "border-t-verified",
  },
  {
    index: "β",
    name: "structure",
    tagline: "the floor — deterministic",
    body:
      "File-system hooks route decision shapes, check that the verdict artifact exists and holds (a stop verdict admits nothing), and hard-block only the genuinely destructive. Everything is recorded.",
    why: "Deterministic, because deadlines are exactly when discipline gets skipped.",
    accent: "border-t-chain",
  },
  {
    index: "γ",
    name: "memory",
    tagline: "the compounding — chained",
    body:
      "When a verified interrogation teaches something durable, the lesson is sealed into a hash-chained protocol scoped to its context — and resurfaces, unasked, at the next matching decision.",
    why: "Chained, so the agent gets sharper on your codebase — not on the average of the internet.",
    accent: "border-t-unknown",
  },
];

export function ThreeLayers() {
  return (
    <Sectioned
      id="layers"
      index="02"
      label="the three layers"
      kicker="cognition · structure · memory"
    >
      <div className="relative">
        <CornerMarkers />
        <div className="grid grid-cols-1 gap-5 p-3 md:grid-cols-3">
          {LAYERS.map((layer) => (
            <article
              key={layer.name}
              className={`flex flex-col gap-4 border-t-2 panel-gradient p-6 md:p-8 ${layer.accent}`}
            >
              <div className="flex items-baseline justify-between">
                <h3 className="font-display text-[1.375rem] text-bone">
                  {layer.name}
                </h3>
                <span
                  aria-hidden
                  className="font-mono text-[0.875rem] text-muted"
                >
                  {layer.index}
                </span>
              </div>
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.16em] text-ash">
                {layer.tagline}
              </span>
              <p className="font-sans text-[0.9375rem] leading-relaxed text-ash">
                {layer.body}
              </p>
              <p className="mt-auto border-t border-hairline pt-4 font-sans text-[0.875rem] italic leading-relaxed text-bone">
                {layer.why}
              </p>
            </article>
          ))}
        </div>
      </div>

      <p className="mx-auto mt-10 max-w-3xl text-center font-sans text-[0.9375rem] leading-relaxed text-ash">
        It runs where you already work: a Claude Code plugin and a CLI today —
        and because the kernel is plain files (markdown, JSONL, hooks), the
        practice travels with you across tools, not with any one vendor.
      </p>
    </Sectioned>
  );
}

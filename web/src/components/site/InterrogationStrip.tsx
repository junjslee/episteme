/**
 * InterrogationStrip — the single hero visual.
 *
 * A conclusion stamped into a verdict, in miniature: claims are checked one
 * at a time, the verdict comes last. Server component, zero client JS —
 * pure DOM + CSS keyframes (`.stamp-in`, steps() easing, fill-mode forwards).
 * Only the per-chip `animationDelay` is inline; the animation itself is
 * class-owned so the global prefers-reduced-motion block can force the
 * final stamped state.
 */

type Tone = "ink" | "ochre" | "terracotta";

const TONE_STYLES: Record<Tone, string> = {
  ink: "border-line text-bone bg-transparent",
  ochre: "border-unknown/40 text-unknown bg-unknown/[0.04]",
  terracotta: "border-disconfirm/40 text-disconfirm bg-disconfirm/[0.06]",
};

const CLAIM_CHIPS: { id: string; label: string; tone: Tone }[] = [
  { id: "01", label: "measured", tone: "ink" },
  { id: "02", label: "cited", tone: "ink" },
  { id: "03", label: "inferred", tone: "ochre" },
  { id: "04", label: "assumed → refuted", tone: "terracotta" },
];

/** Chips stamp ~400ms apart once the hero strip slot has risen (1100ms). */
const STAMP_BASE_MS = 1300;
const STAMP_STEP_MS = 400;

export function InterrogationStrip() {
  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <p className="font-mono text-[0.75rem] leading-relaxed text-ash">
        <span className="uppercase tracking-[0.16em] text-ash">
          conclusion
        </span>{" "}
        &ldquo;memory system improves response quality&rdquo;
      </p>

      <div className="flex flex-wrap items-center gap-2">
        {CLAIM_CHIPS.map((chip, i) => (
          <span
            key={chip.id}
            className={`stamp-in inline-flex items-center gap-1.5 border px-2 py-[3px] font-mono text-[0.6875rem] uppercase tracking-[0.08em] ${TONE_STYLES[chip.tone]}`}
            style={{ animationDelay: `${STAMP_BASE_MS + i * STAMP_STEP_MS}ms` }}
          >
            <span className="text-ash">{chip.id}</span>
            {chip.label}
          </span>
        ))}

        <span
          aria-hidden
          className="stamp-in font-mono text-[0.6875rem] text-whisper"
          style={{
            animationDelay: `${STAMP_BASE_MS + CLAIM_CHIPS.length * STAMP_STEP_MS}ms`,
          }}
        >
          →
        </span>

        <span
          className="stamp-in inline-flex items-center gap-1.5 border border-chain/50 bg-chain/[0.05] px-2 py-[3px] font-mono text-[0.6875rem] uppercase tracking-[0.08em] text-chain"
          style={{
            animationDelay: `${STAMP_BASE_MS + (CLAIM_CHIPS.length + 1) * STAMP_STEP_MS}ms`,
          }}
        >
          verdict · proceed-with-revision
        </span>
      </div>
    </div>
  );
}

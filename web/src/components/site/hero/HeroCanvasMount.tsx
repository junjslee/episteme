"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { HeroPoster } from "./HeroPoster";
import { SURFACE_FIELDS, type GatePhase } from "./phase";

/**
 * Client boundary for the hero scene.
 *
 * Responsibilities — all of which are why this is separate from the
 * server-rendered hero copy:
 *  - Lazy-chunk the WebGL scene via next/dynamic with ssr:false, so three.js
 *    never lands in the landing page's initial JS.
 *  - Honour prefers-reduced-motion by rendering the static poster instead.
 *  - Reduce node count and disable pointer parallax on small screens.
 *  - Pause rendering entirely (frameloop="never") when the hero scrolls out of
 *    the viewport.
 *
 * Until hydration decides which applies, the poster is what paints — so the
 * hero is never an empty box and first paint stays cheap.
 */

const HeroScene = dynamic(() => import("./HeroScene"), {
  ssr: false,
  loading: () => null,
});

type Mode = "pending" | "poster" | "scene";

export function HeroCanvasMount() {
  const [mode, setMode] = useState<Mode>("pending");
  const [nodeCount, setNodeCount] = useState(2800);
  const [parallax, setParallax] = useState(true);
  const [visible, setVisible] = useState(true);
  const [phase, setPhase] = useState<GatePhase>("approach");
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setMode("poster");
      return;
    }
    const mobile = window.matchMedia("(max-width: 767px)").matches;
    setNodeCount(mobile ? 600 : 2800);
    setParallax(!mobile);
    setMode("scene");
  }, []);

  useEffect(() => {
    if (mode !== "scene") return;
    const el = wrapRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.02 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [mode]);

  const held = phase === "held";
  const verified = phase === "verified" || phase === "reset";

  return (
    <div ref={wrapRef} className="absolute inset-0">
      {mode !== "scene" ? (
        <HeroPoster />
      ) : (
        <>
          <HeroScene
            nodeCount={nodeCount}
            parallax={parallax}
            frameloop={visible ? "always" : "never"}
            onPhase={setPhase}
          />

          {/* Gate readout — a DOM overlay driven by the scene's phase
              TRANSITIONS (about four per loop), never per frame. Hidden on
              small screens, where the hero copy owns the space. */}
          <div
            aria-hidden
            data-gate-phase={phase}
            className="pointer-events-none absolute inset-x-0 bottom-[13%] hidden justify-center md:flex md:translate-x-[22%]"
          >
            <div
              className={`flex min-w-[20rem] flex-col gap-2 border px-4 py-3 font-mono text-[0.6875rem] uppercase tracking-[0.14em] backdrop-blur-sm transition-all duration-500 ${
                held
                  ? "border-disconfirm/50 bg-disconfirm/[0.07] opacity-100"
                  : verified
                    ? "border-verified/50 bg-verified/[0.07] opacity-100"
                    : "border-hairline/60 bg-void/40 opacity-0"
              }`}
            >
              <div className="flex items-center justify-between gap-6">
                <span className="text-muted">reasoning surface</span>
                <span
                  className={
                    held ? "text-disconfirm" : verified ? "text-verified" : "text-muted"
                  }
                >
                  {held ? "● held" : verified ? "● verified" : "○ idle"}
                </span>
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-1">
                {SURFACE_FIELDS.map((f, i) => (
                  <span
                    key={f}
                    className={`transition-all duration-300 ${
                      held || verified
                        ? "translate-y-0 opacity-100"
                        : "translate-y-1 opacity-0"
                    } ${verified ? "text-verified/90" : "text-ash"}`}
                    style={{ transitionDelay: `${i * 130}ms` }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

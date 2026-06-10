"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { EngineFlowStatic } from "./EngineFlowStatic";

/**
 * EngineFlowLoader — SSR static map + lazy client swap.
 *
 * The server prerenders EngineFlowStatic (the full labeled diagram), so the
 * mechanism is readable with zero client JS, before hydration, and forever
 * under prefers-reduced-motion. Only when the stage approaches the viewport
 * AND the reader allows motion does the animated EngineFlow chunk load and
 * swap in. Both renderers share one skeleton — the swap causes zero CLS.
 *
 * Reduced-motion readers never download the animation bundle at all; if the
 * preference flips on after load, EngineFlow itself degrades to the static
 * map via useReducedMotion.
 */

const EngineFlow = dynamic(
  () => import("./EngineFlow").then((mod) => mod.EngineFlow),
  { ssr: false, loading: () => <EngineFlowStatic /> },
);

export function EngineFlowLoader({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return; // never load the animated chunk
    }
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setAnimate(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={cn(className)}>
      {animate ? <EngineFlow /> : <EngineFlowStatic />}
    </div>
  );
}

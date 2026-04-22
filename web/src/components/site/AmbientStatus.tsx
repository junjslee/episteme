"use client";

import { useLiveResource } from "@/lib/hooks/use-live-resource";
import { cn } from "@/lib/utils";
import type { ChainEntry, Protocol, ReasoningSurface } from "@/lib/types/episteme";

interface SurfacePayload {
  surface: ReasoningSurface | null;
  age_minutes: number | null;
  mode: "live" | "fixtures";
}
interface ChainPayload {
  entries: ChainEntry[];
  integrity: "ok" | "broken";
  mode: "live" | "fixtures";
}
interface ProtocolsPayload {
  protocols: Protocol[];
  mode: "live" | "fixtures";
}

/**
 * Live telemetry chrome for the header. Polls three routes at 25s and collapses
 * into a compact three-indicator strip. Hidden below xl (1280px) because the
 * full row competes with the nav items at lg; at xl+ there's room for both.
 */
export function AmbientStatus({ className }: { className?: string }) {
  const surface = useLiveResource<SurfacePayload>(
    "/api/surface",
    { surface: null, age_minutes: null, mode: "live" },
    { intervalMs: 25_000 },
  );
  const chain = useLiveResource<ChainPayload>(
    "/api/chain?limit=1",
    { entries: [], integrity: "ok", mode: "live" },
    { intervalMs: 25_000 },
  );
  const protocols = useLiveResource<ProtocolsPayload>(
    "/api/protocols",
    { protocols: [], mode: "live" },
    { intervalMs: 25_000 },
  );

  const chainIntact = chain.data.integrity === "ok";
  const chainHead = chain.data.entries[0]?.this_hash;
  const surfaceAge = surface.data.age_minutes;
  const surfaceFresh = surfaceAge !== null && surfaceAge < 30;
  const hasSurface = surface.data.surface !== null;
  const protocolCount = protocols.data.protocols.length;

  return (
    <div
      className={cn(
        "hidden xl:flex items-center gap-4 shrink-0 font-mono text-[0.625rem] uppercase tracking-[0.12em] text-muted",
        className,
      )}
    >
      <Row
        label="chain"
        value={
          !chainIntact
            ? "BROKEN"
            : chainHead
              ? chainHead.slice(0, 6)
              : "—"
        }
        tone={!chainIntact ? "disconfirm" : chainHead ? "verified" : "muted"}
        pulse
      />
      <Row
        label="surface"
        value={
          !hasSurface
            ? "—"
            : surfaceFresh
              ? `${surfaceAge}m`
              : `${surfaceAge}m stale`
        }
        tone={!hasSurface ? "muted" : surfaceFresh ? "verified" : "unknown"}
      />
      <Row
        label="proto"
        value={protocolCount === 0 ? "soak" : protocolCount.toString().padStart(2, "0")}
        tone={protocolCount > 0 ? "chain" : "muted"}
      />
    </div>
  );
}

type Tone = "verified" | "unknown" | "disconfirm" | "chain" | "muted";

const toneDot: Record<Tone, string> = {
  verified: "bg-verified",
  unknown: "bg-unknown",
  disconfirm: "bg-disconfirm",
  chain: "bg-chain",
  muted: "bg-whisper",
};

const toneText: Record<Tone, string> = {
  verified: "text-verified",
  unknown: "text-unknown",
  disconfirm: "text-disconfirm",
  chain: "text-chain",
  muted: "text-muted",
};

function Row({
  label,
  value,
  tone,
  pulse,
}: {
  label: string;
  value: string;
  tone: Tone;
  pulse?: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5 whitespace-nowrap">
      <span className="text-muted">{label}</span>
      <span
        className={cn(
          "inline-block size-1 rounded-full",
          toneDot[tone],
          pulse && "status-pulse",
        )}
        aria-hidden
      />
      <span className={cn(toneText[tone])}>{value}</span>
    </span>
  );
}

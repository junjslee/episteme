import { cn } from "@/lib/utils";

export type Signal = "verified" | "unknown" | "disconfirm" | "chain" | "muted";

const styles: Record<Signal, string> = {
  verified: "border-verified/40 text-verified bg-verified/[0.04]",
  unknown: "border-unknown/40 text-unknown bg-unknown/[0.04]",
  disconfirm: "border-disconfirm/40 text-disconfirm bg-disconfirm/[0.04]",
  chain: "border-chain/40 text-chain bg-chain/[0.04]",
  muted: "border-line text-ash bg-transparent",
};

interface SignalBadgeProps {
  signal?: Signal;
  children: React.ReactNode;
  className?: string;
}

export function SignalBadge({
  signal = "muted",
  children,
  className,
}: SignalBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-2 py-[3px] font-mono text-[0.6875rem] uppercase tracking-[0.08em]",
        styles[signal],
        className,
      )}
    >
      <span
        className={cn(
          "inline-block size-1 rounded-full",
          signal === "verified" && "bg-verified",
          signal === "unknown" && "bg-unknown",
          signal === "disconfirm" && "bg-disconfirm",
          signal === "chain" && "bg-chain",
          signal === "muted" && "bg-ash",
        )}
      />
      {children}
    </span>
  );
}

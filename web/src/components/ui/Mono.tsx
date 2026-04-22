import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

interface MonoProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "bone" | "ash" | "muted" | "chain" | "verified" | "unknown" | "disconfirm";
}

const toneMap: Record<NonNullable<MonoProps["tone"]>, string> = {
  bone: "text-bone",
  ash: "text-ash",
  muted: "text-muted",
  chain: "text-chain",
  verified: "text-verified",
  unknown: "text-unknown",
  disconfirm: "text-disconfirm",
};

export function Mono({
  children,
  className,
  tone = "ash",
  ...rest
}: MonoProps) {
  return (
    <span
      className={cn(
        "font-mono text-[0.8125rem] tracking-tight",
        toneMap[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}

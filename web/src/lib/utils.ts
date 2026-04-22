import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Hash display — take first N chars, default 8 */
export function shortHash(hash: string, n = 8): string {
  return hash.slice(0, n);
}

/** Format a Date or ISO string as HH:MM:SS in the local timezone */
export function formatTime(t: Date | string): string {
  const d = typeof t === "string" ? new Date(t) : t;
  return d.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Relative time, short form */
export function relativeTime(t: Date | string): string {
  const then = typeof t === "string" ? new Date(t).getTime() : t.getTime();
  const delta = Math.max(0, Date.now() - then);
  const s = Math.floor(delta / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

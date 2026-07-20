import Link from "next/link";
import { RELEASE_FACTS } from "@/lib/release-facts";

const LINKS: { label: string; href: string; external?: boolean }[] = [
  { label: "github", href: "https://github.com/junjslee/episteme", external: true },
  { label: "readme", href: "/readme" },
  { label: "commands", href: "/commands" },
  { label: "dashboard", href: "/dashboard" },
  { label: "how it works", href: "/#how-it-works" },
  { label: "install", href: "/#install" },
];

export function Footer() {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-7xl flex-col gap-10 px-6 py-14 md:flex-row md:items-start md:justify-between md:px-12">
        <div className="flex max-w-sm flex-col gap-4">
          <span className="flex items-center gap-3 font-display text-[1.25rem] lowercase tracking-tight text-bone">
            <span
              aria-hidden
              className="inline-block size-2 rotate-45 border border-chain/70 bg-chain/25"
            />
            episteme
          </span>
          <p className="font-sans text-[0.9375rem] leading-relaxed text-muted">
            A way to think — 생각의 틀 — for the moments a fluent model would
            otherwise think for you.
          </p>
        </div>

        <nav>
          <ul className="grid grid-cols-2 gap-x-10 gap-y-3 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash">
            {LINKS.map((l) => (
              <li key={l.label}>
                <Link
                  href={l.href}
                  {...(l.external ? { target: "_blank", rel: "noopener" } : {})}
                  className="transition-colors hover:text-bone"
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>

      <div className="mx-auto max-w-7xl border-t border-hairline px-6 py-5 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-muted md:px-12">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span>
            {RELEASE_FACTS.testsGreen} tests green · hash-chain verified ·{" "}
            {RELEASE_FACTS.version}
          </span>
          <span>AGPL-3.0 · built on the practice it describes</span>
        </div>
      </div>
    </footer>
  );
}

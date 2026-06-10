import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-10 md:flex-row md:items-end md:justify-between md:px-12 md:py-14">
        <div className="flex flex-col gap-3">
          <span className="font-display text-[1.25rem] lowercase tracking-tight text-bone">
            episteme
          </span>
          <p className="max-w-md font-mono text-[0.75rem] leading-relaxed text-muted">
            A way to think — 생각의 틀 — for the moments a fluent model would
            otherwise think for you.
          </p>
        </div>
        <nav>
          <ul className="flex flex-wrap gap-6 font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-ash">
            <li>
              <Link href="https://github.com/junjslee/episteme" className="hover:text-bone">
                github
              </Link>
            </li>
            <li>
              <Link href="/#how-it-works" className="hover:text-bone">
                how it works
              </Link>
            </li>
            <li>
              <Link href="/#proof" className="hover:text-bone">
                proof
              </Link>
            </li>
            <li>
              <Link href="/#install" className="hover:text-bone">
                install
              </Link>
            </li>
            <li>
              <Link href="/dashboard" className="hover:text-bone">
                dashboard
              </Link>
            </li>
          </ul>
        </nav>
      </div>
      <div className="mx-auto max-w-7xl border-t border-hairline px-6 py-4 font-mono text-[0.625rem] uppercase tracking-[0.16em] text-muted md:px-12">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span>1367 tests green · hash-chain verified</span>
          <span>© 2026 · built on the practice it describes</span>
        </div>
      </div>
    </footer>
  );
}

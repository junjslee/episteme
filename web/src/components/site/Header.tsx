import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-void/80 backdrop-blur-md">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 md:px-12">
        <Link
          href="/"
          className="flex items-baseline gap-3 font-display text-[1.125rem] lowercase tracking-tight text-bone"
        >
          <span aria-hidden className="inline-block size-2 bg-chain" />
          episteme
          <span className="font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted">
            rc · v1.0
          </span>
        </Link>
        <ul className="hidden items-center gap-8 font-mono text-[0.75rem] uppercase tracking-[0.12em] text-ash md:flex">
          <li>
            <Link href="#framework" className="hover:text-bone transition-colors">
              framework
            </Link>
          </li>
          <li>
            <Link href="#surface" className="hover:text-bone transition-colors">
              surface
            </Link>
          </li>
          <li>
            <Link href="#protocols" className="hover:text-bone transition-colors">
              protocols
            </Link>
          </li>
          <li>
            <Link
              href="/dashboard"
              className="border border-line px-3 py-1.5 text-bone hover:border-chain hover:text-chain transition-colors"
            >
              dashboard →
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}

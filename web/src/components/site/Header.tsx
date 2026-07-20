import Link from "next/link";

/**
 * Header — shared by the landing, /readme, /commands and /dashboard.
 *
 * Server component with zero client JS. The live telemetry strip that used to
 * sit here polled three API routes on every page; it was removed in the Event
 * 164 revamp to keep the landing's initial JS lean. The dashboard renders its
 * own live viz below the fold, so nothing was lost that mattered.
 */
export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline/70 bg-void/60 backdrop-blur-md">
      <nav className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-4 md:px-12">
        <Link
          href="/"
          className="flex shrink-0 items-center gap-3 font-display text-[1.125rem] lowercase tracking-tight text-bone"
        >
          <span
            aria-hidden
            className="inline-block size-2 rotate-45 border border-chain/70 bg-chain/25"
          />
          <span className="leading-none">episteme</span>
          <span className="hidden font-mono text-[0.6875rem] uppercase tracking-[0.2em] text-muted sm:inline">
            a way to think
          </span>
        </Link>

        <ul className="hidden shrink-0 items-center gap-6 font-mono text-[0.75rem] uppercase tracking-[0.12em] text-ash md:flex">
          <li className="hidden lg:block">
            <Link href="/#how-it-works" className="transition-colors hover:text-bone">
              how it works
            </Link>
          </li>
          <li className="hidden lg:block">
            <Link href="/#way-to-think" className="transition-colors hover:text-bone">
              the practice
            </Link>
          </li>
          <li>
            <Link href="/commands" className="transition-colors hover:text-bone">
              commands
            </Link>
          </li>
          <li>
            <Link href="/dashboard" className="transition-colors hover:text-bone">
              dashboard
            </Link>
          </li>
          <li>
            <Link
              href="/#install"
              className="inline-block whitespace-nowrap border border-chain/50 bg-chain/10 px-3 py-1.5 text-bone transition-colors hover:bg-chain/20"
            >
              install
            </Link>
          </li>
          <li
            aria-label="locale"
            className="ml-1 hidden items-center gap-1.5 border-l border-hairline/60 pl-4 font-mono text-[0.625rem] uppercase tracking-[0.14em] text-muted lg:flex"
          >
            <Link href="/readme" className="transition-colors hover:text-ash" aria-label="English README">
              EN
            </Link>
            <span aria-hidden className="text-whisper">·</span>
            <Link href="/readme/ko" className="transition-colors hover:text-ash" aria-label="한국어 README">
              한
            </Link>
            <span aria-hidden className="text-whisper">·</span>
            <Link href="/readme/es" className="transition-colors hover:text-ash" aria-label="Español README">
              ES
            </Link>
            <span aria-hidden className="text-whisper">·</span>
            <Link href="/readme/zh" className="transition-colors hover:text-ash" aria-label="中文 README">
              中
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}

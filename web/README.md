# episteme · web

Go-to-market landing page + live operator-console dashboard for the [episteme](../README.md) sovereign cognitive kernel. Built with **Next.js 16** / **React 19** / **Tailwind 4** / **Turbopack** / **pnpm**.

Lives inside the kernel repo at `web/` so the dashboard can live-read the kernel's on-disk state during local development, and so the kernel's Blueprint D cascade detector stays aware of cross-references between marketing copy and kernel symbols. The directory is self-contained — nothing else in the repo depends on it.

---

## Local development

Requires Node.js **20.9+** and pnpm. From the kernel repo root:

```bash
cd web
pnpm install
pnpm dev              # http://localhost:3000
```

The three API routes return **fixture data** by default in `NODE_ENV=development` unless you set `EPISTEME_MODE` explicitly. To read your local kernel state live:

```bash
EPISTEME_MODE=live \
EPISTEME_HOME="$HOME/.episteme" \
EPISTEME_PROJECT="$(pwd)/.." \
pnpm dev
```

With those set, the dashboard will render:

- `/api/surface` — reads `$EPISTEME_PROJECT/.episteme/reasoning-surface.json`
- `/api/chain` — reads both hash-chained streams under `$EPISTEME_HOME/framework/`
- `/api/protocols` — reads `$EPISTEME_HOME/framework/protocols.jsonl`

The landing page polls at 30s; the dashboard polls at 10s. Both use `useLiveResource` for SWR-lite semantics (last-good data preserved across refetches).

---

## Deployment

### Vercel (recommended)

Vercel auto-detects the Next.js project. Two ways to deploy from this monorepo:

**Option A — point Vercel at `web/` as the project root.** Recommended. In the Vercel dashboard, create a new project, select this GitHub repo, and set the **Root Directory** to `web`. Vercel will detect Next.js 16, use the `build` script in `web/package.json`, and ship.

**Option B — CLI from inside `web/`.**

```bash
cd web
pnpm dlx vercel@latest              # first deploy (guided)
pnpm dlx vercel@latest deploy --prod # subsequent prod promotions
```

### Environment variables on Vercel

`web/` ships with a **safe default**: when `NODE_ENV=production` and no `EPISTEME_MODE` is set, `src/lib/server/mode.ts` resolves to `"fixtures"` — the landing + dashboard render the curated fixture data under `src/lib/fixtures/` rather than attempting to read `$EPISTEME_HOME` (which doesn't exist on Vercel's serverless infrastructure).

The matrix:

| `NODE_ENV`    | `EPISTEME_MODE`    | resolved mode | use case                                    |
|---------------|--------------------|---------------|---------------------------------------------|
| `development` | _unset_            | `live`        | local kernel on disk                        |
| `development` | `fixtures`         | `fixtures`    | demo local dev without a kernel             |
| `production`  | _unset_            | `fixtures`    | **Vercel default — safe for public site**   |
| `production`  | `live`             | `live`        | only if `$EPISTEME_HOME` is mounted         |
| any           | `live`             | `live`        | requires `$EPISTEME_HOME` to resolve        |
| any           | `fixtures`         | `fixtures`    | forces fixture data regardless of env       |

If you want to deploy the dashboard against a real kernel (e.g. an internal preview that runs a live `episteme` daemon), set:

- `EPISTEME_MODE=live`
- `EPISTEME_HOME=/path/to/.episteme` (absolute)
- `EPISTEME_PROJECT=/path/to/your-project` (absolute, optional — defaults to `process.cwd()`)

All three read-time path resolution happens in `src/lib/server/`. Relative paths are rejected and fall back gracefully; permission errors resolve to an empty payload with a warning, never a 5xx.

### Framework-specific notes

- The three API routes at `src/app/api/{chain,protocols,surface}/route.ts` are `export const dynamic = "force-dynamic"` and `runtime = "nodejs"`. Vercel ships them as Node serverless functions. They call `fs.readFile`, so moving them to Edge requires replacing the reader with an HTTP-based data fetch first.
- Fonts are self-hosted: Fraunces (Google) + JetBrains Mono (Google) via `next/font/google`; Satoshi (variable woff2) via `next/font/local` under `public/fonts/satoshi/` with the Fontshare Free Font License committed alongside. CI does not need network access to Fontshare.
- Images, if any, land under `public/` and are served by Vercel's default CDN. The landing and dashboard do not use `next/image` with remote sources.

### Preview deploys

Vercel previews use the same config. When reviewing a PR preview, the default mode is still `fixtures` — the page will render exactly as it does in production, just against the fixture snapshots.

---

## Build verification

```bash
pnpm build                    # production build via Turbopack
pnpm lint                     # ESLint flat config
NODE_ENV=production pnpm start  # serve the production bundle locally
```

Expected output at the end of `pnpm build`:

```
Route (app)
┌ ○ /
├ ○ /_not-found
├ ƒ /api/chain
├ ƒ /api/protocols
├ ƒ /api/surface
└ ○ /dashboard
```

Landing + dashboard are statically prerendered (`○`); API routes are dynamic (`ƒ`) per the `force-dynamic` directive.

---

## File layout

```
web/
├── public/
│   ├── data/                  # static JSONL snapshots (fixture-mode backing)
│   └── fonts/satoshi/         # self-hosted variable woff2 + FFL license
├── scripts/
│   └── build-fixtures.mjs     # regenerates public/data/ from TS fixtures
└── src/
    ├── app/
    │   ├── api/{chain,protocols,surface}/route.ts   # GET handlers
    │   ├── dashboard/page.tsx                       # operator console
    │   ├── globals.css                              # tokens + atmosphere + blur
    │   ├── layout.tsx                               # fonts + chrome layers
    │   └── page.tsx                                 # landing composition
    ├── components/
    │   ├── site/                                    # marketing surfaces
    │   ├── ui/                                      # primitives (Mono, SignalBadge, Sectioned, CornerMarkers)
    │   └── viz/                                     # dumb viz + Live* wrappers + EmptyState
    └── lib/
        ├── fixtures/                                # TS fixtures (dev + fixtures mode)
        ├── hooks/use-live-resource.ts               # SWR-lite client fetcher
        ├── parsers/                                 # JSONL + chain integrity
        ├── server/                                  # path resolver + readers + mode + zod
        └── types/episteme.ts                        # domain models
```

---

## Related docs

- [`../docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`](../docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md) — the v1.0 RC spec the dashboard visualizes
- [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) — kernel architecture Mermaid (pillars, blueprints, chain, framework)
- [`../docs/PROGRESS.md`](../docs/PROGRESS.md) — Events 18–22 capture the GTM work stream (v1 scaffold · v2 live wiring · v1.1 polish · visual coherence · demo + launch prep)

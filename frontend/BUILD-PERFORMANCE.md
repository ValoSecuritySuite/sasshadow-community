# Build & compile performance

## Root causes of slow compilation (findings)

1. **ESLint during build**  
   Next runs ESLint on every file during `next build`, which adds noticeable time. **Fix applied:** `eslint.ignoreDuringBuilds: true` in `next.config.ts`. Run `npm run lint` in CI or pre-commit instead.

2. **Webpack (default) vs Turbopack**  
   Dev server uses Webpack by default. **Fix applied:** Use `npm run dev:turbo` for local dev; Turbopack is much faster for incremental compilation.

3. **Barrel imports**  
   Importing from `@/hooks/api` loads the barrel, which re-exports all API hooks. The bundler and TypeScript still touch those modules. For pages that need only one or two hooks, consider direct imports, e.g.:
   - `import { useConnectors } from "@/hooks/api/use-connectors"`
   - instead of `import { useConnectors } from "@/hooks/api"`  
   This reduces work for the compiler and can speed up cold builds.

4. **Large single-file components**  
   `src/app/scan/page.tsx` is very large (~1,000+ lines). Splitting it into smaller components (e.g. result panels, forms, tabs) improves:
   - Incremental compilation (fewer lines recompiled per change)
   - IDE responsiveness and type-checking

5. **lucide-react**  
   Icons are tree-shaken, but the package is big. Duplicate import blocks were merged in `scan/page.tsx`. Keep one import per file when possible.

6. **TypeScript**  
   `tsconfig.json` already has `incremental: true` and `skipLibCheck: true`, which help. Do not set `typescript.ignoreBuildErrors: true` unless you need a one-off faster build and run type-check separately.

## Quick wins

| Action | When | Effect |
|--------|------|--------|
| `npm run dev:turbo` | Local dev | Much faster dev compilation |
| ESLint skipped in build | `next build` | Shorter production builds |
| Direct hook imports | Optional refactor | Slightly faster builds |
| Split large pages | Optional refactor | Faster incremental dev |

## Optional: skip TypeScript during build

Only if you run `tsc --noEmit` in CI and want faster `next build`:

```ts
// next.config.ts
typescript: { ignoreBuildErrors: true },
```

Not recommended for daily use; keep type-checking in the build for safety.

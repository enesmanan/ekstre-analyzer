---
paths:
  - "frontend/**"
---

# Frontend rules (ADR-0007)

- Packages: `vite@8`, `react@19`, `react-router@8`. Import `createBrowserRouter` from `react-router` and `RouterProvider` from `react-router/dom`. Do not add `react-router-dom`.
- Data mode routers; loaders are not used. Fetch with TanStack Query.
- No component libraries. Primitives live in `src/ui/`: Button, Input, Select, Table, Tabs, Dialog, Toast, DateRange.
- System font stack only (`ui-sans-serif, system-ui, sans-serif`). Do not load Google Fonts or self-host Inter.
- Type scale: 13 / 15 / 22 px. Gray scale plus one accent (`--accent`). No gradients, emoji, or card-in-card.
- Honor `prefers-color-scheme`.
- Upload is a raw `application/pdf` body (`fetch` + `File`/`Blob`). Never `FormData` or multipart.
- Preview uses `<img src="/api/v1/statements/{id}/preview.png">`. Do not use `blob:` URLs (CSP).
- Production CSP: `default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'`. Keep `build.assetsInlineLimit = 0`.
- uPlot is `React.lazy` on Overview only so it stays in a separate chunk.
- Amounts are kuruş integers; format with `lib/money.ts` (`Intl` `tr-TR`).

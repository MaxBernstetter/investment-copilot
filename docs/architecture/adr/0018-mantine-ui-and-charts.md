# ADR 0018: Mantine UI and charts

**Status:** Accepted · 2026-10-19 · Amends the chart choice of [[0005-react-spa-on-github-pages]]

## Context
The frontend is a React SPA ([[0005-react-spa-on-github-pages]]) that started with hand-written layout and Plotly.js for charts. Plotly.js adds about 1.5 MB (gzip) to the bundle, and the app has no shared look, no dark mode and no common set of accessible controls.

## Decision
1. The frontend uses **Mantine 9** (`@mantine/core`, `@mantine/hooks`) for layout, controls, tables and feedback. It adds no hand-written CSS beyond theme overrides in `src/theme.ts`.
2. Charts use **`@mantine/charts`** (Recharts), lazy-loaded. Plotly.js is removed in a later change of issue #153.

## Why
- One themed, accessible component kit with dark mode, shared by all views.
- Smaller bundle: about 1.5 MB → about 0.26 MB (gzip) for the charts.
- Charts are declarative React components, so they follow the same state and test patterns as the rest of the app.

## Consequences
- No wheel zoom in the charts; a brush selects a range instead.
- Mantine 9 needs React ^19.2; the project pins React 19.3.1.
- Tests wrap renders in `MantineProvider` (`src/test/render.tsx`).

## Rejected
- **shadcn/ui:** copies component code into the repository that we then own and maintain.
- **Chakra UI:** Emotion runtime cost and no charts package.
- **MUI and Ant Design:** heavier, a look that is hard to change, and paid features.
- **ECharts and uPlot:** imperative APIs with manual theming.
- **Tremor:** does not support React 19.

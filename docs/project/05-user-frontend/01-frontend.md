# Frontend

The user frontend (`src/frontend/`) is a static React single-page app that calls only the public `access` API. It is deployed to GitHub Pages (see [[0005-react-spa-on-github-pages]]).

## Stack

| Part | Choice |
|---|---|
| UI | React 19, TypeScript |
| Build and dev server | Vite 7 |
| Charts | Plotly.js (`plotly.js-dist-min`) |
| Unit tests | Vitest 3 with jsdom, Testing Library, jest-dom |
| Lint | ESLint 9 with typescript-eslint and react-hooks rules |

Dependencies are pinned to exact versions in `package.json`; `package-lock.json` is committed and is never edited by hand.

## Configuration

| Variable | Default | Use |
|---|---|---|
| `VITE_ACCESS_URL` | `http://localhost:8000` | Base URL of the `access` API, read at build time (`src/config.ts`) |

## Offline state

On mount the app calls `GET {VITE_ACCESS_URL}/health` (`src/backend.ts`). A `2xx` response shows "Backend online"; a non-2xx response or a network error shows a `role="alert"` message ("Backend offline: the YieldLens API is not reachable. Try again later."). While the check runs, the page shows "Loading…".

## Layout

| Path | Content |
|---|---|
| `src/main.tsx` | Entry point, renders `App` |
| `src/App.tsx` | Page, backend state |
| `src/backend.ts` | `isBackendOnline` health check |
| `src/config.ts` | `ACCESS_URL` |
| `src/test/setup.ts` | Test setup (jest-dom matchers) |
| `src/api/schema.d.ts` | Generated API types, git-ignored |

## Tasks

Run from the repository root with `devbox run -- task frontend:<task>` (see [[13-build-and-ci]]):

| Task | Does |
|---|---|
| `frontend:setup` | `npm ci` from the lockfile |
| `frontend:fmt` | ESLint with `--fix` |
| `frontend:lint` | ESLint |
| `frontend:typecheck` | `tsc -b` (app and Vite config) |
| `frontend:test:unit` | Vitest, single run |
| `frontend:build` | Production bundle in `dist/` |
| `frontend:dev` | Vite dev server |

CI runs `setup`, `lint`, `typecheck`, `test:unit` and `build` in `.github/workflows/frontend.yml`.

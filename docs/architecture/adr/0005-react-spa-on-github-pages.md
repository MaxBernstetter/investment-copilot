# ADR 0005: React SPA on GitHub Pages

**Status:** Accepted · 2026-10-18 · Supersedes the earlier choice of Dash

Charts superseded by [[0018-mantine-ui-and-charts]].

## Context
The final target is a live web app at no cost, with the UI on GitHub Pages. Pages serves static files only. Dash (and other server-rendered Python UIs) need a running Python server.

## Decision
Build the frontend as a **static React + TypeScript SPA** (Vite, Plotly.js), deployed to GitHub Pages. It calls only the public `access` API, through a client generated from its OpenAPI document.

## Consequences
- Free global hosting via CDN; frontend and backend deploy independently.
- Adds a TypeScript toolchain. The posting's "Python application" is covered by the Python backend services.
- CORS and the public API surface must be managed (read-only, rate-limited).

Rejected:
- Dash. It can't be hosted on Pages.
- Python-in-browser (Pyodide/Panel/Shiny). Slow startup and immature tooling.

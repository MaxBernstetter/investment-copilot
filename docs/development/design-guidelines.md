# Design guidelines

Binding reference for the frontend. **Direction A (Calm editorial) is binding**, chosen by the user on 2026-10-20, with the compact table density (`verticalSpacing="xs"`). The Burger/Navbar below `sm` is legacy and not required (see Display range).
Rule IDs (T, L, D, Q, C, A, Don't) are cited by the `designer` agent and by visual review. Taste is not a criterion; cite a rule.
The theme lives only in `src/frontend/src/theme.ts`; no other CSS (ADR 0018).

## Display range
- **Decided by the user on 2026-10-20: desktop only.** The frontend must look good on regular desktop displays, 1280–1920 px wide. Phone layouts (390 px) are no longer a requirement.
- Review and snapshot sizes: 1280×800, 1440×900 and 1920×1080, in light and dark.
- The Burger/Navbar below `sm` is legacy code that stays on main. No new mobile-specific work is done.

## Tokens
- T1 Type scale: body md 16; secondary sm 14; captions/labels xs 12. Headings 600: h1 26 (page title, one per page),
  h2 18 (card titles), h3 15 (sub-sections). No other sizes.
- T2 Spacing: page sections `Stack gap="lg"`; inside cards `gap="md"`; label↔value `gap={4}`; page header `mb="lg"`.
- T3 Radius `md` everywhere; badges `sm`. Shadows: none. Cards separate by border + page background (gray.0 / dark.8).
- T4 Colour roles: primary blue.8 (links, primary buttons, active nav). Text: default / `c="dimmed"` only.
  Status (only badges/alerts, always with icon + label): ok green, info blue, warn yellow (filled, autoContrast),
  error red. Simulated: orange (one badge in header + one subtle Alert). Reason: initial gray, revision blue, correction orange.
- T5 Chart palette (fixed order, never cycled, same in light and dark; validated with dataviz validate_palette.js,
  light #fff and dark #242424 surfaces): blue.8 #1971c2, orange.8 #e8590c, teal.8 #099268, grape.8 #9c36b5,
  pink.8 #c2255c, lime.9 #5c940d. Light: all checks pass, worst CVD ΔE 9.5. Dark: pass, contrast WARN for
  grape/pink (<3:1) → legend + values table required (we have both). Max 6 series (current + 5 overlays).
  Colour follows the series (a date keeps its colour when others are removed).

## Layout
- L1 AppShell: header 56 px; no desktop sidebar (≤5 views). Below `sm` (legacy, not required): Burger opens AppShell.Navbar
  (NavLinks + curve choice); header keeps logo, Burger and the as-of status.
- L2 Body: `Container size={1200} px={{ base: 'md', sm: 'lg' }} py="lg"`. Each page = PageHeader + sections in Cards.
- L3 PageHeader: Title order 1 + one-line dimmed subtitle (what, which unit) + actions right .
- L4 Footer: in-flow at page end (`component="footer"`, Divider above, `py="lg"`, Text xs dimmed): source + licence
  left; API docs, Methodology, GitHub, version · commit right. Not fixed.
- L5 Key figures as a 4-col (desktop) SimpleGrid of StatCards above the chart. Max 4.
- L6 No horizontal page scroll at 1280 px; wide tables scroll inside `Table.ScrollContainer`.

## Data display
- D1 All numbers tabular (`Table tabularNums`, Title theme override). Numeric columns `ta="right"`, header too.
- D2 Yields: 3 decimals, unit in the column header or after the value with a thin space: `2.871 %`.
  Spreads and changes: basis points, 1 decimal, always signed with true minus: `+9.0 bp`, `−2,376.0 bp`.
  Thousands separator in bp. Missing: `–`.
- D3 Dates: valid dates ISO `2026-10-16`. Knowledge times: `19 Oct 2026, 18:49:25 UTC` (one helper `formatUtc`).
  Inputs that take local time say so in their description ("Your local time, shown in UTC elsewhere").
- D4 Charts: one y-axis; y domain `['auto','auto']` (not forced to 0); `gridAxis="y"`; `curveType="linear"` (never
  smoothed); stroke 2; dots only when ≤ 15 points; `connectNulls={false}` (gaps stay gaps); tooltip 3 dp;
  `tooltipAnimationDuration={0}` and no line animation (snappy); legend only for ≥ 2 series; single series is
  named by the card title; axis labels in dimmed xs; card title states measure + unit.
- D5 Every chart has a table equivalent (values table or Chart|Table toggle).
- D6 Status/quality is never colour alone: Badge with icon + word, explanation on demand (pattern Q1).

## Patterns
- Q1 Quality flag: `Popover width={320} withArrow` around
  `Badge component="button" color={severity} leftSection={<Icon/>}>{rule} · {severity}</Badge>`;
  dropdown: Text fw 600 rule name, Text sm the explanation from the API (as written in the plausibility note),
  `Anchor size="sm" href={METHODOLOGY_URL}` "How we check this". Popover (click/Enter) not HoverCard (keyboard).
- Q2 Empty state: `EmptyState` (Mantine 9) with title + one-sentence description + action, wrapped `role="status"`.
- Q3 Loading: `Skeleton` with the final element's size (chart 320, table 5 rows × 36) + VisuallyHidden "Loading…".
- Q4 Error: `Alert color="red" title="…"` + `Button variant="light" size="xs"` "Try again".
- Q5 Explanations: `Tooltip` (multiline, w 280) on an info `ActionIcon` next to a label, for "Valid date"
  and "Compare from". "Known as of" uses dimmed helper text in the header as-of popover (see C3), not a tooltip on the label.

## Copy
- C1 Sentence case everywhere (titles, buttons, badges). No ALL CAPS except StatCard labels (xs).
- C2 Page titles: "Yield curve", "Time series", "Changes", "Data quality", "Runs and alerts".
- C3 Valid date tooltip: "The business day the yield applies to, as published by the ECB."
  Known as of tooltip: "See the data exactly as YieldLens knew it at that moment. Later corrections are
  hidden. Choose Now to see the latest knowledge."
- C4 Errors say what happened and what to do; no stack traces, no HTTP codes in the headline.

## Accessibility
- A1 WCAG 2.1 AA contrast (text 4.5:1, UI and chart marks 3:1 or table relief). axe: zero violations.
- A2 Keyboard: all actions reachable by Tab in visual order; focus ring visible (`focusRing: 'auto'`); popovers
  open with Enter/Space and close with Esc.
- A3 Landmarks: header, nav, main, footer (contentinfo); one h1 per page.
- A4 Live regions: as-of status `role="status"`; errors `role="alert"`.

## Don't
- No hand-written CSS files, `style={{…}}` props, or CSS modules (theme overrides only).
- No web fonts, no icon fonts; icons only from `@tabler/icons-react` by named import (≤ 12 icons).
- No smoothed lines, dual axes, 0-forced yield axes, rainbow or cycled palettes, numbers on every point.
- No status colours as series colours; no colour-only meaning.
- No more than one banner (Alert) stacked above content; simulated + as-of go in the header/status, not two alerts.
- No uppercase badges, no raw floats (`3.4444646497`), no `toUTCString()`, no hyphen as minus.
- No per-view copies of global state (curve, as-of).
- No new UI library or chart library; no Mantine components outside core/charts/hooks.

Related: [[03-agent-harness]] (the `designer` agent), [[principles/README|principles]]

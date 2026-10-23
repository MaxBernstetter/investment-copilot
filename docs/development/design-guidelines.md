# Design guidelines

Binding reference for the frontend. **Direction A (Calm editorial) is binding**, chosen by the user on 2026-10-20, with the compact table density (`verticalSpacing="xs"`). The Burger/Navbar below `sm` is legacy and not required (see Display range).
Rule IDs (T, L, D, Q, C, A, Don't) are cited by the `designer` agent in its UI spec. Taste is not a criterion; cite a rule.
The theme lives only in `src/frontend/src/theme.ts`; no other CSS (ADR 0018).

## Display range
- **Decided by the user on 2026-10-20: desktop only.** The frontend must look good on regular desktop displays, 1280–1920 px wide. Phone layouts (390 px) are no longer a requirement.
- Sizes the e2e layout checks run at: 1280×800, 1440×900 and 1920×1080. There are no screenshot baselines; the user reviews the look.
- The Burger/Navbar below `sm` is legacy code that stays on main. No new mobile-specific work is done.

## Tokens
- T1 Type scale: body md 16; secondary sm 14; captions/labels xs 12. Headings 600: h1 26 (page title, one per page),
  h2 18 (card titles), h3 15 (sub-sections). No other sizes.
- T2 Spacing: page sections `Stack gap="lg"`; inside cards `gap="md"`; label↔value `gap={4}`; page header `mb="lg"`.
- T3 Radius `md` everywhere; badges `sm`. Shadows: none. Cards separate by border + page background (gray.0 / dark.8).
- T4 Colour roles: primary blue.8 (links, primary buttons, active nav). Text: default / `c="dimmed"` only.
  Amended 2026-10-23 (#282): light-mode subtle primary buttons (e.g. the Values table History button) use **blue.9**, not blue.8.
  Primary filled buttons and active nav stay blue.8.
  Reason: blue.8 is 4.23:1 on the gray.1 table row hover, below AA, and the theme cannot target ancestor hover (ADR 0018).
  Contrast: blue.9 on white 6.09:1, on gray.0 5.77:1 (page background), on gray.1 row hover 5.13:1; hover background blue.0 gives blue.9 5.48:1.
  Dark mode keeps its own shade.
  Status (only badges/alerts, always with icon + label): ok green, info blue, warn yellow (filled, autoContrast),
  error red. Simulated: orange (one badge in header + one subtle Alert). Reason: initial gray, revision blue, correction orange.
  Market state is not quality: the 'Inverted' badge is `Badge color="gray" variant="light" size="sm"` with `IconArrowsDownUp` and the word, never a status colour.
- T5 Chart palette (fixed order, never cycled, same in light and dark; validated with dataviz validate_palette.js,
  light #fff and dark #242424 surfaces): blue.8 #1971c2, orange.8 #e8590c, teal.8 #099268, grape.8 #9c36b5,
  pink.8 #c2255c, lime.9 #5c940d. Light: all checks pass, worst CVD ΔE 9.5. Dark: pass, contrast WARN for
  grape/pink (<3:1) → legend + values table required (we have both). Max 6 series (current + 5 overlays).
  Colour follows the series (a date keeps its colour when others are removed).
  Overlay colours: the shown curve is slot 0; each overlay entry keeps the lowest free slot it got when added until removed. Legend labels are `{curve} · {date}`.

## Layout
- L1 AppShell: header 56 px; no desktop sidebar (≤5 views). Below `sm` (legacy, not required): Burger opens AppShell.Navbar
  (NavLinks + curve choice); header keeps logo, Burger and the as-of status. The curve choice is a `Select` (`aria-label="Curve"`, size xs, w 280) right of the view tabs, grouped "Published" then "Simulated", with options in catalogue order showing the catalogue label. An unknown `?curve=` falls back to the default curve, never to a simulated one.
- L2 Body: `Container size={1200} px={{ base: 'md', sm: 'lg' }} py="lg"`. Each page = PageHeader + sections in Cards.
- L3 PageHeader: Title order 1 + one-line dimmed subtitle (what, which unit) + actions right .
- L4 Footer: in-flow at page end (`component="footer"`, Divider above, `py="lg"`, Text xs dimmed): attribution left, from the curve catalogue: `{attribution}, {label}.` plus the publisher's reuse-terms link where the source has reuse terms; simulated curves: `{attribution}. Scenario data, not published by {publisher}.`; empty until the catalogue has loaded. Overlays list each distinct attribution under the chart; the footer keeps the shown curve's line and terms link. Right: API docs, Methodology, GitHub, version · commit. Not fixed.
- L5 Key figures as a 4-col (desktop) SimpleGrid of StatCards above the chart. Max 4.
- L6 No horizontal page scroll at 1280 px; wide tables scroll inside `Table.ScrollContainer`.

## Data display
- D1 All numbers tabular (`Table tabularNums`, Title theme override). Numeric columns `ta="right"`, header too.
- D2 Yields: 3 decimals, unit in the column header or after the value with a narrow no-break space (U+202F): `2.871 %`.
  Spreads and changes: basis points, 1 decimal, always signed with true minus: `+9.0 bp`, `−2,376.0 bp`.
  Thousands separator in bp. Missing: `–`. In a table the unit may sit in the column header (`Value (bp)`) with bare signed cells (`+9.0`, `−12.4`).
- D3 Dates: valid dates ISO `2026-10-16`. Knowledge times: `19 Oct 2026, 18:49:25 UTC` (one helper `formatUtc`).
  Inputs that take local time say so in their description ("Your local time, shown in UTC elsewhere").
- D4 Charts: one y-axis; y domain `['auto','auto']` (not forced to 0); `gridAxis="y"`; `curveType="linear"` (never
  smoothed); stroke 2; dots only when ≤ 15 points; `connectNulls={false}` (gaps stay gaps); tooltip 3 dp;
  `tooltipAnimationDuration={0}` and no line animation (snappy); legend only for ≥ 2 series, and legend entries are `{series} · {date}` for curve overlays; single series is
  named by the card title; axis labels in dimmed xs; card title states measure + unit.
  Spreads (2Y–10Y, 3M–10Y) add a dashed, dimmed reference line at 0 bp labelled "0 bp" (stroke 1, `var(--mantine-color-dimmed)`) and the caption "Inverted on {n} of {m} days"; curvature has no 0 line. The y domain stays auto, so the line shows only where 0 is in range. Measure charts (bp) use 1 decimal in the tooltip and ticks; yield charts keep 3 decimals.
- D5 Every chart has a table equivalent (values table or Chart|Table toggle).
- D6 Status/quality is never colour alone: Badge with icon + word, explanation on demand (pattern Q1).

## Patterns
- Q1 Quality flag: `Popover width={320} withArrow` around
  `Badge component="button" color={severity} leftSection={<Icon/>}>{rule} · {severity}</Badge>`;
  dropdown: Text fw 600 rule name, Text sm the explanation from the API (as written in the plausibility note),
  `Anchor size="sm" href={METHODOLOGY_URL}` "How we check this". Popover (click/Enter) not HoverCard (keyboard).
- Q2 Empty state: `EmptyState` (Mantine 9) with title + one-sentence description + action, wrapped `role="status"`. The Time series view's empty states (yield or measure) follow it.
- Q3 Loading: `Skeleton` with the final element's size (chart 320, table 5 rows × 36) + VisuallyHidden "Loading…".
- Q4 Error: `Alert color="red" title="…"` + `Button variant="light" size="xs"` "Try again". The Time series view's offline and error answers follow it.
- Q5 Explanations: `Tooltip` (multiline, w 280) on an info `ActionIcon` next to a label, for "Valid date", "Compare from" and each key-figure label in the Yield curve view. Tooltips open on hover and keyboard focus (theme `events` focus: true) and close with Esc.
  "Known as of" uses dimmed helper text in the header as-of popover (see C3), not a tooltip on the label.
  The Time series measure card title carries the same info icon and definition (`MEASURE_HELP`) as the curve-view card.
- Q6 Overlay entries: a pill row (`ul aria-label="Overlaid curves"`, each entry a colour swatch + `{label} · {date}`, with a remove button `Remove {label} · {date} from overlay`). At most 5 overlays plus the shown curve. When the limit is reached, a disabled add control shows the reason as dimmed hint text (not a tooltip). Removing an entry moves focus to the neighbouring remove button.
- Q7 Notes under a chart (shared with #258): the order directly below the chart is (1) one `Alert variant="light" color="blue" role="note"` convention note, (2) one dimmed sm line per drawn curve that lacks tenors other drawn curves publish ("No value on {label}: 1.5M, 20Y.", or "for {n} maturities" above 8), (3) an h3 "Attribution" list of `{catalogue attribution} ({labels})`. Notes never sit above the chart and are not a banner.

## Copy
- C1 Sentence case everywhere (titles, buttons, badges). No ALL CAPS except StatCard labels (xs).
- C2 Page titles: "Yield curve", "Time series", "Changes", "Data quality", "Runs and alerts".
- C3 Valid date tooltip: "The business day the yield applies to, as published by {publisher}." (simulated: "The business day the yield applies to in this scenario.")
  Known as of helper text (dimmed text in the header as-of popover, not a label tooltip): "See the data
  exactly as YieldLens knew it at that moment. Later corrections are hidden. Choose Now to see the latest
  knowledge."
- C4 Errors say what happened and what to do; no stack traces, no HTTP codes in the headline.
- C5 Unavailable values show `–` and a dimmed hint saying why: 'No 5Y value', 'No 2Y or 10Y value' or 'Not available'. A present value with a flagged input adds 'Input flagged: 10Y' / 'Inputs flagged: 2Y, 10Y'. The Time series table's Quality column carries these hints for null or flagged days.
- C6 Curve convention in text, never a badge: curve view subtitle `{label} · {rate type} rates, {compounding} compounding`; curve card title `{Rate type} curve ({unit})`.
- C7 Comparability copy: "These curves are not directly comparable: {rate types differ (a, b)} {and compounding differs (c, d)}. A gap between lines can come from the convention, not from the market."

## Accessibility
- A1 WCAG 2.1 AA contrast (text 4.5:1, UI and chart marks 3:1 or table relief). axe: zero violations.
- A2 Keyboard: all actions reachable by Tab in visual order; focus ring visible (`focusRing: 'auto'`); popovers
  open with Enter/Space and close with Esc.
- A3 Landmarks: header, nav, main, footer (contentinfo); one h1 per page.
- A4 Live regions: as-of status `role="status"`; errors `role="alert"`.
- A5 Links inside running text (an `Anchor` within a `Text` sentence) use `underline="always"`, so they never differ from the text by colour alone (WCAG 1.4.1, axe `link-in-text-block`). Links that stand alone (own line, `Group`, `Stack`, popover footer) keep the default underline on hover.

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

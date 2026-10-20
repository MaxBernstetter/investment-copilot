import { Alert, AppShell, Badge, Card, Table, Title, Tooltip, createTheme, rem, type CSSVariablesResolver } from '@mantine/core'

const sans =
  'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

/** Chart series colours in fixed order, the same in light and dark (design guidelines T5). */
export const CHART_COLORS = ['blue.8', 'orange.8', 'teal.8', 'grape.8', 'pink.8', 'lime.9'] as const

/** Dimmed text is darkened (light) or lightened (dark) so it meets 4.5:1 contrast (A1). */
export const cssVariablesResolver: CSSVariablesResolver = () => ({
  variables: {},
  light: { '--mantine-color-dimmed': 'var(--mantine-color-gray-7)' },
  dark: { '--mantine-color-dimmed': 'var(--mantine-color-dark-1)' },
})

export const theme = createTheme({
  primaryColor: 'blue',
  primaryShade: { light: 8, dark: 5 },
  autoContrast: true,
  fontFamily: sans,
  fontFamilyMonospace: 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
  headings: {
    fontFamily: sans,
    fontWeight: '600',
    sizes: {
      h1: { fontSize: rem(26), lineHeight: '1.25' },
      h2: { fontSize: rem(18), lineHeight: '1.35' },
      h3: { fontSize: rem(15), lineHeight: '1.4' },
    },
  },
  defaultRadius: 'md',
  cursorType: 'pointer',
  focusRing: 'auto',
  components: {
    AppShell: AppShell.extend({
      styles: {
        main: { backgroundColor: 'light-dark(var(--mantine-color-gray-0), var(--mantine-color-dark-8))' },
      },
    }),
    Card: Card.extend({ defaultProps: { withBorder: true, padding: 'lg', radius: 'md' } }),
    Table: Table.extend({
      defaultProps: { tabularNums: true, verticalSpacing: 'xs', highlightOnHover: true },
    }),
    Title: Title.extend({ styles: { root: { fontVariantNumeric: 'tabular-nums' } } }),
    Badge: Badge.extend({
      defaultProps: { variant: 'light', radius: 'sm' },
      styles: { label: { textTransform: 'none' } },
    }),
    Alert: Alert.extend({ defaultProps: { variant: 'light' } }),
    Tooltip: Tooltip.extend({
      defaultProps: { withArrow: true, multiline: true, w: 280, openDelay: 300 },
    }),
  },
  other: {
    contentWidth: 1200,
    status: { ok: 'green', info: 'blue', warn: 'yellow', error: 'red', simulated: 'orange' },
    reason: { initial: 'gray', revision: 'blue', correction: 'orange' },
  },
})

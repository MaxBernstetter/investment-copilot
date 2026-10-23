import { createElement } from 'react'
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleDashed,
  IconInfoCircle,
} from '@tabler/icons-react'
import {
  Alert,
  AppShell,
  Badge,
  type BadgeProps,
  Button,
  Card,
  Table,
  Text,
  Title,
  Tooltip,
  createTheme,
  rem,
  type CSSVariablesResolver,
} from '@mantine/core'

const sans =
  'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

/** Chart series colours in fixed order, the same in light and dark (design guidelines T5). */
export const CHART_COLORS = ['blue.8', 'orange.8', 'teal.8', 'grape.8', 'pink.8', 'lime.9'] as const

const REASON_COLORS: Record<string, string> = {
  correction: 'orange',
  revision: 'blue',
}

export function reasonBadgeProps(reason: string): Pick<BadgeProps, 'color' | 'variant' | 'miw'> {
  if (reason === 'correction') {
    // orange.6 keeps L > theme luminanceThreshold so autoContrast uses black label text (≥4.5:1).
    return { color: 'orange.6', variant: 'filled', miw: 'max-content' }
  }
  return { color: REASON_COLORS[reason] ?? 'gray', variant: 'light', miw: 'max-content' }
}

/** Status badges for quality flags and days; the icon carries the status without colour alone. */
export function qualityBadgeProps(status: string): Pick<BadgeProps, 'color' | 'variant' | 'leftSection'> {
  const icon = (Icon: typeof IconCircleCheck) => createElement(Icon, { size: 12, 'aria-hidden': true })
  if (status === 'passed') {
    return { color: 'green.7', variant: 'filled', leftSection: icon(IconCircleCheck) }
  }
  if (status === 'info') {
    return { color: 'blue', variant: 'light', leftSection: icon(IconInfoCircle) }
  }
  if (status === 'warn') {
    return { color: 'yellow', variant: 'filled', leftSection: icon(IconAlertTriangle) }
  }
  return { color: 'gray', variant: 'light', leftSection: icon(IconCircleDashed) }
}

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
    // Figures in Text use tabular numerals (D1); Mantine has no style prop for font-variant-numeric.
    Text: Text.extend({
      styles: (_theme, props) => ({
        root: props.variant === 'tabular' ? { fontVariantNumeric: 'tabular-nums' } : {},
      }),
    }),
    Badge: Badge.extend({
      defaultProps: { variant: 'light', radius: 'sm' },
      styles: { label: { textTransform: 'none' } },
    }),
    Alert: Alert.extend({ defaultProps: { variant: 'light' } }),
    // Subtle buttons in the primary colour: Mantine's dark light-colour is blue.0 (near white), so pin the text and hover.
    Button: Button.extend({
      vars: (_theme, props) => ({
        root:
          props.variant === 'subtle'
            ? {
                '--button-color': 'light-dark(var(--mantine-color-blue-9), var(--mantine-color-blue-4))',
                '--button-hover': 'light-dark(var(--mantine-color-blue-1), var(--mantine-color-blue-light))',
              }
            : {},
      }),
    }),
    Tooltip: Tooltip.extend({
      defaultProps: {
        withArrow: true,
        multiline: true,
        w: 280,
        openDelay: 300,
        events: { hover: true, focus: true, touch: false },
      },
    }),
  },
  other: {
    contentWidth: 1200,
    status: { ok: 'green', info: 'blue', warn: 'yellow', error: 'red', simulated: 'orange' },
    reason: { initial: 'gray', revision: 'blue', correction: 'orange' },
  },
})

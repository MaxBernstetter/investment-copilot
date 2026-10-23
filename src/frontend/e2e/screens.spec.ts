import { test, expect, type Page } from '@playwright/test'
import {
  assertNoHorizontalScroll,
  runAxe,
  expectChartsInsideCards,
  expectOpaque,
  settleAnimations,
  setColorScheme,
  VIEWPORTS,
  waitForCurveLoaded,
  waitForKeyFigures,
} from './helpers'
import { catalogue, curveBody, curveGrid, freezeClock, installApiMocks, measuresBody, measuresGrid } from './mockApi'

const AXE_VIEWPORT = { width: 1440, height: 900 }

/** Checks the layout at every viewport and scheme: no horizontal scroll at 1280 px, and charts inside their cards. */
async function checkLayout(page: Page, schemes: ('light' | 'dark')[]) {
  for (const { width, height } of VIEWPORTS) {
    for (const scheme of schemes) {
      await page.setViewportSize({ width, height })
      await setColorScheme(page, scheme)
      if (width === 1280) {
        await assertNoHorizontalScroll(page)
      }
      await page.mouse.move(0, 0)
      await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
      await expectChartsInsideCards(page)
    }
  }
}

async function assertAxeAt(page: Page, schemes: ('light' | 'dark')[]) {
  await page.setViewportSize(AXE_VIEWPORT)
  for (const scheme of schemes) {
    await setColorScheme(page, scheme)
    await runAxe(page)
  }
}

/** Opens the Quality tab on the default curve; the fixture days are not awaited here. */
async function openQualityTab(page: Page) {
  await page.goto('/')
  await waitForCurveLoaded(page)
  await page.getByRole('tab', { name: 'Quality' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Data quality' })).toBeVisible()
}

async function openQuality(page: Page) {
  await openQualityTab(page)
  await expect(page.getByRole('cell', { name: '2026-10-16' })).toBeVisible()
}

/** Overrides the quality endpoint for one test; registered after beforeEach, so it wins. */
async function routeQuality(page: Page, status: number, body: unknown) {
  await page.route('**/v1/curves/*/quality**', (route) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }),
  )
}

/** Overrides the measures endpoint for one test; registered after beforeEach, so it wins. */
async function routeMeasures(page: Page, status: number, body: unknown) {
  await page.route('**/v1/curves/*/measures**', (route) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }),
  )
}

/** The key-figure card with this label, found by its label text. */
function statCard(page: Page, label: string) {
  return page.locator('.mantine-Card-root', { has: page.getByText(label, { exact: true }) })
}

/** Opens one flag popover at every viewport and scheme, checks it, and closes it again. */
async function checkFlagPopover(page: Page, flagName: string) {
  const flag = page.getByRole('button', { name: flagName })
  const link = page.getByRole('link', { name: 'How we check this' })
  for (const { width, height } of VIEWPORTS) {
    for (const scheme of ['light', 'dark'] as const) {
      await page.setViewportSize({ width, height })
      await setColorScheme(page, scheme)
      await flag.focus()
      await page.keyboard.press('Enter')
      await expect(link).toBeFocused()
      await settleAnimations(page)
      await expectOpaque(link)
      await page.mouse.move(0, 0)
      if (width === AXE_VIEWPORT.width) {
        await runAxe(page)
      }
      await expect(link).toBeVisible()
      await page.keyboard.press('Escape')
      await expect(link).toBeHidden()
    }
  }
}

const QUALITY_META = { as_of: '2026-10-19T12:00:00Z', source_attribution: 'Source: ECB statistics' }

test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(() => {
    window.matchMedia = (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })
  })
  await freezeClock(page)
  await installApiMocks(page, 'online')
})

test.describe('screens §7', () => {
  test('S1 curve, real, live', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await expect(page.getByText('+52.1 bp')).toBeVisible()
    await expect(page.getByText('+77.1 bp')).toBeVisible()
    await expect(page.getByText('\u221212.1 bp')).toBeVisible()
    await expect(statCard(page, '10Y yield')).toContainText('2.871')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S2 curve, simulated, as-of spike', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim&as_of=2026-10-19T18%3A49%3A25Z')
    await waitForCurveLoaded(page)
    await expect(page.getByRole('status')).toContainText('As of 19 Oct 2026, 18:49:25 UTC')
    await expect(page.getByRole('note')).toBeVisible()
    await expect(page.getByText('Flagged: 10Y', { exact: true })).toBeVisible()
    await expect(page.getByText('Input flagged: 10Y')).toHaveCount(3)
    await expect(page.getByText('Value flagged')).toBeVisible()
    await expect(page.getByText('+2,405.0 bp')).toBeVisible()
    await expect(page.getByText('+2,430.0 bp')).toBeVisible()
    await expect(page.getByText('\u22122,365.0 bp')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S3 curve with two overlays', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByLabel(/Valid date/).fill('2026-10-15')
    await page.getByRole('button', { name: 'Add to overlay' }).click()
    await page.getByLabel(/Valid date/).fill('2026-10-14')
    await page.getByRole('button', { name: 'Add to overlay' }).click()
    await page.getByLabel(/Valid date/).fill('2026-10-16')
    await expect(page.getByLabel('Overlaid curves')).toBeVisible()
    await waitForKeyFigures(page)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S3b overlay entry from another curve', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'par')
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByLabel(/Valid date/).fill('2026-10-15')
    await page.getByRole('button', { name: 'Add to overlay' }).click()
    await page.getByLabel(/Valid date/).fill('2026-10-16')
    await page.getByRole('combobox', { name: 'Curve' }).click()
    await page.getByRole('option', { name: 'US Treasury par' }).click()
    await expect(page).toHaveURL(/curve=ust-par/)
    await waitForCurveLoaded(page)
    await page.getByRole('button', { name: 'Add to overlay' }).click()

    const pills = page.getByRole('list', { name: 'Overlaid curves' })
    await expect(pills.getByRole('listitem')).toHaveText([
      'ECB euro area AAA spot · 2026-10-15',
      'US Treasury par · 2026-10-16',
    ])
    await waitForKeyFigures(page)
    await expect(page.getByRole('note')).toContainText('These curves are not directly comparable')
    await expect(page.getByRole('note')).toContainText('rate types differ (par, spot) and compounding differs (semi-annual, continuous)')
    await expect(page.getByText('No value on ECB euro area AAA spot · 2026-10-15: 1M.')).toBeVisible()
    await expect(page.getByText('No value on US Treasury par · 2026-10-16: 15Y.')).toBeVisible()
    const overlayTable = page.getByRole('table', { name: /^Overlaid curves:/ })
    await expect(overlayTable.getByRole('rowheader')).toHaveText(['US Treasury par · 2026-10-16', 'ECB euro area AAA spot · 2026-10-15'])
    await expect(overlayTable.getByText('No value')).toHaveCount(2)
    await expect(
      page.getByRole('listitem').filter({ hasText: 'Source: ECB statistics (ECB euro area AAA spot)' }),
    ).toBeVisible()
    await expect(
      page.getByRole('listitem').filter({ hasText: 'Source: U.S. Department of the Treasury (US Treasury par)' }),
    ).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await pills.getByRole('button', { name: 'Remove ECB euro area AAA spot · 2026-10-15 from overlay' }).click()
    await expect(pills.getByRole('listitem')).toHaveCount(1)
    await expect(pills.getByRole('button', { name: 'Remove US Treasury par · 2026-10-16 from overlay' })).toBeFocused()
    await expect(page.getByRole('note')).toHaveCount(0)
    await expect(page.getByText(/^No value on /)).toHaveCount(0)
    await expect(page.getByRole('table', { name: /^Overlaid curves:/ }).getByRole('rowheader')).toHaveCount(1)
  })

  test('S3d overlay full: five entries and the disabled add button', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    const add = page.getByRole('button', { name: 'Add to overlay' })
    for (const date of ['2026-10-15', '2026-10-14', '2026-10-01', '2026-09-30', '2026-09-29']) {
      await page.getByLabel(/Valid date/).fill(date)
      await add.click()
    }
    await page.getByLabel(/Valid date/).fill('2026-09-28')
    await expect(add).toBeDisabled()
    await expect(add).toHaveAccessibleDescription('The overlay holds 5 curves. Remove one to add another.')
    await waitForKeyFigures(page)
    await assertAxeAt(page, ['light', 'dark'])
  })

  test('S4 history drawer 10Y simulated', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim')
    await waitForCurveLoaded(page)
    const drawerHeading = page.getByRole('heading', { name: 'History of 10Y on 2026-10-16' })
    const drawer = page.getByRole('dialog')
    for (const scheme of ['light', 'dark'] as const) {
      await page.setViewportSize(AXE_VIEWPORT)
      await setColorScheme(page, scheme)
      await settleAnimations(page)
      await page.getByRole('button', { name: 'History 10Y' }).click()
      await expect(drawerHeading).toBeVisible()
      await settleAnimations(page)
      // The drawer fades in on a timer, so wait for full opacity before axe samples colours.
      await expectOpaque(drawer)
      await runAxe(page)
      await page.keyboard.press('Escape')
      await expect(drawer).toBeHidden()
    }
    await setColorScheme(page, 'light')
    await page.getByRole('button', { name: 'History 10Y' }).click()
    await expect(drawerHeading).toBeVisible()
    await settleAnimations(page)
    await expectOpaque(drawer)
    await checkLayout(page, ['light'])
  })

  test('S5 time series chart', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    // Inactive views stay in the DOM with their own skeletons, so count only this panel's.
    await expect(page.getByRole('tabpanel', { name: 'Time series' }).locator('.mantine-Skeleton-root')).toHaveCount(0)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S5t time series table', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    await expect(page.getByRole('heading', { level: 1, name: 'Time series' })).toBeVisible()
    await page.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
    await expect(page.getByRole('columnheader', { name: 'Valid date' })).toBeVisible()
    await expect(page.getByText('Unchecked means the quality checks have not run on the value yet.')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S17 time series table, simulated, flagged', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    const panel = page.getByRole('tabpanel', { name: 'Time series' })
    await expect(panel.locator('.mantine-Skeleton-root')).toHaveCount(0)
    await expect(panel.getByText('Flagged: 1 value. Choose Table to see why.')).toBeVisible()
    await panel.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
    await expect(panel.getByRole('columnheader', { name: 'Quality' })).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Range · warn, 10Y' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S33 time series measure empty', async ({ page }) => {
    await routeMeasures(
      page,
      200,
      measuresBody(
        'ecb-aaa-spot',
        {
          ...measuresGrid,
          point: {
            ...measuresGrid.point,
            spread_2y_10y: null,
            inverted: null,
            inputs: [],
            missing: ['2Y', '10Y'],
          },
        },
        '2025-10-19',
      ),
    )
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    const panel = page.getByRole('tabpanel', { name: 'Time series' })
    await page.getByLabel('Series', { exact: true }).selectOption({ label: '2Y–10Y spread' })
    await expect(panel.getByText('No values in this range')).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Show 10Y yield' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S30 time series spread chart', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    const panel = page.getByRole('tabpanel', { name: 'Time series' })
    await page.getByLabel('Series', { exact: true }).selectOption({ label: '2Y–10Y spread' })
    await expect(panel.getByText('Inverted on 3 of 7 days')).toBeVisible()
    await expect(panel.locator('.recharts-wrapper')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S31 time series spread table', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    const panel = page.getByRole('tabpanel', { name: 'Time series' })
    await page.getByLabel('Series', { exact: true }).selectOption({ label: '2Y–10Y spread' })
    await panel.locator('.mantine-SegmentedControl-label').filter({ hasText: 'Table' }).click()
    await expect(panel.getByRole('cell', { name: '−12.4', exact: true })).toBeVisible()
    await expect(panel.getByText('No 2Y value')).toBeVisible()
    await expect(panel.getByText('Input flagged: 10Y')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S32 time series curvature chart', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Time series' }).click()
    const panel = page.getByRole('tabpanel', { name: 'Time series' })
    await page.getByLabel('Series', { exact: true }).selectOption({ label: '2Y–5Y–10Y curvature' })
    await expect(panel.getByRole('heading', { name: '2Y–5Y–10Y curvature (bp)' })).toBeVisible()
    await expect(panel.getByText(/^Inverted on/)).toHaveCount(0)
    await expect(panel.locator('.recharts-wrapper')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S6 changes with three rows', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Changes' }).click()
    await page.getByLabel('Compare from (known as of)').fill('2026-10-17T08:00')
    await expect(page.getByRole('cell', { name: 'correction' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S7 changes empty state', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByRole('tab', { name: 'Changes' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Pick a starting point' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S8 offline', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'offline')
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('Backend offline')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S9 loading', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'loading')
    await page.goto('/')
    await expect(page.getByText('Loading…')).toBeAttached()
    await expect(page.locator('.mantine-Skeleton-root')).toHaveCount(1)
    await expect(page.locator('.mantine-Loader-root')).toHaveCount(0)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S10 no data 404', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'not-found')
    await page.goto('/')
    await expect(page.getByRole('status').getByText('No data for this date')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Show latest date' })).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S11 data quality view', async ({ page }) => {
    await openQuality(page)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S12 quality flag popover', async ({ page }) => {
    await openQuality(page)
    await checkFlagPopover(page, 'Jump · warn, 10Y')
  })

  test('S16 curve flag popover', async ({ page }) => {
    await page.goto('/?curve=ecb-aaa-spot-sim&as_of=2026-10-19T18%3A49%3A25Z')
    await waitForCurveLoaded(page)
    await checkFlagPopover(page, 'Range · warn, 10Y')
  })

  test('S18 curve inverted', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await page.getByLabel(/Valid date/).fill('2026-10-13')
    await expect(page.getByLabel(/Valid date/)).toHaveValue('2026-10-13')
    await waitForKeyFigures(page)
    await expect(page.getByText('Inverted')).toBeVisible()
    await expect(page.getByText('\u221215.0 bp')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S19 curvature without 5Y', async ({ page }) => {
    const inputs = (measuresGrid.point.inputs as { maturity: string }[]).filter((input) => input.maturity !== '5Y')
    await page.route('**/v1/curves/*/observations**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          curveBody('ecb-aaa-spot', {
            ...curveGrid,
            points: curveGrid.points.map((point) => (point.maturity === '5Y' ? { ...point, value: null } : point)),
          }),
        ),
      }),
    )
    await routeMeasures(
      page,
      200,
      measuresBody(
        'ecb-aaa-spot',
        {
          ...measuresGrid,
          point: {
            ...measuresGrid.point,
            curvature_2y_5y_10y: null,
            missing: ['5Y'],
            inputs,
          },
        },
        '2026-10-16',
      ),
    )
    await page.goto('/')
    await waitForCurveLoaded(page)
    await expect(page.getByText('No 5Y value')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S20 measures unavailable', async ({ page }) => {
    await routeMeasures(page, 503, { detail: 'The measures service is not reachable; try again later.' })
    await page.goto('/')
    await waitForCurveLoaded(page)
    await expect(page.getByText('Not available')).toHaveCount(3)
    await expect(page.getByRole('heading', { name: 'Values' })).toBeVisible()
    await expect(page.getByRole('alert')).toHaveCount(0)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('Values History link keeps blue.9 with contrast on a hovered row (light)', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    await setColorScheme(page, 'light')
    const history = page.getByRole('button', { name: /^History / }).first()
    const row = history.locator('xpath=ancestor::tr')
    await row.hover()
    const measured = await history.evaluate((button) => {
      const parse = (css: string) => css.match(/[\d.]+/g)!.slice(0, 3).map(Number)
      const luminance = ([r, g, b]: number[]) => {
        const [R, G, B] = [r, g, b].map((c) => {
          const v = c / 255
          return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
        })
        return 0.2126 * R + 0.7152 * G + 0.0722 * B
      }
      const text = parse(getComputedStyle(button).color)
      const bg = parse(getComputedStyle(button.closest('tr')!).backgroundColor)
      const [hi, lo] = [luminance(text), luminance(bg)].sort((a, b) => b - a)
      return { text, bg, ratio: (hi + 0.05) / (lo + 0.05) }
    })
    expect(measured.text).toEqual([24, 100, 171]) // blue.9 #1864ab (T4)
    expect(measured.ratio).toBeGreaterThanOrEqual(4.5)
  })

  test('S21 key figure tooltip from keyboard', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    const add = page.getByRole('button', { name: 'Add to overlay' })
    const about = page.getByRole('button', { name: 'About 2Y–10Y spread' })
    const tooltip = page.getByRole('tooltip')
    for (const { width, height } of VIEWPORTS) {
      for (const scheme of ['light', 'dark'] as const) {
        await page.setViewportSize({ width, height })
        await setColorScheme(page, scheme)
        await add.focus()
        await expect(add).toBeFocused()
        await page.keyboard.press('Tab')
        await page.keyboard.press('Tab')
        await expect(about).toBeFocused()
        // Wait for the new tooltip by its text, then for it to be the only one: a closing tooltip can linger.
        await expect(page.getByRole('tooltip', { name: /Also called the slope/ })).toBeVisible()
        await expect(tooltip).toHaveCount(1)
        await settleAnimations(page)
        await expectOpaque(tooltip)
        if (width === AXE_VIEWPORT.width) {
          await runAxe(page)
        }
        await page.keyboard.press('Escape')
        await expect(tooltip).toHaveCount(0)
      }
    }
  })

  test('S13 quality no business days', async ({ page }) => {
    await routeQuality(page, 200, {
      data: { curve_id: 'ecb-aaa-spot', valid_from: '2026-09-19', valid_to: '2026-10-19', days: [] },
      meta: QUALITY_META,
    })
    await openQualityTab(page)
    await expect(page.getByText('No business days in this range')).toBeVisible()
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S14 quality loading', async ({ page }) => {
    await page.route('**/v1/curves/*/quality**', () => {})
    await openQualityTab(page)
    const panel = page.getByRole('tabpanel', { name: 'Quality' })
    await expect(panel.getByText('Loading…')).toBeAttached()
    await expect(panel.locator('.mantine-Skeleton-root')).toHaveCount(5)
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S15 quality backend offline', async ({ page }) => {
    await routeQuality(page, 503, { detail: 'The quality service is not reachable; try again later.' })
    await openQualityTab(page)
    await expect(page.getByRole('alert')).toContainText('Backend offline')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S25 curve select open', async ({ page }) => {
    await page.goto('/')
    await waitForCurveLoaded(page)
    const select = page.getByRole('combobox', { name: 'Curve' })
    const listbox = page.getByRole('listbox')
    for (const { width, height } of VIEWPORTS) {
      for (const scheme of ['light', 'dark'] as const) {
        await page.setViewportSize({ width, height })
        await setColorScheme(page, scheme)
        await select.click()
        await expect(listbox).toBeVisible()
        await settleAnimations(page)
        await expectOpaque(listbox)
        await page.mouse.move(0, 0)
        if (width === AXE_VIEWPORT.width) {
          await runAxe(page)
        }
        await expect(listbox.getByRole('option')).toHaveText([
          'ECB euro area AAA spot',
          'ECB euro area all-issuer spot',
          'ECB euro area AAA spot (scenario data)',
        ])
        await expect(listbox.getByText('Published')).toBeVisible()
        await expect(listbox.getByText('Simulated')).toBeVisible()
        await page.keyboard.press('Escape')
        await expect(listbox).toBeHidden()
      }
    }
  })

  test('S28 curve list error', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'catalogue-error')
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: 'Curves unavailable' })).toBeVisible()
    await expect(page.getByRole('alert')).toContainText('Curve list not loaded')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S29 curve list empty', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'catalogue-empty')
    await page.goto('/')
    await expect(page.getByRole('status')).toContainText('No curves yet')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })

  test('S26 all-issuer curve', async ({ page }) => {
    await page.goto('/?curve=ecb-all-spot')
    await waitForCurveLoaded(page)
    await expect(page.getByText('ECB euro area all-issuer spot · spot rates, continuous compounding')).toBeVisible()
    await expect(page.getByRole('contentinfo')).toContainText('Source: ECB statistics, ECB euro area all-issuer spot.')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light', 'dark'])
  })

  test('S27 par curve', async ({ page }) => {
    await page.unroute('http://localhost:8000/**')
    await installApiMocks(page, 'par')
    await page.goto('/?curve=ust-par')
    await waitForCurveLoaded(page)
    await expect(page.getByRole('heading', { name: 'Par curve (%)' })).toBeVisible()
    await expect(page.getByText('US Treasury par · par rates, semi-annual compounding')).toBeVisible()
    await expect(page.getByRole('contentinfo')).toContainText('Source: U.S. Department of the Treasury, US Treasury par.')
    await assertAxeAt(page, ['light', 'dark'])
    await checkLayout(page, ['light'])
  })
})

test.describe('curve catalogue', () => {
  test('unknown curve falls back to the default and rewrites the URL', async ({ page }) => {
    await page.goto('/?curve=nope')
    await waitForCurveLoaded(page)
    await expect(page).toHaveURL(/[?&]curve=ecb-aaa-spot(&|$)/)
    await expect(page.getByRole('combobox', { name: 'Curve' })).toHaveValue('ECB euro area AAA spot')
    await expect(page.getByRole('note')).toHaveCount(0)
  })

  test('without the default curve, falls back to the first published curve', async ({ page }) => {
    const curves = catalogue.data.filter((curve) => curve.curve_id !== 'ecb-aaa-spot')
    await page.route('**/v1/curves', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: curves }) }),
    )
    await page.goto('/?curve=nope')
    await waitForCurveLoaded(page)
    await expect(page).toHaveURL(/[?&]curve=ecb-all-spot(&|$)/)
    await expect(page.getByRole('note')).toHaveCount(0)
    await expect(page.locator('.mantine-Badge-label', { hasText: 'Simulated' })).toHaveCount(0)
  })

  test('shows the connecting page while the curve list loads', async ({ page }) => {
    await page.route('**/v1/curves', () => {})
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1, name: 'Connecting' })).toBeVisible()
    await expect(page.getByText('Loading…')).toBeAttached()
    await expect(page.locator('.mantine-Skeleton-root')).toHaveCount(1)
  })

  test('header fits at 1280 with the longest label', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/?curve=ecb-aaa-spot-sim')
    await waitForCurveLoaded(page)
    await assertNoHorizontalScroll(page)
    const controls = [
      page.getByRole('tablist'),
      page.getByRole('combobox', { name: 'Curve' }),
      page.getByRole('button', { name: 'Toggle colour scheme' }),
    ]
    for (const control of controls) {
      const box = await control.boundingBox()
      expect(box).not.toBeNull()
      expect(box!.y).toBeGreaterThanOrEqual(0)
      expect(box!.y + box!.height).toBeLessThanOrEqual(56)
    }
  })
})

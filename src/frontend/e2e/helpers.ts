import AxeBuilder from '@axe-core/playwright'
import { expect, type Locator, type Page } from '@playwright/test'

export const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
] as const

export async function runAxe(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
    .analyze()
  expect(results.violations).toEqual([])
}

export async function assertNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.innerWidth)
}

export async function setColorScheme(page: Page, scheme: 'light' | 'dark') {
  const current = await page.evaluate(() =>
    document.documentElement.getAttribute('data-mantine-color-scheme'),
  )
  if (current === scheme) return
  await page.getByRole('button', { name: 'Toggle colour scheme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-mantine-color-scheme', scheme)
  await page.mouse.move(0, 0)
}

export async function waitForCurveLoaded(page: Page) {
  await expect(page.getByRole('heading', { level: 1, name: 'Yield curve' })).toBeVisible()
  await expect(page.getByLabel(/Valid date/)).toHaveValue('2026-10-16', { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Add to overlay' })).toBeEnabled({ timeout: 15_000 })
}

/** Inner padding of a chart card (design T2/L2): chart content keeps at least this many px from the border. */
const MIN_CARD_INSET_PX = 16

/**
 * Fails when the chart surface, a tick label, a dot or the card title sits closer than MIN_CARD_INSET_PX
 * to the card's border box on any side (main's ~1 px flush layout fails, Card padding "lg" passes).
 */
export async function expectChartsInsideCards(page: Page) {
  const tooClose = await page.evaluate((minInset) =>
    Array.from(document.querySelectorAll('.recharts-wrapper')).flatMap((chart) => {
      const cardEl = chart.closest('.mantine-Card-root')
      const card = cardEl?.getBoundingClientRect()
      if (!cardEl || !card || card.width === 0) return []
      const content = [
        chart.querySelector('svg'),
        ...chart.querySelectorAll('.recharts-cartesian-axis-tick-value, .recharts-dot'),
        cardEl.querySelector('h2'),
      ]
      return content
        .filter((el): el is Element => el !== null)
        .map((el) => ({ label: el.textContent?.trim() || el.tagName, r: el.getBoundingClientRect() }))
        .map(({ label, r }) => ({
          label,
          inset: Math.min(r.left - card.left, card.right - r.right, r.top - card.top, card.bottom - r.bottom),
        }))
        .filter(({ inset }) => inset < minInset)
        .map(({ label, inset }) => `${label}: ${inset.toFixed(1)} px`)
    }),
  MIN_CARD_INSET_PX)
  expect(tooClose).toEqual([])
}

export function screenshotName(id: string, width: number, height: number, scheme: 'light' | 'dark') {
  return `${id}-${width}x${height}-${scheme}.png`
}

/** Waits for finite CSS transitions and animations, so axe samples settled colours. */
export async function settleAnimations(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((a) => a.effect?.getTiming().iterations !== Infinity)
        .map((a) => a.finished.catch(() => undefined)),
    ),
  )
}

/**
 * Waits until the element and its ancestors are fully opaque. Mantine starts its fade-in with a
 * timer, so a freshly opened popover can have no running animation yet when settleAnimations runs.
 */
export async function expectOpaque(locator: Locator) {
  await expect
    .poll(() =>
      locator.evaluate((el) => {
        let opacity = 1
        for (let node: Element | null = el; node; node = node.parentElement) {
          opacity *= Number(getComputedStyle(node).opacity)
        }
        return opacity
      }),
    )
    .toBe(1)
}

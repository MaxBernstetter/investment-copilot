import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Page, Route } from '@playwright/test'

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), 'fixtures')
const ACCESS_URL = 'http://localhost:8000'

export type MockMode = 'online' | 'offline' | 'loading' | 'not-found'

type CurveFixture = {
  meta: { as_of: string; source_attribution: string }
  valid_date?: string
  points: {
    maturity: string
    months: number
    value: number | null
    origin: string
    quality?: { status: string; flags: unknown[] } | null
  }[]
}

function loadJson<T>(name: string): T {
  return JSON.parse(readFileSync(join(FIXTURES, name), 'utf8')) as T
}

const curveGrid = loadJson<CurveFixture>('curve-grid.json')
const curveOverlay15 = loadJson<CurveFixture>('curve-overlay-2026-10-15.json')
const curveOverlay14 = loadJson<CurveFixture>('curve-overlay-2026-10-14.json')
const curveSimSpike = loadJson<CurveFixture>('curve-sim-spike.json')
type SeriesFixture = {
  meta: { as_of: string; source_attribution: string }
  points: { valid_date: string; value: number; quality?: { status: string; flags: unknown[] } }[]
}
const series10y = loadJson<SeriesFixture>('series-10y.json')
const series10ySimSpike = loadJson<SeriesFixture>('series-10y-sim-spike.json')
const changesThree = loadJson<{
  meta: { since: string; as_of: string; source_attribution: string }
  changes: unknown[]
}>('changes-three.json')
const qualityMixed = loadJson<{
  meta: { as_of: string; source_attribution: string }
  days: unknown[]
}>('quality-mixed.json')
const versionsSim = loadJson<{
  meta: { as_of: string; source_attribution: string }
  versions: unknown[]
}>('versions-sim-correction.json')

function curveBody(curveId: string, fixture: CurveFixture, validDate?: string) {
  const valid_date = validDate ?? fixture.valid_date ?? '2026-10-16'
  return {
    data: {
      curve_id: curveId,
      valid_date,
      points: fixture.points.map((point) => ({
        ...point,
        version_id: point.value === null ? null : 1,
        quality: point.quality ?? (point.value === null ? null : { status: 'passed', flags: [] }),
      })),
    },
    meta: fixture.meta,
  }
}

function fulfillJson(route: Route, status: number, body: unknown) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

export async function installApiMocks(page: Page, mode: MockMode = 'online') {
  await page.route(`${ACCESS_URL}/**`, async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    if (path === '/health') {
      if (mode === 'offline') {
        await fulfillJson(route, 503, { detail: 'unavailable' })
        return
      }
      if (mode === 'loading') {
        return
      }
      await fulfillJson(route, 200, { status: 'ok' })
      return
    }

    if (mode === 'offline') {
      await route.abort('failed')
      return
    }

    if (
      mode === 'loading' &&
      path.match(/^\/v1\/curves\/[^/]+\/observations$/) &&
      !path.includes('/maturities')
    ) {
      return
    }

    if (path.match(/^\/v1\/curves\/[^/]+\/observations$/) && !path.includes('/maturities')) {
      const curveId = path.split('/')[3]
      const validDate = url.searchParams.get('valid_date')
      const asOf = url.searchParams.get('as_of')

      if (mode === 'not-found') {
        await fulfillJson(route, 404, { detail: 'No data known for this date.' })
        return
      }

      if (curveId === 'ecb-aaa-spot-sim' && asOf === '2026-10-19T18:49:25Z') {
        await fulfillJson(route, 200, curveBody(curveId, curveSimSpike))
        return
      }

      if (validDate === '2026-10-15') {
        await fulfillJson(route, 200, curveBody(curveId, curveOverlay15, '2026-10-15'))
        return
      }
      if (validDate === '2026-10-14') {
        await fulfillJson(route, 200, curveBody(curveId, curveOverlay14, '2026-10-14'))
        return
      }

      await fulfillJson(route, 200, curveBody(curveId, curveGrid))
      return
    }

    if (path.match(/^\/v1\/curves\/[^/]+\/maturities\/[^/]+\/observations$/) && !path.includes('/versions')) {
      const curveId = path.split('/')[3]
      const maturity = path.split('/')[5]
      if (mode === 'not-found') {
        await fulfillJson(route, 404, { detail: 'No data known for this maturity.' })
        return
      }
      const fixture = curveId === 'ecb-aaa-spot-sim' ? series10ySimSpike : series10y
      await fulfillJson(route, 200, {
        data: {
          curve_id: curveId,
          maturity,
          valid_from: url.searchParams.get('from') ?? '2025-10-19',
          valid_to: url.searchParams.get('to') ?? '2026-10-19',
          points: fixture.points.map((p) => ({
            ...p,
            version_id: 1,
            origin: 'published',
            quality: p.quality ?? { status: 'passed', flags: [] },
          })),
        },
        meta: fixture.meta,
      })
      return
    }

    if (path.includes('/versions')) {
      const parts = path.split('/')
      const curveId = parts[3]
      const maturity = parts[5]
      const validDate = parts[7]
      await fulfillJson(route, 200, {
        data: {
          curve_id: curveId,
          maturity,
          valid_date: validDate,
          versions: versionsSim.versions,
        },
        meta: versionsSim.meta,
      })
      return
    }

    if (path.match(/^\/v1\/curves\/[^/]+\/changes$/)) {
      const curveId = path.split('/')[3]
      await fulfillJson(route, 200, {
        data: {
          curve_id: curveId,
          valid_from: url.searchParams.get('from') ?? '2025-10-19',
          valid_to: url.searchParams.get('to') ?? '2026-10-19',
          changes: changesThree.changes,
        },
        meta: changesThree.meta,
      })
      return
    }

    if (path.match(/^\/v1\/curves\/[^/]+\/quality$/)) {
      const curveId = path.split('/')[3]
      await fulfillJson(route, 200, {
        data: {
          curve_id: curveId,
          valid_from: url.searchParams.get('from') ?? '2025-10-19',
          valid_to: url.searchParams.get('to') ?? '2026-10-19',
          days: qualityMixed.days,
        },
        meta: qualityMixed.meta,
      })
      return
    }

    await fulfillJson(route, 404, { detail: `Unhandled mock path: ${path}` })
  })
}

export const FIXED_TIME = '2026-10-19T12:00:00Z'

export async function freezeClock(page: Page) {
  await page.addInitScript((iso: string) => {
    const fixed = new Date(iso).getTime()
    const RealDate = Date
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(globalThis as any).Date = class extends RealDate {
      constructor(...args: [] | [string | number | Date] | [number, number, number, number, number, number, number]) {
        if (args.length === 0) {
          super(fixed)
          return
        }
        super(...(args as ConstructorParameters<typeof Date>))
      }
      static now() {
        return fixed
      }
    }
  }, FIXED_TIME)
}

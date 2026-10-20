import { describe, expect, it } from 'vitest'
import type { components } from '../api/schema'
import {
  defaultQualityRange,
  filterDays,
  flagAriaLabel,
  flagLabel,
  newestFirst,
  qualityStats,
  rangeError,
  sortFindings,
  uncheckedRuleLabels,
  type QualityDay,
  type QualityFinding,
} from './qualityData'

type Rule = components['schemas']['Rule']

function finding(
  rule: Rule,
  severity: 'warn' | 'info',
  maturity: string | null = null,
): QualityFinding {
  return { rule, severity, maturity, explanation: 'why', evidence: 'what' }
}

function day(
  valid_date: string,
  status: QualityDay['status'],
  overrides: Partial<QualityDay> = {},
): QualityDay {
  return { valid_date, status, findings: [], rules: [], checked_as_of: null, ...overrides }
}

const days: QualityDay[] = [
  day('2026-10-14', 'passed', { checked_as_of: '2026-10-14T18:00:00Z' }),
  day('2026-10-15', 'warn', {
    checked_as_of: '2026-10-15T18:00:00Z',
    findings: [finding('range', 'warn', '10Y'), finding('jump', 'info', '2Y')],
  }),
  day('2026-10-16', 'info', {
    checked_as_of: '2026-10-16T09:00:00Z',
    findings: [finding('jump', 'info', '5Y')],
  }),
  day('2026-10-17', 'unchecked'),
]

describe('qualityStats', () => {
  it('counts checked days, findings and the days they occur on', () => {
    expect(qualityStats(days)).toEqual({
      checked: 3,
      total: 4,
      warnings: 1,
      warnDays: 1,
      infos: 2,
      infoDays: 2,
      lastCheck: '2026-10-16T09:00:00Z',
    })
  })

  it('last check is the latest checked_as_of, undefined when none', () => {
    expect(qualityStats([day('2026-10-17', 'unchecked')]).lastCheck).toBeUndefined()
    expect(
      qualityStats([
        day('2026-10-14', 'passed', { checked_as_of: '2026-10-14T23:00:00+02:00' }),
        day('2026-10-15', 'passed', { checked_as_of: '2026-10-15T10:00:00Z' }),
      ]).lastCheck,
    ).toBe('2026-10-15T10:00:00Z')
  })
})

describe('newestFirst', () => {
  it('newestFirst reverses API order', () => {
    expect(newestFirst(days).map((d) => d.valid_date)).toEqual([
      '2026-10-17',
      '2026-10-16',
      '2026-10-15',
      '2026-10-14',
    ])
  })
})

describe('filterDays', () => {
  it('filterDays keeps all or the matching status', () => {
    expect(filterDays(days, 'all')).toHaveLength(4)
    expect(filterDays(days, 'warn').map((d) => d.valid_date)).toEqual(['2026-10-15'])
    expect(filterDays(days, 'unchecked').map((d) => d.valid_date)).toEqual(['2026-10-17'])
  })
})

describe('sortFindings', () => {
  it('sortFindings puts warn first, then date-level, then grid order', () => {
    const sorted = sortFindings([
      finding('jump', 'info', '3M'),
      finding('range', 'warn', '30Y'),
      finding('missing-maturity', 'info', 'XX'),
      finding('missing-date', 'info'),
      finding('range', 'warn', '1Y'),
      finding('jump', 'info', '10Y'),
    ])
    expect(sorted.map((f) => [f.severity, f.maturity ?? null])).toEqual([
      ['warn', '1Y'],
      ['warn', '30Y'],
      ['info', null],
      ['info', '3M'],
      ['info', '10Y'],
      ['info', 'XX'],
    ])
  })
})

describe('uncheckedRuleLabels', () => {
  it('uncheckedRuleLabels lists partial checks only', () => {
    expect(
      uncheckedRuleLabels(
        day('2026-10-15', 'passed', {
          rules: [
            { rule: 'range', outcome: 'passed', finding_count: 0 },
            { rule: 'missing-date', outcome: 'unchecked', finding_count: 0 },
            { rule: 'jump', outcome: 'unchecked', finding_count: 0 },
          ],
        }),
      ),
    ).toEqual(['Missing date', 'Jump'])
    expect(
      uncheckedRuleLabels(
        day('2026-10-17', 'unchecked', {
          rules: [{ rule: 'range', outcome: 'unchecked', finding_count: 0 }],
        }),
      ),
    ).toEqual([])
  })
})

describe('flag labels', () => {
  it('flag labels include maturity in aria-label', () => {
    const withMaturity = finding('range', 'warn', '10Y')
    expect(flagLabel(withMaturity)).toBe('Range · warn')
    expect(flagAriaLabel(withMaturity)).toBe('Range · warn, 10Y')
    expect(flagAriaLabel(finding('missing-date', 'warn'))).toBeUndefined()
  })
})

describe('defaultQualityRange', () => {
  it('defaultQualityRange spans 30 days to today UTC', () => {
    expect(defaultQualityRange(new Date('2026-10-19T12:00:00Z'))).toEqual({
      from: '2026-09-19',
      to: '2026-10-19',
    })
  })
})

describe('rangeError', () => {
  it('rangeError accepts 366 days, rejects 367 and to < from', () => {
    expect(rangeError({ from: '2025-10-19', to: '2026-10-20' })).toBeUndefined()
    expect(rangeError({ from: '2025-10-19', to: '2026-10-21' })).toBe(
      'Choose a range of at most 366 days.',
    )
    expect(rangeError({ from: '2026-10-19', to: '2026-10-18' })).toBe(
      'To must be on or after From.',
    )
  })
})

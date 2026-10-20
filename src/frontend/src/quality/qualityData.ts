import type { components } from '../api/schema'
import { MATURITIES } from '../series/seriesData'

export type QualityDay = components['schemas']['QualityDay']
export type QualityFinding = components['schemas']['QualityFinding']
export type QualityStatus = components['schemas']['QualityStatus']
export type Rule = components['schemas']['Rule']
export type Severity = components['schemas']['Severity']

export const RULE_LABEL: Record<Rule, string> = {
  range: 'Range',
  jump: 'Jump',
  'missing-date': 'Missing date',
  'missing-maturity': 'Missing maturity',
}

export const STATUS_LABEL: Record<QualityStatus, string> = {
  passed: 'Passed',
  info: 'Info',
  warn: 'Warn',
  unchecked: 'Unchecked',
}

export type DayFilter = 'all' | 'warn' | 'info' | 'unchecked'

export type QualityStats = {
  checked: number
  total: number
  warnings: number
  warnDays: number
  infos: number
  infoDays: number
  lastCheck: string | undefined
}

const DAY_MS = 24 * 60 * 60 * 1000

export function qualityStats(days: QualityDay[]): QualityStats {
  let checked = 0
  let warnings = 0
  let warnDays = 0
  let infos = 0
  let infoDays = 0
  let lastCheck: string | undefined
  let lastCheckMs = Number.NEGATIVE_INFINITY

  for (const day of days) {
    if (day.status !== 'unchecked') checked += 1
    const dayWarnings = day.findings.filter((f) => f.severity === 'warn').length
    const dayInfos = day.findings.filter((f) => f.severity === 'info').length
    warnings += dayWarnings
    infos += dayInfos
    if (dayWarnings > 0) warnDays += 1
    if (dayInfos > 0) infoDays += 1
    if (day.checked_as_of) {
      const ms = Date.parse(day.checked_as_of)
      if (!Number.isNaN(ms) && ms > lastCheckMs) {
        lastCheckMs = ms
        lastCheck = day.checked_as_of
      }
    }
  }

  return { checked, total: days.length, warnings, warnDays, infos, infoDays, lastCheck }
}

/** The API returns days in valid-date order; the UI shows the newest first. */
export function newestFirst(days: QualityDay[]): QualityDay[] {
  return [...days].reverse()
}

export function filterDays(days: QualityDay[], filter: DayFilter): QualityDay[] {
  if (filter === 'all') return days
  return days.filter((day) => day.status === filter)
}

const SEVERITY_RANK: Record<Severity, number> = { warn: 0, info: 1 }

function maturityRank(maturity: string | null | undefined): number {
  if (maturity === null || maturity === undefined) return -1
  const index = (MATURITIES as readonly string[]).indexOf(maturity)
  return index === -1 ? Number.POSITIVE_INFINITY : index
}

/** Warnings before info; then date-level findings, then the grid order; unknown maturities last. */
export function sortFindings(findings: QualityFinding[]): QualityFinding[] {
  return [...findings].sort((a, b) => {
    const bySeverity = SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
    if (bySeverity !== 0) return bySeverity
    const aRank = maturityRank(a.maturity)
    const bRank = maturityRank(b.maturity)
    if (aRank === bRank) return 0
    return aRank < bRank ? -1 : 1
  })
}

/** Labels of the rules that could not run on a partly checked day. */
export function uncheckedRuleLabels(day: QualityDay): string[] {
  if (day.status === 'unchecked') return []
  return day.rules.filter((rule) => rule.outcome === 'unchecked').map((rule) => RULE_LABEL[rule.rule])
}

export function flagLabel(finding: QualityFinding): string {
  return `${RULE_LABEL[finding.rule]} · ${finding.severity}`
}

export function flagAriaLabel(finding: QualityFinding): string | undefined {
  if (!finding.maturity) return undefined
  return `${flagLabel(finding)}, ${finding.maturity}`
}

function isoDate(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

/** The 30 days up to today (UTC), as valid dates. */
export function defaultQualityRange(today: Date): { from: string; to: string } {
  return {
    from: isoDate(today.getTime() - 30 * DAY_MS),
    to: isoDate(today.getTime()),
  }
}

export function rangeError({ from, to }: { from: string; to: string }): string | undefined {
  const span = (Date.parse(to) - Date.parse(from)) / DAY_MS
  if (span < 0) return 'To must be on or after From.'
  if (span > 365) return 'Choose a range of at most 366 days.'
  return undefined
}

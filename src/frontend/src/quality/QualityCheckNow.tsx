import { useState } from 'react'
import { Alert, Button, Stack, Text } from '@mantine/core'
import { IconPlayerPlay } from '@tabler/icons-react'
import { fetchQualityCheck, type QualityCheckResult } from './fetchQualityCheck'

type QualityCheckNowProps = {
  curveId: string
  from: string
  to: string
  /** The range is invalid, or the views show a past knowledge time that a new check cannot change. */
  disabledReason?: string
  /** Called after a check finished so the view reads the new results. */
  onChecked: () => void
}

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * The last date a check covers: the chosen end, but not later than yesterday (UTC), because today's
 * values are published later and a check would flag today as missing. Never before the start.
 */
export function checkEnd(from: string, to: string, now: Date): string {
  const yesterday = new Date(now.getTime() - DAY_MS).toISOString().slice(0, 10)
  const end = to > yesterday ? yesterday : to
  return end < from ? from : end
}

type Check = {
  days: number
  values: number
  warn_count: number
  info_count: number
  checked_as_of?: string | null
}

/** Result line of a finished check over `from` to `to`. */
export function checkSummary(
  { days, values, warn_count, info_count, checked_as_of }: Check,
  from: string,
  to: string,
): string {
  if (checked_as_of === null || checked_as_of === undefined) {
    return 'Nothing to check: the curve has no published values yet.'
  }
  return `Checked ${from} to ${to}: ${days} business days and ${values} values, ${warn_count} warnings, ${info_count} info flags.`
}

/** The Check now button and the answer to it; the button is hidden once the deployment says no. */
export default function QualityCheckNow({ curveId, from, to, disabledReason, onChecked }: QualityCheckNowProps) {
  const [running, setRunning] = useState(false)
  const [answer, setAnswer] = useState<{ result: QualityCheckResult; from: string; to: string } | undefined>(
    undefined,
  )

  const start = async () => {
    setRunning(true)
    setAnswer(undefined)
    const end = checkEnd(from, to, new Date())
    const result = await fetchQualityCheck({ curveId, from, to: end })
    setAnswer({ result, from, to: end })
    setRunning(false)
    if (result.kind === 'ok') onChecked()
  }

  return (
    <Stack gap={4}>
      {answer?.result.kind !== 'disabled' && (
        <Button
          variant="light"
          leftSection={<IconPlayerPlay size={16} aria-hidden />}
          loading={running}
          disabled={disabledReason !== undefined}
          onClick={start}
        >
          Check now
        </Button>
      )}
      {disabledReason !== undefined && answer?.result.kind !== 'disabled' && (
        <Text size="xs" c="dimmed">
          {disabledReason}
        </Text>
      )}
      <AnswerNote answer={answer} />
    </Stack>
  )
}

function AnswerNote({ answer }: { answer: { result: QualityCheckResult; from: string; to: string } | undefined }) {
  if (answer === undefined) return null
  const { result } = answer
  if (result.kind === 'ok') {
    return (
      <Alert variant="light" color="green" role="status">
        {checkSummary(result.check, answer.from, answer.to)}
      </Alert>
    )
  }
  const detail =
    result.kind === 'offline'
      ? 'The YieldLens API is not reachable. Try again in a moment.'
      : result.detail
  const title = result.kind === 'disabled' ? 'Checks cannot be started here' : 'Could not run the check'
  return (
    <Alert color="red" role="alert" title={title}>
      {detail}
    </Alert>
  )
}

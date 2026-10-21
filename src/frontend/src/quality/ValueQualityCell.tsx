import { Badge, Group, VisuallyHidden } from '@mantine/core'
import { qualityBadgeProps } from '../theme'
import QualityFlag from './QualityFlag'
import { STATUS_LABEL, sortFindings, type ValueQuality } from './qualityData'

type ValueQualityCellProps = { quality: ValueQuality | null; maturity: string }

/** Quality of one table value: a flag badge per flag, or a static status badge; nothing without a value. */
export default function ValueQualityCell({ quality, maturity }: ValueQualityCellProps) {
  if (quality === null) return null
  if (quality.status === 'passed') return <VisuallyHidden>{STATUS_LABEL.passed}</VisuallyHidden>
  if (quality.status === 'unchecked' || quality.flags.length === 0) {
    return <Badge {...qualityBadgeProps(quality.status)}>{STATUS_LABEL[quality.status]}</Badge>
  }
  const flags = sortFindings(quality.flags.map((flag) => ({ ...flag, maturity })))
  return (
    <Group gap={4} wrap="nowrap">
      {flags.map((flag, index) => (
        <QualityFlag key={`${flag.rule}-${index}`} finding={flag} />
      ))}
    </Group>
  )
}

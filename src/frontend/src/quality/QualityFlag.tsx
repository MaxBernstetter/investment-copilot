import { Anchor, Badge, Popover, Stack, Text } from '@mantine/core'
import { METHODOLOGY_URL } from '../config'
import { qualityBadgeProps } from '../theme'
import { RULE_LABEL, flagAriaLabel, flagLabel, type QualityFinding } from './qualityData'

export default function QualityFlag({ finding }: { finding: QualityFinding }) {
  const ruleTitle = finding.maturity
    ? `${RULE_LABEL[finding.rule]} at ${finding.maturity}`
    : RULE_LABEL[finding.rule]

  return (
    <Popover width={320} withArrow position="bottom-start" trapFocus returnFocus>
      <Popover.Target>
        <Badge
          component="button"
          type="button"
          {...qualityBadgeProps(finding.severity)}
          aria-label={flagAriaLabel(finding)}
        >
          {flagLabel(finding)}
        </Badge>
      </Popover.Target>
      <Popover.Dropdown>
        <Stack gap={4}>
          <Text fw={600}>{ruleTitle}</Text>
          <Text size="sm">{finding.explanation}</Text>
          <Text size="sm" c="dimmed">
            {finding.evidence}
          </Text>
          <Anchor size="sm" href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
            How we check this
          </Anchor>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}

import { Accordion, Anchor, Card, Stack, Text, Title } from '@mantine/core'
import { METHODOLOGY_URL } from '../config'
import { RULE_LABEL, type Rule } from './qualityData'

const HOW_WE_CHECK: Record<Rule, string> = {
  range:
    'A yield outside \u22122.00\u202f% to 8.00\u202f% is flagged as a warning. ECB AAA spot yields stayed between \u22121.00\u202f% and 5.18\u202f% since 2004.',
  jump: 'A move of more than 25 bp since the previous business day is flagged as info, more than 50 bp as a warning.',
  'missing-date':
    'A TARGET business day without any published value is flagged as a warning.',
  'missing-maturity':
    'A maturity without a value on a TARGET business day on which other maturities have one is flagged as a warning.',
}

const RULES = Object.keys(HOW_WE_CHECK) as Rule[]

export default function HowWeCheck() {
  return (
    <Card>
      <Stack gap="md">
        <Title order={2}>How we check</Title>
        <Accordion>
          {RULES.map((rule) => (
            <Accordion.Item key={rule} value={rule}>
              <Accordion.Control>{RULE_LABEL[rule]}</Accordion.Control>
              <Accordion.Panel>
                <Text size="sm">{HOW_WE_CHECK[rule]}</Text>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
        <Anchor size="sm" href={METHODOLOGY_URL} target="_blank" rel="noreferrer">
          Read the full method
        </Anchor>
      </Stack>
    </Card>
  )
}

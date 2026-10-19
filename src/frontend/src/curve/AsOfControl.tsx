import { Button, TextInput } from '@mantine/core'
import { localInputToUtc, utcToLocalInput } from '../asOf'

type AsOfControlProps = {
  asOf: string | undefined
  onChange: (asOf: string | undefined) => void
}

export default function AsOfControl({ asOf, onChange }: AsOfControlProps) {
  return (
    <>
      <TextInput
        type="datetime-local"
        step={1}
        label="Known as of"
        value={asOf ? utcToLocalInput(asOf) : ''}
        onChange={(event) =>
          onChange(event.currentTarget.value ? localInputToUtc(event.currentTarget.value) : undefined)
        }
      />
      <Button variant="default" onClick={() => onChange(undefined)}>
        Now
      </Button>
    </>
  )
}

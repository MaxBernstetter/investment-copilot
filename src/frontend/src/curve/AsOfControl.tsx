import { localInputToUtc, utcToLocalInput } from '../asOf'

type AsOfControlProps = {
  asOf: string | undefined
  onChange: (asOf: string | undefined) => void
}

export default function AsOfControl({ asOf, onChange }: AsOfControlProps) {
  return (
    <div>
      <label>
        Known as of{' '}
        <input
          type="datetime-local"
          step="1"
          value={asOf ? utcToLocalInput(asOf) : ''}
          onChange={(event) =>
            onChange(event.target.value ? localInputToUtc(event.target.value) : undefined)
          }
        />
      </label>{' '}
      <button type="button" onClick={() => onChange(undefined)}>
        Now
      </button>
    </div>
  )
}

import type { ReactNode } from 'react'
import { render as testingLibraryRender } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import { cssVariablesResolver, theme } from '../theme'

export function render(ui: ReactNode) {
  return testingLibraryRender(<>{ui}</>, {
    wrapper: ({ children }: { children: ReactNode }) => (
      <MantineProvider theme={theme} cssVariablesResolver={cssVariablesResolver} env="test">
        {children}
      </MantineProvider>
    ),
  })
}

export * from '@testing-library/react'

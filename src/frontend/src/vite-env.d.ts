/// <reference types="vite/client" />

declare const __APP_VERSION__: string

interface ImportMetaEnv {
  readonly VITE_ACCESS_URL?: string
  readonly VITE_COMMIT?: string
}

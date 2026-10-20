export const ACCESS_URL: string = import.meta.env.VITE_ACCESS_URL ?? 'http://localhost:8000'
/** The release version from package.json (set in vite.config.ts). */
export const APP_VERSION: string = __APP_VERSION__
/** The short git commit of the build (set by the frontend build task), `dev` when unknown. */
export const COMMIT: string = import.meta.env.VITE_COMMIT || 'dev'
export const REPOSITORY_URL = 'https://github.com/MaxBernstetter/yield-lens'
export const METHODOLOGY_URL =
  'https://github.com/MaxBernstetter/yield-lens/blob/main/docs/project/02-data-processing/01-plausibility-thresholds.md'

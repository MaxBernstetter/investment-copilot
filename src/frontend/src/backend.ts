import { ACCESS_URL } from './config'

export async function isBackendOnline(fetchFn: typeof fetch = fetch): Promise<boolean> {
  try {
    const response = await fetchFn(`${ACCESS_URL}/health`)
    return response.ok
  } catch {
    return false
  }
}

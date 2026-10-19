import createClient from 'openapi-fetch'
import { ACCESS_URL } from '../config'
import type { paths } from './schema'

export const api = createClient<paths>({ baseUrl: ACCESS_URL })

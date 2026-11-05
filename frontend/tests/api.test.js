import assert from 'node:assert/strict'
import test from 'node:test'
import { request } from '../src/services/api.js'

globalThis.sessionStorage ??= { getItem: () => null }
globalThis.localStorage ??= { getItem: () => null }

test('request converts network failures into a friendly message', async (t) => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch') }

  await assert.rejects(
    request('/auth/login', { timeoutMs: 100 }),
    { message: 'Unable to connect to PocketWise. Check your internet connection and try again.' },
  )
})

test('request reports timeout failures separately', async (t) => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = (_url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
  })

  await assert.rejects(
    request('/auth/register', { timeoutMs: 5 }),
    { message: 'This is taking longer than expected. Please try again.' },
  )
})

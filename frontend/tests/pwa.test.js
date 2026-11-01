import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const root = new URL('../', import.meta.url)
test('PWA manifest exposes install icons and service worker never caches private APIs', async () => {
  const manifest = JSON.parse(await readFile(new URL('public/manifest.webmanifest', root), 'utf8'))
  assert.equal(manifest.name, 'PocketWise - Student Finance')
  assert.deepEqual(manifest.icons.map(icon => icon.sizes), ['192x192', '512x512'])
  const worker = await readFile(new URL('public/sw.js', root), 'utf8')
  assert.match(worker, /url\.pathname\.startsWith\("\/api\/"\)/)
  assert.match(worker, /request\.headers\.has\("authorization"\)/)
  assert.match(worker, /offline\.html/)
})


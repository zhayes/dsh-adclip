/** Shape test for the first-run preflight and its persisted setup state.
 *
 * Windows and macOS share this code, so the assertions are platform neutral:
 * they check the contract the setup page depends on, not which binaries this
 * machine happens to have.
 *
 *   node tests/preflight.mjs
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { asrRemedy, preflight, readSetupState, writeSetupState } from '../plugin/host/preflight.js'

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const pluginRoot = path.join(repo, 'plugin')
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'adclip-preflight-'))

const STATUSES = new Set(['ok', 'warn', 'missing'])
const REQUIRED_IDS = ['sources', 'python', 'venv', 'ffmpeg', 'ffprobe', 'data', 'asr']

const result = await preflight({ dataDir, pluginRoot })

assert.equal(typeof result.ok, 'boolean')
assert.equal(typeof result.ready, 'boolean')
assert.ok(Array.isArray(result.blocking) && Array.isArray(result.pending))
assert.ok(Array.isArray(result.items) && result.items.length >= REQUIRED_IDS.length, 'all checks present')

const ids = result.items.map((item) => item.id)
for (const id of REQUIRED_IDS) assert.ok(ids.includes(id), `missing check: ${id}`)
assert.equal(new Set(ids).size, ids.length, 'check ids must be unique')

for (const item of result.items) {
  assert.ok(STATUSES.has(item.status), `${item.id}: bad status ${item.status}`)
  assert.ok(item.level === 'required' || item.level === 'optional', `${item.id}: bad level`)
  assert.equal(typeof item.title, 'string')
  assert.ok(item.title.length > 0, `${item.id}: empty title`)
  // Anything the page can ask the user to fix needs an actionable remedy.
  if (item.status === 'missing' && item.id !== 'sources') {
    assert.ok(item.remedy, `${item.id}: missing check without a remedy`)
    assert.ok(item.remedy.command || item.remedy.note, `${item.id}: remedy is empty`)
  }
}

// The private venv is built on first launch; it is a step, never a blocker.
assert.ok(!result.blocking.includes('venv'), 'venv must not block the setup page')
assert.deepEqual(result.blocking, result.items.filter((i) => i.level === 'required' && i.status === 'missing').map((i) => i.id))
assert.equal(result.ready, result.ok && result.pending.length === 0)

// A machine without the plugin's sources is the only unfixable required item.
if (result.blocking.includes('sources')) {
  const sources = result.items.find((item) => item.id === 'sources')
  assert.equal(sources.remedy, null)
}

// First run is derived from the persisted state file, not from a clock.
assert.equal(result.firstRun, true)
assert.deepEqual(readSetupState(dataDir), { doneAt: null, skippedAt: null })
assert.equal(result.paths.dataDir, dataDir)

// Optional ASR must explain the same step differently per OS: the shell syntax
// for HF_ENDPOINT and the runtime library note are not portable.
const winNote = asrRemedy('win32').note
const macNote = asrRemedy('darwin').note
const linuxNote = asrRemedy('linux').note
assert.match(winNote, /PowerShell/)
assert.match(winNote, /Visual C\+\+/)
assert.match(macNote, /export HF_ENDPOINT/)
assert.match(macNote, /Apple Silicon/)
assert.match(linuxNote, /huggingface\.co/)
assert.notEqual(winNote, macNote)
assert.notEqual(macNote, linuxNote)

const asrItem = result.items.find((item) => item.id === 'asr')
if (asrItem && asrItem.remedy) {
  assert.ok(asrItem.remedy.command.includes('-m pip install faster-whisper'), 'ASR remedy needs a copyable command')
  assert.ok(asrItem.remedy.note.length > 20, 'ASR remedy needs an OS-specific note')
}

writeSetupState(dataDir, { skippedAt: '2026-01-01T00:00:00.000Z' })
assert.equal(readSetupState(dataDir).skippedAt, '2026-01-01T00:00:00.000Z')
assert.equal((await preflight({ dataDir, pluginRoot })).firstRun, false)

writeSetupState(dataDir, { doneAt: '2026-01-02T00:00:00.000Z' })
const done = await preflight({ dataDir, pluginRoot })
assert.equal(done.firstRun, false)
assert.ok(done.state.doneAt)

fs.rmSync(dataDir, { recursive: true, force: true })
console.log('preflight ok:', result.ok, '| blocking:', result.blocking, '| pending:', result.pending)

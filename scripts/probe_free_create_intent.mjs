#!/usr/bin/env node
/** Probe the free-create intent contract against the running DSH host.
 *
 *   node scripts/probe_free_create_intent.mjs [port]
 *
 * Reads the system prompt straight out of plugin/client.js so the probe cannot
 * drift from what the UI actually sends. Prints the raw JSON the model returns.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const port = process.argv[2] || '56372'
const source = readFileSync(path.join(repoRoot, 'plugin/client.js'), 'utf8')

const start = source.indexOf('const systemPrompt = [')
const end = source.indexOf(".join('\\n')", start)
if (start < 0 || end < 0) throw new Error('cannot locate systemPrompt in plugin/client.js')
const systemPrompt = new Function(`${source.slice(start, end)}.join('\\n'); return systemPrompt;`)()

const cases = [
  {
    name: 'revise-param',
    context: '\n当前已有一版提案，用户可能是在它基础上继续：类型=图片；规格=3:4 · 2K；prompt=咖啡海报，暖棕色调',
    text: '改成 4.5k',
  },
  {
    name: 'revise-content',
    context: '\n当前已有一版提案，用户可能是在它基础上继续：类型=图片；规格=1:1 · 2K；prompt=咖啡海报',
    text: '加一点蒸汽和窗边光',
  },
  { name: 'create', context: '', text: '画一张猫在沙发上睡觉的图' },
  { name: 'chat', context: '', text: '你觉得咖啡海报用什么色调比较好' },
  { name: 'cancel', context: '\n当前已有一版提案，类型=视频；规格=9:16 · 8 秒 · 720p', text: '算了，不要了' },
]

for (const item of cases) {
  const response = await fetch(`http://127.0.0.1:${port}/adplus/api/dsh/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      system: systemPrompt + item.context,
      maxTokens: 900,
      messages: [{ role: 'user', content: [{ type: 'text', text: item.text }] }],
    }),
  })
  const body = await response.json()
  const text = String((body.dsh && body.dsh.text) || '')
  console.log(`\n=== ${item.name} :: ${item.text}`)
  console.log(text.replace(/\s*\n\s*/g, ' ').slice(0, 400))
}

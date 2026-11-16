#!/usr/bin/env node
/** Build the publishable plugin package.
 *
 * The source tree keeps the development name and the engine next to the
 * plugin, which is convenient locally and wrong for everybody else. This
 * script produces one self-contained directory: the Host and Client halves,
 * the bundle patch, display resources, and the Python engine sources plus
 * their pinned requirements. No absolute developer path survives.
 *
 *   node scripts/stage-plugin.mjs --out dist/dsh-adclip [--name @acme/dsh-adclip]
 *
 * Publish the result (`npm publish dist/adplus-studio`, or `pnpm pack` it and
 * hand the tarball to Plugin Manager's "Add plugin" dialog).
 */
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const pluginDir = path.join(repoRoot, 'plugin')
const engineSrc = path.join(repoRoot, 'src', 'adclip')
const requirementsSrc = path.join(repoRoot, 'requirements.txt')

function arg(name, fallback) {
  const at = process.argv.indexOf(`--${name}`)
  if (at === -1) return fallback
  const value = process.argv[at + 1]
  if (!value || value.startsWith('--')) throw new Error(`--${name} needs a value`)
  return value
}

const sourceManifest = JSON.parse(readFileSync(path.join(pluginDir, 'package.json'), 'utf8'))
const packageName = arg('name', sourceManifest.name)
const outDir = path.resolve(repoRoot, arg('out', path.join('dist', 'adplus-studio')))
const DEVELOPMENT_NAME = sourceManifest.name

if (!/^(?:@[a-z0-9][a-z0-9._~-]*\/)?[a-z0-9][a-z0-9._~-]*$/.test(packageName)) {
  throw new Error(`not a publishable package name: ${packageName}`)
}
if (!existsSync(requirementsSrc)) throw new Error('requirements.txt is missing at the repository root')
if (!existsSync(path.join(engineSrc, 'api.py'))) throw new Error('src/adclip/api.py is missing')

rmSync(outDir, { recursive: true, force: true })
mkdirSync(outDir, { recursive: true })

for (const entry of ['index.js', 'client.js', 'cordis.patch.yml', 'icon.svg']) {
  cpSync(path.join(pluginDir, entry), path.join(outDir, entry))
}
for (const entry of ['host', 'locale']) {
  cpSync(path.join(pluginDir, entry), path.join(outDir, entry), { recursive: true })
}
cpSync(engineSrc, path.join(outDir, 'engine', 'src', 'adclip'), {
  recursive: true,
  filter: (source) => !source.split(path.sep).includes('__pycache__') && !source.endsWith('.pyc'),
})
cpSync(requirementsSrc, path.join(outDir, 'engine', 'requirements.txt'))

const manifest = {
  ...sourceManifest,
  name: packageName,
  private: undefined,
  license: sourceManifest.license || 'UNLICENSED',
  publishConfig: { access: 'public' },
  engines: { dsh: '>=0.2.1-rc.1 <0.3.0' },
  keywords: ['dsh', 'dsh-plugin', 'ad-video', 'text-to-video', 'storyboard'],
  files: [
    'index.js',
    'client.js',
    'cordis.patch.yml',
    'host/*.js',
    'locale/*.json',
    'icon.svg',
    'LICENSE',
    'NOTICE',
    'engine/**',
  ],
}
delete manifest.private
writeFileSync(path.join(outDir, 'package.json'), JSON.stringify(manifest, null, 2) + '\n')

const packageReadme = `# ${packageName}

Ad+ Studio as a DSH profile bundle: ad-video scenarios (viral remake, text to
video, storyboard edits, stitching, personas, assets) inside the Harness Web UI.

## Install in DSH

1. Open **Plugins** in the DSH sidebar.
2. **Add plugin** and paste \`${packageName}\`.
3. Choose **Enable now**, then restart DSH.

The Web UI composes its client modules at Host start, so the sidebar entry
appears after that restart.

## First launch

The Host half ships the Python engine and prepares a private virtualenv under
the Ad+ data directory on first launch (20–60 s, needs network). Python 3.10+
is only required when that venv has to be built; ffmpeg/ffprobe are required for
media work. Both are explained in the plugin's Settings tab when missing.

Data: \`~/Library/Application Support/AdPlusStudio/data\` (macOS),
\`%APPDATA%/AdPlusStudio/data\` (Windows), \`~/.local/share/adplus-studio/data\`
(Linux). Removing the plugin leaves that directory in place.

## Upgrade

Install the new version over the old one. The data directory and the prepared
runtime survive; the runtime is rebuilt only when the pinned requirements change.
`
writeFileSync(path.join(outDir, 'README.md'), packageReadme)
const licenseFile = path.join(repoRoot, 'LICENSE')
if (existsSync(licenseFile)) cpSync(licenseFile, path.join(outDir, 'LICENSE'))
const noticeFile = path.join(repoRoot, 'NOTICE')
if (existsSync(noticeFile)) cpSync(noticeFile, path.join(outDir, 'NOTICE'))


const rewrite = (file, from, to) => {
  const target = path.join(outDir, file)
  const before = readFileSync(target, 'utf8')
  const after = before.replaceAll(from, to)
  if (after !== before) writeFileSync(target, after)
  return after !== before
}
const renamedPatch = rewrite('cordis.patch.yml', `'${DEVELOPMENT_NAME}'`, `'${packageName}'`)
const renamedClient = rewrite('client.js', `id: '${DEVELOPMENT_NAME}'`, `id: '${packageName}'`)

const problems = []
if (!renamedPatch) problems.push('cordis.patch.yml still names the development package')
if (!renamedClient) problems.push('client.js loader id still names the development package')

const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
  const full = path.join(dir, entry.name)
  if (entry.isDirectory()) return walk(full)
  return [full]
})
const shipped = walk(outDir)
const textFiles = shipped.filter((file) => /\.(js|mjs|json|ya?ml|md|txt)$/.test(file))
for (const file of textFiles) {
  const text = readFileSync(file, 'utf8')
  if (text.includes(repoRoot)) problems.push(`${path.relative(outDir, file)} contains the developer path ${repoRoot}`)
}
for (const file of shipped.filter((f) => f.endsWith('.js'))) {
  try {
    execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' })
  } catch (error) {
    problems.push(`${path.relative(outDir, file)} fails node --check: ${String(error.stderr || error.message).split('\n')[0]}`)
  }
}
for (const required of ['engine/src/adclip/api.py', 'engine/requirements.txt', 'client.js', 'index.js', 'host/engine.js']) {
  if (!existsSync(path.join(outDir, required))) problems.push(`missing ${required}`)
}

const bytes = shipped.reduce((total, file) => total + statSync(file).size, 0)
if (problems.length) {
  console.error('stage-plugin: refusing to build\n' + problems.map((line) => `  - ${line}`).join('\n'))
  process.exit(1)
}
console.log(`staged ${packageName} -> ${outDir}`)
console.log(`  files: ${shipped.length}`)
console.log(`  size:  ${(bytes / 1024).toFixed(0)} KiB`)
console.log('  next:  npm publish <dir>   (or: pnpm pack <dir> and install the tarball)')

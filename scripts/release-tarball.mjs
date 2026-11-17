#!/usr/bin/env node
/** Build a tarball users can install without waiting for pnpm's 24-hour window.
 *
 * pnpm 11 (the one DSH bundles) defaults to `minimumReleaseAge: 1440`: a version
 * published less than a day ago is skipped by `pnpm add <name>`, and also by a
 * tarball URL that points at the npm registry, because pnpm looks the package up
 * to learn its publish time. A tarball served from anywhere else, or an
 * absolute path to a downloaded one, installs immediately.
 *
 *   node scripts/release-tarball.mjs
 *   node scripts/release-tarball.mjs --url-base https://example.com/adclip
 *
 * Upload the printed file wherever users can download it (a GitHub Release, an
 * object store, any static host) and hand them the URL. Nothing is published.
 */
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function arg(name, fallback) {
  const at = process.argv.indexOf(`--${name}`)
  if (at === -1) return fallback
  const value = process.argv[at + 1]
  if (!value || value.startsWith('--')) throw new Error(`--${name} needs a value`)
  return value
}

const sourceManifest = JSON.parse(readFileSync(path.join(repoRoot, 'plugin', 'package.json'), 'utf8'))
const packageName = arg('name', '@chad.dev/dsh-adclip')
const urlBase = arg('url-base', '').replace(/\/+$/, '')
const outDir = path.join(repoRoot, 'dist', 'dsh-adclip')

console.log(`staging ${packageName}@${sourceManifest.version}`)
execFileSync(process.execPath, [
  path.join(repoRoot, 'scripts', 'stage-plugin.mjs'),
  '--out', outDir,
  '--name', packageName,
], { cwd: repoRoot, stdio: 'inherit' })

const manifest = JSON.parse(readFileSync(path.join(outDir, 'package.json'), 'utf8'))
const fileName = packageName.replace(/^@/, '').replace('/', '-') + '-' + manifest.version + '.tgz'
execFileSync('npm', ['pack', outDir, '--pack-destination', path.join(repoRoot, 'dist')], {
  cwd: repoRoot,
  stdio: ['ignore', 'ignore', 'inherit'],
})

const tarball = path.join(repoRoot, 'dist', fileName)
if (!existsSync(tarball)) throw new Error(`npm pack did not produce ${tarball}`)

const bytes = statSync(tarball).size
const sha256 = createHash('sha256').update(readFileSync(tarball)).digest('hex')
const installUrl = urlBase ? `${urlBase}/${fileName}` : ''

console.log('')
console.log(`tarball  ${tarball}`)
console.log(`version  ${manifest.version}`)
console.log(`size     ${(bytes / 1024).toFixed(0)} KiB`)
console.log(`sha256   ${sha256}`)
console.log('')
console.log('Install in DSH — Plugins -> Add plugin, then paste one of:')
console.log(`  ${tarball}`)
if (installUrl) console.log(`  ${installUrl}`)
console.log('')
console.log('A tarball URL on any host other than the npm registry installs immediately;')
console.log('the plain package name waits until the version is 24 hours old (pnpm')
console.log('minimumReleaseAge defaults to 1440 in pnpm 11).')
console.log('After Enable now, quit and reopen DSH so the client module graph includes it.')

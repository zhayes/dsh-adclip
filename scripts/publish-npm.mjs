#!/usr/bin/env node
/** Publish the AdClip plugin package to npm.
 *
 * Stages the self-contained package (engine included), then publishes it with
 * public access. The package name defaults to the npm account's own scope,
 * which every account can publish under without registering an organisation:
 *
 *   node scripts/publish-npm.mjs                 # -> @<npm-user>/dsh-adclip
 *   node scripts/publish-npm.mjs --name @acme/dsh-adclip
 *   node scripts/publish-npm.mjs --dry-run       # validate without publishing
 *
 * After it succeeds, users install with Plugins → Add plugin → the printed
 * name, enable the bundle, and restart DSH once.
 */
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dryRun = process.argv.includes('--dry-run')

function arg(name, fallback) {
  const at = process.argv.indexOf(`--${name}`)
  if (at === -1) return fallback
  const value = process.argv[at + 1]
  if (!value || value.startsWith('--')) throw new Error(`--${name} needs a value`)
  return value
}

function run(command, args, options = {}) {
  return execFileSync(command, args, { cwd: repoRoot, stdio: 'inherit', ...options })
}

function capture(command, args) {
  try {
    return execFileSync(command, args, { cwd: repoRoot, encoding: 'utf8' }).trim()
  } catch {
    return ''
  }
}

const npmUser = capture('npm', ['whoami'])
if (!npmUser && !dryRun) {
  console.error([
    'Not signed in to npm.',
    '',
    '  1. npm login            (a 2FA-enabled account: npm requires one to publish)',
    '  2. node scripts/publish-npm.mjs',
    '',
    'Use --dry-run to validate the package without an account, or --name to',
    'publish under a scope other than your username.',
  ].join('\n'))
  process.exit(1)
}

const version = JSON.parse(readFileSync(path.join(repoRoot, 'plugin', 'package.json'), 'utf8')).version
const packageName = arg('name', npmUser ? `@${npmUser}/dsh-adclip` : '@adplus/dsh-adclip')
const scope = packageName.startsWith('@') ? packageName.slice(1, packageName.indexOf('/')) : ''
if (!packageName.startsWith('@')) {
  console.warn(`warning: ${packageName} is unscoped; anyone can publish that name. Prefer @<your-scope>/dsh-adclip.`)
} else if (scope !== npmUser && npmUser && !dryRun) {
  console.warn(`warning: publishing into scope @${scope}, which ${npmUser} may not own. Use @${npmUser}/${packageName.split('/')[1]} if unsure.`)
}

const outDir = path.join(repoRoot, 'dist', 'dsh-adclip')
console.log(`staging ${packageName}@${version} -> ${outDir}`)
run(process.execPath, [path.join(repoRoot, 'scripts', 'stage-plugin.mjs'), '--out', outDir, '--name', packageName])

// `--otp` forwards the one-time password: npm requires 2FA for publish, and a
// non-interactive shell cannot answer its prompt.
const otp = arg('otp', '')
const publishArgs = ['publish', outDir, '--access', 'public', ...(otp ? [`--otp=${otp}`] : []), ...(dryRun ? ['--dry-run'] : [])]
console.log(`npm ${publishArgs.join(' ')}`)
try {
  run('npm', publishArgs)
} catch (error) {
  if (!dryRun) {
    console.error([
      '',
      'Publish failed. The two common causes:',
      '  - 2FA: run `node scripts/publish-npm.mjs --otp <6-digit code>` (npm requires a one-time password),',
      '  - that version already exists: bump `version` in plugin/package.json.',
    ].join('\n'))
  }
  process.exit(1)
}

const spec = packageName + '@' + version
if (dryRun) {
  console.log(`\ndry run only. Publish for real with:\n  node scripts/publish-npm.mjs${packageName !== `@${npmUser}/dsh-adclip` ? ` --name ${packageName}` : ''}`)
} else {
  console.log(`\npublished ${spec}`)
  console.log('Users install it in DSH with: Plugins -> Add plugin -> ' + spec)
  console.log('then Enable now and restart DSH once (the client module graph composes at start).')
}

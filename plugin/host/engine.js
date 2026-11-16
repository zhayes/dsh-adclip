/** Locate the Python engine, prepare its interpreter, and pick a loopback port.
 *
 * The plugin must work on machines that have neither this checkout nor its
 * virtualenv: the engine ships inside the package, and the first launch builds
 * a private venv beside the user's data. Every absolute path below is derived
 * from the installed package or the data directory, never from the developer's
 * working copy.
 */
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import crypto from 'node:crypto'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import process from 'node:process'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const MIN_PYTHON = [3, 10]

export function defaultDataDir() {
  if (process.env.ADSTUDIO_DATA_DIR) return process.env.ADSTUDIO_DATA_DIR
  if (process.platform === 'darwin') return path.join(os.homedir(), 'Library', 'Application Support', 'AdPlusStudio', 'data')
  if (process.platform === 'win32') return path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), 'AdPlusStudio', 'data')
  return path.join(os.homedir(), '.local', 'share', 'adplus-studio', 'data')
}

/** Interpreter path inside a venv root. */
export function venvPython(venvDir) {
  return process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python')
}

function isFile(target) {
  try { return fs.statSync(target).isFile() } catch { return false }
}

function isDir(target) {
  try { return fs.statSync(target).isDirectory() } catch { return false }
}

function requirementsDigest(file) {
  try { return createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0, 16) } catch { return '' }
}

function readStamp(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) } catch { return null }
}

/** Directories that may hold the engine sources, most specific first. */
export function engineCandidates({ config = {}, pluginRoot }) {
  const list = []
  if (config.engineRoot) list.push(config.engineRoot)
  if (pluginRoot) {
    list.push(path.join(pluginRoot, 'engine'))
    list.push(path.resolve(pluginRoot, '..'))
  }
  return list
}

/** Import root of an engine directory: `src/` in a src-layout tree, else the root itself. */
export function engineModuleRoot(root) {
  if (isFile(path.join(root, 'src', 'adclip', 'api.py'))) return path.join(root, 'src')
  if (isFile(path.join(root, 'adclip', 'api.py'))) return root
  return null
}

/** Resolve the engine sources and the interpreter to run them with.
 *
 * Order: an explicit `config.python`, a virtualenv beside the engine sources
 * (a source checkout), the venv this plugin built under the data directory,
 * then a bootstrap from the system `python3`.
 */
export function resolveEngine({ config = {}, dataDir = defaultDataDir(), pluginRoot }) {
  const candidates = engineCandidates({ config, pluginRoot })
  const engineRoot = candidates.find((root) => engineModuleRoot(root) !== null) || null
  const moduleRoot = engineRoot ? engineModuleRoot(engineRoot) : null
  const relativeVenv = engineRoot ? path.join(engineRoot, '.venv') : null
  const controlDir = path.join(dataDir, '.engine')
  return {
    engineRoot,
    moduleRoot,
    candidates,
    requirements: engineRoot ? path.join(engineRoot, 'requirements.txt') : null,
    controlDir,
    venvDir: path.join(controlDir, 'venv'),
    stampPath: path.join(controlDir, 'venv.json'),
    logPath: path.join(controlDir, 'bootstrap.log'),
    sourceCheckoutPython: relativeVenv ? venvPython(relativeVenv) : null,
    configuredPython: config.python || null,
  }
}

/** Append one bootstrap line to the log file and the in-memory tail. */
function makeLog(logPath) {
  fs.mkdirSync(path.dirname(logPath), { recursive: true })
  const lines = []
  const write = (line) => {
    const text = `[${new Date().toISOString()}] ${line}`
    lines.push(text)
    if (lines.length > 400) lines.splice(0, lines.length - 400)
    try { fs.appendFileSync(logPath, text + '\n') } catch { /* logging never blocks startup */ }
  }
  return { write, tail: () => lines.slice(-60) }
}

function run(file, args, { cwd, timeoutMs = 180000 } = {}) {
  return new Promise((resolve) => {
    let child
    try {
      child = spawn(file, args, {
        cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: '1', PYTHONUNBUFFERED: '1' },
      })
    } catch (error) {
      resolve({ code: -1, output: String(error?.message || error) })
      return
    }
    let output = ''
    const collect = (chunk) => {
      output += String(chunk)
      if (output.length > 20000) output = output.slice(-20000)
    }
    child.stdout?.setEncoding('utf8')
    child.stderr?.setEncoding('utf8')
    child.stdout?.on('data', collect)
    child.stderr?.on('data', collect)
    const timer = setTimeout(() => { try { child.kill('SIGKILL') } catch { /* gone */ } }, timeoutMs)
    child.on('error', (error) => {
      clearTimeout(timer)
      resolve({ code: -1, output: output + String(error?.message || error) })
    })
    child.on('exit', (code, signal) => {
      clearTimeout(timer)
      resolve({ code: code ?? -1, signal, output })
    })
  })
}

function systemPythons() {
  return process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
}

/** Prompt for a loopback port, or reuse the configured one. */
export function pickPort(fixed) {
  const wanted = Number(fixed)
  if (Number.isInteger(wanted) && wanted > 0) return Promise.resolve(wanted)
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : 0
      server.close(() => (port ? resolve(port) : reject(new Error('could not reserve a port'))))
    })
  })
}

/** A free TCP port bound to loopback only. */
export async function freePort() {
  return pickPort(0)
}

/** Version of an interpreter, or null when it cannot be queried. */
async function pythonVersion(python) {
  const result = await run(python, ['-c', 'import sys;print("%d.%d" % sys.version_info[:2])'], { timeoutMs: 15000 })
  if (result.code !== 0) return null
  const match = /^(\d+)\.(\d+)/.exec(result.output.trim())
  return match ? [Number(match[1]), Number(match[2])] : null
}

function versionOk(version) {
  if (!version) return false
  return version[0] > MIN_PYTHON[0] || (version[0] === MIN_PYTHON[0] && version[1] >= MIN_PYTHON[1])
}

/** Smallest install that can run the engine, by platform. */
function pythonHint() {
  if (process.platform === 'darwin') {
    return '未找到 Python 3.10+。安装 Xcode 命令行工具（xcode-select --install）或 Homebrew：brew install python@3.12'
  }
  if (process.platform === 'win32') {
    return '未找到 Python 3.10+。请从 https://www.python.org/downloads/ 安装（勾选 Add python.exe to PATH），或 winget install Python.Python.3.12'
  }
  return '未找到 Python 3.10+。请安装发行版提供的 python3-venv 与 python3-pip，例如 apt install python3 python3-venv python3-pip'
}

/** Ensure a python that can import the engine's dependencies exists.
 *
 * Returns `{ ok, python, source, detail, logs }`; never throws. `source` is
 * one of `config`, `source-checkout`, `venv`, `system`.
 */
export async function ensureRuntime({ config = {}, dataDir = defaultDataDir(), pluginRoot } = {}) {
  const resolved = resolveEngine({ config, dataDir, pluginRoot })
  const logger = makeLog(resolved.logPath)
  const fail = (detail) => {
    logger.write(`failed: ${detail}`)
    return { ok: false, detail, logs: logger.tail(), ...resolved }
  }
  if (!resolved.engineRoot) {
    return fail(`找不到引擎源码（src/adclip/api.py 或 adclip/api.py）。已尝试：${engineCandidates({ config, pluginRoot }).join('、')}`)
  }
  if (resolved.configuredPython) {
    if (isFile(resolved.configuredPython)) {
      logger.write(`using configured python ${resolved.configuredPython}`)
      return { ok: true, python: resolved.configuredPython, source: 'config', engineRoot: resolved.engineRoot, moduleRoot: resolved.moduleRoot, logs: logger.tail() }
    }
    logger.write(`configured python missing, ignoring: ${resolved.configuredPython}`)
  }
  if (resolved.sourceCheckoutPython && isFile(resolved.sourceCheckoutPython)) {
    logger.write(`using source-checkout python ${resolved.sourceCheckoutPython}`)
    return { ok: true, python: resolved.sourceCheckoutPython, source: 'source-checkout', engineRoot: resolved.engineRoot, moduleRoot: resolved.moduleRoot, logs: logger.tail() }
  }
  const digest = requirementsDigest(resolved.requirements)
  const venvPythonPath = venvPython(resolved.venvDir)
  if (isFile(venvPythonPath)) {
    const stamp = readStamp(resolved.stampPath)
    if (!digest || stamp?.requirements === digest) {
      logger.write(`using prepared venv ${resolved.venvDir}`)
      return { ok: true, python: venvPythonPath, source: 'venv', engineRoot: resolved.engineRoot, moduleRoot: resolved.moduleRoot, logs: logger.tail() }
    }
    logger.write('requirements changed, rebuilding the venv')
  }
  if (!resolved.requirements || !isFile(resolved.requirements)) {
    return fail(`引擎依赖清单缺失：${resolved.requirements}`)
  }
  let python = null
  for (const candidate of systemPythons()) {
    const version = await pythonVersion(candidate)
    if (versionOk(version)) { python = candidate; break }
    if (version) logger.write(`${candidate} is ${version.join('.')}, need ${MIN_PYTHON.join('.')}+`)
  }
  if (!python) return fail(pythonHint())
  logger.write(`bootstrapping venv with ${python} (${resolved.venvDir})`)
  const created = await run(python, ['-m', 'venv', resolved.venvDir], { timeoutMs: 120000 })
  if (created.code !== 0) {
    logger.write(created.output)
    return fail('创建 Python 虚拟环境失败，请确认已安装 python3-venv（macOS 上通常随 Xcode 命令行工具提供）')
  }
  const installed = await run(venvPythonPath, ['-m', 'pip', 'install', '--no-input', '-r', resolved.requirements], {
    cwd: resolved.engineRoot,
    timeoutMs: 600000,
  })
  if (installed.code !== 0) {
    logger.write(installed.output)
    return fail('安装引擎依赖失败。请检查网络或代理后重试；也可以手动把依赖装进该虚拟环境。')
  }
  fs.mkdirSync(path.dirname(resolved.stampPath), { recursive: true })
  fs.writeFileSync(resolved.stampPath, JSON.stringify({
    requirements: digest,
    python: (await pythonVersion(venvPythonPath))?.join('.') || '',
    at: new Date().toISOString(),
  }, null, 2))
  logger.write('venv ready')
  return { ok: true, python: venvPythonPath, source: 'venv', engineRoot: resolved.engineRoot, moduleRoot: resolved.moduleRoot, logs: logger.tail() }
}

/** Stable id for one engine launch, so the page can spot a replacement. */
export function launchId() {
  return crypto.randomBytes(6).toString('hex')
}

export { sleep }

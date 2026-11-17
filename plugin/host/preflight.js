/** First-run environment checks for the Host half.
 *
 * Everything the engine cannot report about itself when it is not running lives
 * here: the interpreter, ffmpeg, the data directory. The result is plain data,
 * so the Web UI can render a setup page without guessing or parsing logs.
 *
 * Checks never install anything. Each failing item carries a `remedy` the page
 * can present as a copyable command plus a link, or as a manual instruction.
 */
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import {
  defaultDataDir,
  engineModuleRoot,
  pythonVersion,
  resolveBinary,
  resolveEngine,
  runCommand,
  systemPythons,
  venvPython,
  versionOk,
  windowsInterpreters,
} from './engine.js'

const SETUP_FILE = 'setup.json'

export function setupStatePath(dataDir) {
  return path.join(dataDir, '.engine', SETUP_FILE)
}

export function readSetupState(dataDir) {
  try {
    const value = JSON.parse(fs.readFileSync(setupStatePath(dataDir), 'utf8'))
    return {
      doneAt: typeof value.doneAt === 'string' ? value.doneAt : null,
      skippedAt: typeof value.skippedAt === 'string' ? value.skippedAt : null,
    }
  } catch {
    return { doneAt: null, skippedAt: null }
  }
}

export function writeSetupState(dataDir, patch) {
  const file = setupStatePath(dataDir)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const next = { ...readSetupState(dataDir), ...patch, at: new Date().toISOString() }
  fs.writeFileSync(file, JSON.stringify(next, null, 2))
  return next
}

function isFile(target) {
  try { return fs.statSync(target).isFile() } catch { return false }
}

function digestOf(file) {
  try { return createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0, 16) } catch { return '' }
}

/** Installed package inside a venv, without importing it (imports are slow). */
function venvHasPackage(venvDir, name) {
  const roots = [path.join(venvDir, 'Lib', 'site-packages')]
  const lib = path.join(venvDir, 'lib')
  try {
    for (const entry of fs.readdirSync(lib, { withFileTypes: true })) {
      if (entry.isDirectory()) roots.push(path.join(lib, entry.name, 'site-packages'))
    }
  } catch { /* no lib/ on Windows */ }
  return roots.some((root) => fs.existsSync(path.join(root, name)))
}

function remedies() {
  if (process.platform === 'win32') {
    return {
      python: {
        kind: 'command',
        command: 'winget install --id Python.Python.3.12 -e',
        url: 'https://www.python.org/downloads/windows/',
        note: '安装时勾选 “Add python.exe to PATH”。装完完全退出 DSH 再打开。',
      },
      ffmpeg: {
        kind: 'command',
        command: 'winget install --id Gyan.FFmpeg -e',
        url: 'https://www.gyan.dev/ffmpeg/builds/',
        note: '也可以下载完整包，解压后把 bin 目录加入 PATH。装完必须完全退出 DSH 再打开。',
      },
      data: { kind: 'manual', note: '检查 %APPDATA% 的写权限，或安全软件是否拦截了插件目录。' },
    }
  }
  if (process.platform === 'darwin') {
    return {
      python: {
        kind: 'command',
        command: 'brew install python@3.12',
        url: 'https://www.python.org/downloads/macos/',
        note: '没有 Homebrew 时可用 xcode-select --install 提供的 python3。',
      },
      ffmpeg: {
        kind: 'command',
        command: 'brew install ffmpeg',
        url: 'https://evermeet.cx/ffmpeg/',
        note: '也可以用 evermeet 的静态包，把二进制放进 PATH。',
      },
      data: { kind: 'manual', note: '检查 ~/Library/Application Support 的写权限。' },
    }
  }
  return {
    python: {
      kind: 'command',
      command: 'sudo apt install python3 python3-venv python3-pip',
      url: 'https://www.python.org/downloads/',
      note: 'Debian/Ubuntu 需要 python3-venv；Fedora 用 dnf。',
    },
    ffmpeg: {
      kind: 'command',
      command: 'sudo apt install ffmpeg',
      url: 'https://ffmpeg.org/download.html',
      note: 'Fedora 上用 dnf install ffmpeg。',
    },
    data: { kind: 'manual', note: '检查 ~/.local/share 的写权限。' },
  }
}

function trimLine(text, limit = 110) {
  const line = String(text || '').split(/\r?\n/).find(Boolean) || ''
  return line.length > limit ? line.slice(0, limit) + '…' : line
}

/** Pick the interpreter the engine would use. Mirrors ensureRuntime's order. */
async function findPython(resolved, runtime) {
  const candidates = []
  if (runtime?.ok && runtime.python) candidates.push(runtime.python)
  candidates.push(venvPython(resolved.venvDir), resolved.sourceCheckoutPython, resolved.configuredPython)
  for (const candidate of candidates) {
    if (!candidate || !isFile(candidate)) continue
    const version = await pythonVersion(candidate)
    if (versionOk(version)) return { python: candidate, version, source: 'existing' }
  }
  for (const row of await windowsInterpreters()) {
    if (/\\WindowsApps\\/i.test(row.path)) continue
    const version = await pythonVersion(row.path)
    if (versionOk(version)) return { python: row.path, version, source: 'py-launcher' }
  }
  for (const candidate of systemPythons()) {
    const version = await pythonVersion(candidate)
    if (versionOk(version)) return { python: candidate, version, source: 'path' }
  }
  return null
}

/**
 * Run every check and return data for the first-run page.
 * Never throws: a broken check becomes a failed item, not a rejected promise.
 */
export async function preflight({ config = {}, dataDir = defaultDataDir(), pluginRoot, runtime = null } = {}) {
  const resolved = resolveEngine({ config, dataDir, pluginRoot })
  const fix = remedies()
  const items = []
  const push = (item) => items.push(item)

  // 1. Engine sources — nothing works without them.
  const moduleRoot = engineModuleRoot(resolved.engineRoot || '')
  push({
    id: 'sources',
    level: 'required',
    status: moduleRoot ? 'ok' : 'missing',
    title: '引擎源码',
    detail: moduleRoot ? resolved.engineRoot : '包内缺少 engine/src/adclip，需要重新打包',
    remedy: null,
  })

  // 2. Python 3.10+.
  const found = await findPython(resolved, runtime)
  push({
    id: 'python',
    level: 'required',
    status: found ? 'ok' : 'missing',
    title: 'Python 3.10+',
    detail: found ? `Python ${found.version.join('.')} · ${found.python}` : '未找到可用的解释器',
    remedy: found ? null : fix.python,
  })

  // 3. Private venv. Missing is normal on first run; the engine builds it.
  const venvPy = venvPython(resolved.venvDir)
  const venvReady = isFile(venvPy)
  const stamp = venvReady ? (() => {
    try { return JSON.parse(fs.readFileSync(resolved.stampPath, 'utf8')) } catch { return null }
  })() : null
  const digest = digestOf(resolved.requirements)
  const venvCurrent = venvReady && (!digest || stamp?.requirements === digest)
  // A source checkout or an overriding interpreter never builds this venv.
  const externalPython = Boolean(runtime?.ok && ['config', 'source-checkout'].includes(runtime.source))
  push({
    id: 'venv',
    level: 'required',
    status: externalPython || venvCurrent ? 'ok' : 'warn',
    title: 'Python 依赖环境',
    detail: externalPython
      ? `使用现成解释器：${runtime.python}`
      : venvCurrent
        ? resolved.venvDir
        : (venvReady ? '依赖已变化，启动时会重建' : '首次启动时自动创建（约 1 分钟，需要联网）'),
    remedy: null,
  })

  // 4/5. ffmpeg + ffprobe.
  for (const name of ['ffmpeg', 'ffprobe']) {
    const binary = resolveBinary(name)
    let version = ''
    let broken = false
    if (binary) {
      const probe = await runCommand(binary, ['-hide_banner', '-version'], { timeoutMs: 8000 })
      version = probe.code === 0 ? trimLine(probe.output) : trimLine(probe.output, 140)
      broken = probe.code !== 0
    }
    push({
      id: name,
      level: 'required',
      status: binary && !broken ? 'ok' : 'missing',
      title: name === 'ffmpeg' ? 'ffmpeg' : 'ffprobe',
      detail: binary ? (broken ? `无法执行：${version}` : version) : '未在 PATH 或常见安装目录中找到',
      remedy: binary && !broken ? null : fix.ffmpeg,
    })
  }

  // 6. Data directory must be writable; the engine writes on first start.
  let dataOk = true
  let dataDetail = dataDir
  try {
    fs.mkdirSync(dataDir, { recursive: true })
    const probeFile = path.join(dataDir, '.preflight-write')
    fs.writeFileSync(probeFile, 'ok')
    fs.unlinkSync(probeFile)
  } catch (error) {
    dataOk = false
    dataDetail = `${dataDir}（${error?.code || error?.message || error}）`
  }
  push({
    id: 'data',
    level: 'required',
    status: dataOk ? 'ok' : 'missing',
    title: '数据目录',
    detail: dataDetail,
    remedy: dataOk ? null : fix.data,
  })

  // 7. Optional: local ASR, installed by hand, never by the bootstrap.
  const asrInstalled = venvReady && venvHasPackage(resolved.venvDir, 'faster_whisper')
  push({
    id: 'asr',
    level: 'optional',
    status: asrInstalled ? 'ok' : 'warn',
    title: '本地语音识别（可选）',
    detail: asrInstalled
      ? '已安装，参考片可自动转写'
      : '未安装，参考片只做画面分析；不影响出片',
    remedy: {
      kind: 'command',
      command: `"${venvPy}" -m pip install faster-whisper`,
      url: 'https://github.com/SYSTRAN/faster-whisper',
      note: '首次识别会下载约 500 MB 模型；网络受限时设置 HF_ENDPOINT=https://hf-mirror.com。',
    },
  })

  const required = items.filter((item) => item.level === 'required')
  // `missing` stops the engine; `warn` is a step that completes on its own
  // (the private venv), so it must not gate the page.
  const blocking = required.filter((item) => item.status === 'missing').map((item) => item.id)
  const pending = required.filter((item) => item.status === 'warn').map((item) => item.id)
  const state = readSetupState(dataDir)
  return {
    ok: blocking.length === 0,
    ready: blocking.length === 0 && pending.length === 0,
    blocking,
    pending,
    platform: process.platform,
    checkedAt: new Date().toISOString(),
    firstRun: !state.doneAt && !state.skippedAt,
    state,
    paths: { dataDir, engineRoot: resolved.engineRoot || '', venvDir: resolved.venvDir, moduleRoot: moduleRoot || '' },
    items,
  }
}

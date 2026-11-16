/** Own the Python sidecar: prepare its interpreter, launch it, watch it, stop it.
 *
 * The plugin runs on machines that never saw this checkout, so nothing here
 * may assume a developer path. `host/engine.js` resolves the bundled sources
 * and builds a private venv under the data directory on first launch; this
 * class only spends that answer.
 */
import { spawn } from 'node:child_process'
import http from 'node:http'
import crypto from 'node:crypto'
import process from 'node:process'
import { defaultDataDir, ensureRuntime, freePort, sleep } from './engine.js'

export { defaultDataDir }

function getJson(url, timeoutMs = 1500) {
  if (!url) return Promise.resolve({ ok: false, status: 0 })
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', (chunk) => { body += chunk })
      res.on('end', () => {
        try { resolve({ ok: res.statusCode >= 200 && res.statusCode < 300, data: JSON.parse(body), status: res.statusCode }) }
        catch { resolve({ ok: false, status: res.statusCode }) }
      })
    })
    req.on('timeout', () => { req.destroy(); resolve({ ok: false, status: 0 }) })
    req.on('error', () => resolve({ ok: false, status: 0 }))
  })
}

function killTree(child, signal) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return
  if (process.platform === 'win32') {
    try { spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' }) } catch { /* already gone */ }
    return
  }
  try { process.kill(-child.pid, signal) } catch {
    try { child.kill(signal) } catch { /* already gone */ }
  }
}

export class EngineSupervisor {
  constructor(config = {}, options = {}) {
    this.config = config || {}
    this.pluginRoot = options.pluginRoot || null
    this.dataDir = this.config.dataDir || defaultDataDir()
    const fixed = Number(this.config.port)
    this.fixedPort = Number.isInteger(fixed) && fixed > 0 && fixed < 65536 ? fixed : 0
    this.port = this.fixedPort
    this.autoStart = this.config.autoStart !== false
    this.token = crypto.randomBytes(24).toString('hex')
    this.child = null
    this.python = null
    this.engineRoot = null
    this.moduleRoot = null
    this.stopping = false
    this.restarts = 0
    this.failures = 0
    this.logs = []
    this.watchTimer = null
    this.running = null
    this.boot = { stage: 'idle', detail: '', logs: [], source: '' }
    this.status = { ok: false, detail: 'not started', url: this.url, boot: this.boot }
  }

  get url() { return this.port ? `http://127.0.0.1:${this.port}` : '' }

  log(line) {
    this.logs.push(`[${new Date().toISOString()}] ${line}`)
    if (this.logs.length > 200) this.logs.splice(0, this.logs.length - 200)
  }

  /** One object the page can render without guessing. */
  snapshot() {
    return {
      ...this.status,
      url: this.url,
      port: this.port,
      python: this.python,
      engineRoot: this.engineRoot,
      moduleRoot: this.moduleRoot,
      boot: this.boot,
      logs: (this.status.logs || this.logs).slice(-40),
    }
  }

  async health() {
    return getJson(this.url ? `${this.url}/health` : '', 1500)
  }

  setBoot(stage, detail, extra = {}) {
    this.boot = { ...this.boot, stage, detail, ...extra }
    this.status = { ...this.status, boot: this.boot }
  }

  /** Prepare, launch and confirm the engine. Safe to call repeatedly. */
  async start() {
    if (this.running) return this.running
    this.running = this.#start().finally(() => { this.running = null })
    return this.running
  }

  async #start() {
    if (this.fixedPort) {
      const existing = await this.health()
      if (existing.ok && existing.data?.service === 'adclip') {
        this.status = { ok: true, detail: 'reused', url: this.url, data: existing.data, boot: this.boot }
        this.setBoot('ready', '已复用正在运行的引擎')
        this.startWatch()
        return
      }
    }
    if (!this.autoStart) {
      this.status = { ...this.status, ok: false, detail: 'autoStart disabled' }
      this.setBoot('disabled', '配置里关闭了 autoStart')
      return
    }
    this.parentStartedAt = Date.now()
    this.setBoot('preparing', '准备 Python 运行时…')
    const runtime = await ensureRuntime({ config: this.config, dataDir: this.dataDir, pluginRoot: this.pluginRoot })
    if (!runtime.ok) {
      this.status = { ok: false, detail: runtime.detail, url: this.url, logs: runtime.logs, boot: this.boot }
      this.setBoot('failed', runtime.detail, { logs: runtime.logs })
      this.log(`runtime unavailable: ${runtime.detail}`)
      return
    }
    this.python = runtime.python
    this.engineRoot = runtime.engineRoot
    this.moduleRoot = runtime.moduleRoot || runtime.engineRoot
    this.setBoot('preparing', `引擎运行时就绪（${runtime.source}），启动服务…`, { source: runtime.source })
    this.port = this.fixedPort || await freePort()
    this.status = { ok: false, detail: 'starting', url: this.url, boot: this.boot }
    this.spawnEngine()
    const deadline = Date.now() + 30000
    while (Date.now() < deadline) {
      if (this.stopping) return
      const check = await this.health()
      if (check.ok && check.data?.service === 'adclip') {
        this.status = { ok: true, detail: 'started', url: this.url, data: check.data, boot: this.boot }
        this.setBoot('ready', '引擎已就绪')
        this.log('engine healthy')
        this.startWatch()
        return
      }
      await sleep(400)
    }
    this.status = { ok: false, detail: '引擎启动超时', url: this.url, logs: this.logs.slice(-40), boot: this.boot }
    this.setBoot('failed', '引擎启动超时', { logs: this.logs.slice(-40) })
    this.log('engine startup timeout')
  }

  spawnEngine() {
    if (this.child) return
    const args = ['-m', 'adclip.api', '--host', '127.0.0.1', '--port', String(this.port), '--graceful-timeout', '5']
    this.log(`spawn ${this.python} ${args.join(' ')} (cwd ${this.moduleRoot})`)
    const child = spawn(this.python, args, {
      cwd: this.moduleRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        ADSTUDIO_DATA_DIR: this.dataDir,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32',
    })
    this.child = child
    child.stdout?.setEncoding('utf8')
    child.stderr?.setEncoding('utf8')
    child.stdout?.on('data', (chunk) => this.log(String(chunk).trim()))
    child.stderr?.on('data', (chunk) => this.log(String(chunk).trim()))
    child.on('error', (error) => this.log(`engine spawn failed: ${error?.message || error}`))
    child.on('exit', (code, signal) => {
      this.log(`engine exited code=${code} signal=${signal}`)
      if (this.child === child) this.child = null
      if (this.stopping) return
      this.stopWatch()
      this.status = { ok: false, detail: `engine exited (${code ?? signal})`, url: this.url, logs: this.logs.slice(-40), boot: this.boot }
      this.setBoot('stopped', `引擎退出（${code ?? signal}）`, { logs: this.logs.slice(-40) })
      if (this.restarts < 2 && this.autoStart) {
        this.restarts += 1
        setTimeout(() => { void this.start() }, 1000)
      }
    })
  }

  /** Restart after a wedged child or a failed bootstrap. */
  async restart() {
    this.log('restart requested')
    this.restarts = 0
    const wasStopping = this.stopping
    this.stopping = true
    await this.killChild()
    this.stopping = wasStopping
    this.failures = 0
    await this.start()
    return this.snapshot()
  }

  async killChild() {
    const child = this.child
    this.child = null
    if (!child) return
    this.log('stopping engine')
    killTree(child, 'SIGTERM')
    const deadline = Date.now() + 5000
    while (Date.now() < deadline && child.exitCode === null && child.signalCode === null) await sleep(100)
    if (child.exitCode === null && child.signalCode === null) {
      this.log('engine ignored SIGTERM, killing it')
      killTree(child, 'SIGKILL')
    }
  }

  startWatch() {
    this.stopWatch()
    this.failures = 0
    this.watchTimer = setInterval(() => { void this.watchOnce() }, 15000)
    this.watchTimer.unref?.()
  }

  async watchOnce() {
    if (this.stopping || this.running) return
    const check = await this.health()
    if (check.ok) { this.failures = 0; return }
    this.failures += 1
    this.log(`health check failed (${this.failures}/3)`)
    if (this.failures >= 3) {
      this.failures = 0
      if (this.restarts >= 4) {
        this.setBoot('failed', '引擎反复无响应，已停止自动重启', { logs: this.logs.slice(-40) })
        return
      }
      this.restarts += 1
      this.log('watchdog restarting the engine')
      await this.restart()
    }
  }

  stopWatch() {
    if (this.watchTimer) clearInterval(this.watchTimer)
    this.watchTimer = null
  }

  async stop() {
    this.stopping = true
    this.stopWatch()
    await this.killChild()
    this.setBoot('stopped', '已停止')
  }
}

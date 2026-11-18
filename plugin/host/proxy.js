import http from 'node:http'
import { execFile } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { URL } from 'node:url'

const ALLOWED_METHODS = new Set(['GET', 'POST', 'PATCH', 'DELETE', 'PUT', 'OPTIONS'])

function writeJson(res, status, body) {
  const text = JSON.stringify(body)
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
  res.end(text)
}

function tokenFrom(req, url) {
  const header = req.headers['x-adplus-token']
  if (typeof header === 'string' && header) return header
  return url.searchParams.get('token') || ''
}

function readBody(req, limit = 1_000_000) {
  return new Promise((resolve, reject) => {
    let size = 0
    const chunks = []
    req.on('data', (chunk) => {
      size += chunk.length
      if (size > limit) { reject(new Error('request too large')); return }
      chunks.push(chunk)
    })
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')))
    req.on('error', reject)
  })
}

export function registerProxy(ctx, supervisor, dsh) {
  const handler = async (req, res) => {
    if (!ALLOWED_METHODS.has(req.method || 'GET')) {
      writeJson(res, 405, { error: { code: 'method_not_allowed' } })
      return
    }
    const url = new URL(req.url || '/', supervisor.url || 'http://127.0.0.1')
    if (url.pathname === '/adplus/health') {
      // The first-run page polls this; make sure it gets a check even if the
      // engine never started (autoStart off, or a failed bootstrap).
      if (supervisor.preflightData && !supervisor.preflightData.checkedAt) void supervisor.refreshPreflight()
      writeJson(res, 200, { ok: true, engine: supervisor.snapshot ? supervisor.snapshot() : supervisor.status })
      return
    }
    if (!url.pathname.startsWith('/adplus/api') && !url.pathname.startsWith('/adplus/media')) {
      writeJson(res, 404, { error: { code: 'not_found' } })
      return
    }
    const token = tokenFrom(req, url)
    const remote = req.socket?.remoteAddress || ''
    const loopback = remote === '127.0.0.1' || remote === '::1' || remote === '::ffff:127.0.0.1'
    // The page normally carries the injected token. Allow a loopback request
    // without one so a freshly installed bundle works before the page refresh;
    // a wrong token is always rejected.
    if (token && supervisor.token && token !== supervisor.token) {
      writeJson(res, 401, { error: { code: 'unauthorized', message: 'refresh the page to refresh the AdClip token' } })
      return
    }
    if (!token && !loopback) {
      writeJson(res, 401, { error: { code: 'unauthorized', message: 'loopback or token required' } })
      return
    }
    if (url.pathname === '/adplus/api/engine/restart' && req.method === 'POST') {
      // Answers before the restart finishes: preparing a missing runtime can
      // take minutes, and the page already polls /adplus/health for progress.
      void supervisor.restart()
      writeJson(res, 202, { ok: true, restarting: true, engine: supervisor.status })
      return
    }
    // The first-run page must answer while the engine is still down, so these
    // routes sit before the engine-availability guard.
    if (url.pathname === '/adplus/api/setup') {
      if (!supervisor.preflightData?.checkedAt) await supervisor.refreshPreflight()
      writeJson(res, 200, { ok: true, setup: supervisor.setupState(), preflight: supervisor.preflightData })
      return
    }
    if (url.pathname === '/adplus/api/setup/state' && req.method === 'POST') {
      try {
        const body = JSON.parse(await readBody(req) || '{}')
        const patch = {}
        if (body.done === true) patch.doneAt = new Date().toISOString()
        if (body.skip === true) patch.skippedAt = new Date().toISOString()
        if (body.reset === true) { patch.doneAt = null; patch.skippedAt = null }
        const setup = supervisor.markSetup(patch)
        writeJson(res, 200, { ok: true, setup, preflight: supervisor.preflightData })
      } catch (error) {
        writeJson(res, 400, { error: { code: 'bad_setup_state', message: String(error?.message || error) } })
      }
      return
    }
    if (url.pathname === '/adplus/api/setup/recheck' && req.method === 'POST') {
      writeJson(res, 200, { ok: true, preflight: await supervisor.refreshPreflight() })
      return
    }
    if (!supervisor.status?.ok) {
      writeJson(res, 503, { error: { code: 'engine_unavailable', message: supervisor.status?.detail || 'engine unavailable', logs: supervisor.status?.logs || [] } })
      return
    }
    if (url.pathname === '/adplus/api/reveal' && req.method === 'POST') {
      try {
        const body = JSON.parse(await readBody(req) || '{}')
        const dataDir = path.resolve(supervisor.dataDir || '')
        const rel = String(body.path || '').replace(/^\/+/, '')
        const target = path.resolve(dataDir, rel)
        if (!dataDir || (target !== dataDir && !target.startsWith(dataDir + path.sep))) {
          writeJson(res, 400, { error: { code: 'bad_path', message: 'path outside data directory' } })
          return
        }
        if (!fs.existsSync(target)) {
          writeJson(res, 404, { error: { code: 'not_found', message: 'path not found' } })
          return
        }
        const args = process.platform === 'darwin' ? (fs.statSync(target).isDirectory() ? [target] : ['-R', target]) : []
        if (process.platform === 'darwin') execFile('open', args, () => {})
        else if (process.platform === 'win32') execFile('explorer.exe', ['/select,', target], () => {})
        else execFile('xdg-open', [fs.statSync(target).isDirectory() ? target : path.dirname(target)], () => {})
        writeJson(res, 200, { ok: true })
      } catch (error) {
        writeJson(res, 500, { error: { code: 'reveal_failed', message: String(error?.message || error) } })
      }
      return
    }
    if (url.pathname === '/adplus/api/dsh/models') {
      try {
        writeJson(res, 200, { dsh: await dsh.list() })
      } catch (error) {
        writeJson(res, 500, { error: { code: 'dsh_models_failed', message: String(error?.message || error) } })
      }
      return
    }
    if (url.pathname === '/adplus/api/dsh/chat' && req.method === 'POST') {
      try {
        const body = JSON.parse(await readBody(req) || '{}')
        const result = await dsh.chat(body)
        writeJson(res, 200, { dsh: result })
      } catch (error) {
        writeJson(res, 500, { error: { code: 'dsh_chat_failed', message: String(error?.message || error) } })
      }
      return
    }
    if (url.pathname === '/adplus/api/dsh/vision' && req.method === 'POST') {
      try {
        const body = JSON.parse(await readBody(req) || '{}')
        if (!Array.isArray(body.frames) || body.frames.length === 0 || body.frames.length > 12) {
          writeJson(res, 422, { error: { code: 'bad_frames', message: 'frames must contain 1–12 keyframes' } })
          return
        }
        const result = await dsh.vision(body)
        writeJson(res, 200, { dsh: result })
      } catch (error) {
        writeJson(res, 500, { error: { code: 'dsh_vision_failed', message: String(error?.message || error) } })
      }
      return
    }
    let targetPath = url.pathname
    if (targetPath.startsWith('/adplus/media')) {
      targetPath = '/media'
    } else {
      targetPath = targetPath.slice('/adplus/api'.length) || '/'
    }
    const targetUrl = new URL(supervisor.url)
    const options = {
      hostname: targetUrl.hostname,
      port: targetUrl.port,
      path: targetPath + (url.search ? url.search : ''),
      method: req.method,
      headers: { ...req.headers, host: `${targetUrl.hostname}:${targetUrl.port}` },
    }
    const upstream = http.request(options, (up) => {
      res.writeHead(up.statusCode || 502, up.headers)
      up.pipe(res)
    })
    upstream.on('error', (error) => {
      writeJson(res, 502, { error: { code: 'engine_proxy_failed', message: String(error?.message || error) } })
    })
    req.pipe(upstream)
  }
  return ctx.webServer.register({ kind: 'prefix', path: '/adplus', handler })
}

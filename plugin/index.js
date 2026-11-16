import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { EngineSupervisor } from './host/supervisor.js'
import { registerProxy } from './host/proxy.js'
import { createDshBridge } from './host/dsh.js'

export const inject = ['webServer']

/** The installed package root, used to find the bundled engine sources. */
const pluginRoot = path.dirname(fileURLToPath(import.meta.url))

export function apply(ctx, config = {}) {
  const supervisor = new EngineSupervisor(config, { pluginRoot })
  const dsh = createDshBridge(ctx)
  const boot = { token: supervisor.token, base: '/adplus/api', media: '/adplus/media' }

  ctx.effect(() => {
    void supervisor.start()
    return () => { void supervisor.stop() }
  }, 'adplus-studio-engine')

  ctx.effect(() => registerProxy(ctx, supervisor, dsh), 'adplus-studio-proxy')

  ctx.effect(() => ctx.webServer.tapIndex((html) => html.replace(
    '</body>',
    `<script>window.__ADPLUS_STUDIO__=${JSON.stringify(boot)}</script></body>`,
  )), 'adplus-studio-boot-token')

  ctx.effect(() => {
    const timer = setInterval(() => {
      void supervisor.health().then((result) => {
        if (result.ok && result.data?.service === 'adclip') {
          supervisor.status = { ...supervisor.status, ok: true, detail: 'healthy', url: supervisor.url, data: result.data }
        }
      })
    }, 15000)
    return () => clearInterval(timer)
  }, 'adplus-studio-health')
}

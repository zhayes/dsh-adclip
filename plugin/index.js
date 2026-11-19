import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { EngineSupervisor } from './host/supervisor.js'
import { registerProxy } from './host/proxy.js'
import { createDshBridge } from './host/dsh.js'
import { registerAdclipTools } from './host/tools.js'

export const inject = ['webServer', 'tools', 'systemPrompt']

/** The installed package root, used to find the bundled engine sources. */
const pluginRoot = path.dirname(fileURLToPath(import.meta.url))

export function apply(ctx, config = {}) {
  const currentDshWebUrl = () => {
    const port = Number(ctx.webServer && ctx.webServer.port)
    if (!port) return ''
    const host = String((ctx.webServer && ctx.webServer.host) || '127.0.0.1')
    return `http://${host === '0.0.0.0' ? '127.0.0.1' : host}:${port}`
  }
  const supervisor = new EngineSupervisor(config, { pluginRoot, dshWebUrl: currentDshWebUrl })
  const dsh = createDshBridge(ctx)
  const boot = { token: supervisor.token, base: '/adplus/api', media: '/adplus/media' }

  ctx.effect(() => {
    void supervisor.start()
    return () => { void supervisor.stop() }
  }, 'adplus-studio-engine')

  ctx.effect(() => registerProxy(ctx, supervisor, dsh), 'adplus-studio-proxy')

  ctx.effect(() => registerAdclipTools(ctx, supervisor), 'adplus-studio-tools')

  ctx.effect(() => ctx.systemPrompt.section({
    name: 'adclip:remake-guidance',
    order: 3000,
    interpolate: false,
    text: [
      '【AdClip 爆款复刻模式】',
      '当用户要求“爆款复刻 / 复刻这条视频 / 换人换商品但保留原片”时，优先调用 adclip_remake_video，不要询问用户选择模型。',
      '默认契约：保持参考片的镜头、景别、运镜、场景、动作、构图、节奏、转场和声音；只替换用户指定的人物/商品。',
      '例外：用户在 brief 或 explicit_overrides 中明确要求改动的场景、道具、动作、台词，按用户要求执行。',
      '启动后返回 run_id；用 adclip_get_run 轮询，需要拆解详情时用 adclip_get_analysis；不要重复提交同一任务。',
      '如果工具返回 fallback/degraded，告诉用户当前使用的路径和原因。',
    ].join('\n'),
  }), 'adplus-studio-remake-prompt')

  ctx.effect(() => ctx.systemPrompt.section({
    name: 'adclip:free-create-guidance',
    order: 3010,
    interpolate: false,
    text: [
      '【AdClip 自由创作与素材】',
      '仅在用户明确要求自由创作、生成图片、生成视频、拼接或查找素材时使用本节。',
      '生成图片调用 adclip_create_image；生成视频调用 adclip_create_video；不要询问用户选择图片/视频模型。',
      '未指定视频格式时默认 9:16 / 8 秒 / 720p；未指定图片格式时默认 1:1 / 2K。',
      '需要复用已上传素材或模特时调用 adclip_list_assets / adclip_list_personas，不要让用户重复上传。',
      '只有用户明确要求拼接时才调用 adclip_stitch_videos；普通自由创作不要走拼接。',
      '普通聊天、问方案、改文案时不要调用生成工具；信息不足时先问一个澄清问题。',
      '复刻请求始终优先 adclip_remake_video，不要用自由创作工具替代复刻，也不要改变复刻的保留契约。',
    ].join('\n'),
  }), 'adplus-studio-create-prompt')

  ctx.effect(() => ctx.systemPrompt.section({
    name: 'adclip:vision-guidance',
    order: 3005,
    interpolate: false,
    text: [
      '【AdClip 参考片拆解视觉链】',
      '视觉标签按 MiniMax-M3 → Doubao-Seed-2.1（pro → turbo → lite，火山方舟）→ DSH 视觉桥 → 启发式 自动降级。',
      '不要询问用户选择视觉模型；用 adclip_get_analysis 读取 provider/model，degraded 时说明降级到启发式的原因。',
      '台词时间轴来自本地语音识别：需要单独转写或拿逐句时间时用 adclip_transcribe_audio（asset_id 或 run_id）。',
      'ASR 未安装或失败时 analysis.asr.source 会是 not_installed/disabled/failed/silent，如实告诉用户并给出安装命令，不要编造台词。',
    ].join('\n'),
  }), 'adplus-studio-vision-prompt')

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

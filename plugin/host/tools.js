/** DSH agent tools over the running AdClip engine.
 *
 * The agent gets one high-level remake tool instead of one tool per model:
 * model selection is a capability decision made inside the engine, so the
 * conversation never has to ask the user which model to use. The capability
 * tool exists for inspection, not for choosing.
 */
import fs from 'node:fs/promises'
import { createRequire } from 'node:module'
import path from 'node:path'
import process from 'node:process'
import { pathToFileURL } from 'node:url'

async function loadDefineTool() {
  try {
    return (await import('@deepseek-ai/dsh-tools')).defineTool
  } catch {
    const anchor = process.env.DSH_INSTALL_DIR || process.cwd()
    const require = createRequire(path.join(anchor, 'package.json'))
    const resolved = require.resolve('@deepseek-ai/dsh-tools')
    return (await import(pathToFileURL(resolved).href)).defineTool
  }
}

const defineTool = await loadDefineTool()

const API = ''

function mimeFor(file) {
  const ext = path.extname(file).toLowerCase()
  const map = {
    '.mp4': 'video/mp4',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    '.mkv': 'video/x-matroska',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
  }
  return map[ext] || 'application/octet-stream'
}

function engineBase(supervisor) {
  if (!supervisor?.url) throw new Error('AdClip 引擎尚未启动')
  return supervisor.url
}

async function ensureEngine(supervisor) {
  if (!supervisor?.status?.ok) {
    await supervisor?.start?.()
  }
  if (!supervisor?.status?.ok) {
    throw new Error(supervisor?.status?.detail || 'AdClip 引擎不可用，请到设置里检查运行时')
  }
  return engineBase(supervisor)
}

async function readJson(res) {
  const text = await res.text()
  let data = {}
  try { data = text ? JSON.parse(text) : {} } catch { data = { raw: text } }
  if (!res.ok) {
    const message = (data.error && (data.error.message || data.error.code)) || data.detail || `HTTP ${res.status}`
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return data
}

async function uploadAsset(supervisor, value, kind) {
  const text = String(value || '').trim()
  if (!text) throw new Error('素材路径为空')
  if (/^a_[0-9a-f]+$/i.test(text)) return text
  if (!path.isAbsolute(text)) throw new Error('请传绝对路径或 AdClip asset id')
  const base = await ensureEngine(supervisor)
  const raw = await fs.readFile(text)
  const name = path.basename(text)
  const res = await fetch(`${base}${API}/assets/upload?kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`, {
    method: 'POST',
    headers: { 'content-type': mimeFor(text), 'x-adplus-token': supervisor.token || '' },
    body: raw,
  })
  const data = await readJson(res)
  if (!data.asset?.id) throw new Error('素材上传没有返回 asset id')
  return data.asset.id
}

async function createRun(supervisor, body) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/runs`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-adplus-token': supervisor.token || '' },
    body: JSON.stringify(body),
  })
  return readJson(res)
}

async function getRun(supervisor, runId) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/runs/${encodeURIComponent(runId)}`, {
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

async function cancelRun(supervisor, runId) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/runs/${encodeURIComponent(runId)}/cancel`, {
    method: 'POST',
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

async function createImage(supervisor, body) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/images`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-adplus-token': supervisor.token || '' },
    body: JSON.stringify(body),
  })
  return readJson(res)
}

async function listAssets(supervisor, { kind = '', limit = 20 } = {}) {
  const base = await ensureEngine(supervisor)
  const qs = new URLSearchParams({ limit: String(Math.max(1, Math.min(60, Number(limit) || 20))) })
  if (kind) qs.set('kind', String(kind))
  const res = await fetch(`${base}${API}/assets?${qs.toString()}`, {
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

async function listPersonas(supervisor) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/personas`, {
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

async function stitchVideos(supervisor, body) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/stitch`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-adplus-token': supervisor.token || '' },
    body: JSON.stringify(body),
  })
  return readJson(res)
}

async function getAnalysis(supervisor, runId) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/runs/${encodeURIComponent(runId)}/analysis`, {
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

async function listCapabilities(supervisor) {
  const base = await ensureEngine(supervisor)
  const res = await fetch(`${base}${API}/capabilities`, {
    headers: { 'x-adplus-token': supervisor.token || '' },
  })
  return readJson(res)
}

function compactRun(run, detailed = true) {
  const result = run.result || {}
  const out = {
    run_id: run.id,
    status: run.status,
    step: run.step,
    progress: run.progress,
    error: run.error || '',
    selected_model: (run.selection || {}).model || result.model || '',
    selection_mode: (run.selection || {}).mode || '',
    video_path: result.video || '',
    image_path: result.image || '',
    asset_id: result.asset_id || '',
    srt_path: result.srt || '',
    qa_summary: result.qa?.summary || null,
    analysis_only: Boolean(result.analysis_only),
  }
  if (detailed) return out
  for (const key of ['step', 'progress', 'srt_path', 'qa_summary', 'analysis_only']) delete out[key]
  if (!out.video_path) delete out.video_path
  if (!out.image_path) delete out.image_path
  if (!out.asset_id) delete out.asset_id
  return out
}

function summaryText(data) {
  if (!data) return 'AdClip: no result'
  if (data.analysis_only) {
    return `AdClip run ${data.run_id} finished analysis only: ${data.error || 'no video model was available'}`
  }
  if (data.image_path) {
    return `AdClip image run ${data.run_id}: ${data.status} · model ${data.selected_model || '—'} · ${data.image_path}`
  }
  return `AdClip run ${data.run_id}: ${data.status} · model ${data.selected_model || '—'} (${data.selection_mode || '—'})${data.video_path ? ` · ${data.video_path}` : ''}`
}

export function registerAdclipTools(ctx, supervisor) {
  const disposers = []
  if (!ctx.tools) return () => {}

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_remake_video',
    description:
      'Start an AdClip viral remake from a reference video and optional product/persona images. '
      + 'Preserves the reference camera, scene, action, composition, rhythm and audio; replaces only the '
      + 'specified people/products unless the user explicitly overrides a scene element. The engine selects '
      + 'the best available model automatically; do not ask the user to choose a model. Returns a run id; '
      + 'poll with adclip_get_run.',
    parameters: {
      reference: { type: 'string', required: true, description: 'Absolute local path or AdClip asset id of the reference video (4–15s, ≤50MB).' },
      products: { type: 'array', items: { type: 'string' }, description: 'Absolute image paths or asset ids; first is the main product, max 3.' },
      personas: { type: 'array', items: { type: 'string' }, description: 'Absolute image paths or asset ids for the replacement person(s), max 3.' },
      brief: { type: 'string', description: 'Product, selling points, price and explicit change requests.' },
      explicit_overrides: { type: 'string', description: 'Only when the user explicitly asks to change a scene, prop, action or line.' },
      replace_scope: { type: 'string', enum: ['both', 'product', 'person'], description: 'What to replace; default both.' },
      person_scope: { type: 'string', enum: ['main', 'all'], description: 'Replace the main person or all people; default main.' },
      wait_seconds: { type: 'integer', description: '0 returns immediately; 1–90 waits up to that many seconds.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
          selected_model: { type: 'string', required: true },
          selection_mode: { type: 'string', required: true },
          selection_reason: { type: 'string', required: true },
          analysis: {
            type: 'object',
            additionalProperties: false,
            properties: {
              shots: { type: 'integer', required: true },
              product: { type: 'string', required: true },
              cast: { type: 'array', required: true, items: { type: 'string' } },
              preserve: { type: 'array', required: true, items: { type: 'string' } },
            },
          },
          video_path: { type: 'string' },
          image_path: { type: 'string' },
          asset_id: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: summaryText(value) }],
    },
    async execute(args) {
      await ensureEngine(supervisor)
      const referenceId = await uploadAsset(supervisor, args.reference, 'video')
      const productIds = []
      for (const value of (args.products || []).slice(0, 3)) productIds.push(await uploadAsset(supervisor, value, 'image'))
      const personaIds = []
      for (const value of (args.personas || []).slice(0, 3)) personaIds.push(await uploadAsset(supervisor, value, 'image'))
      const scope = String(args.replace_scope || 'both')
      if (scope !== 'person' && !productIds.length) throw new Error('替换商品需要至少一张商品图')
      if (scope !== 'product' && !personaIds.length) throw new Error('替换人物需要至少一张模特图')
      const data = await createRun(supervisor, {
        scenario: 'viral-remake',
        inputs: {
          reference_asset_id: referenceId,
          product_asset_ids: productIds,
          persona_asset_ids: personaIds,
          brief: String(args.brief || ''),
          explicit_overrides: String(args.explicit_overrides || ''),
        },
        advanced: {
          model: 'auto',
          remake_mode: 'auto',
          replace_scope: String(args.replace_scope || 'both'),
          person_scope: String(args.person_scope || 'main'),
          persona: personaIds.length ? { reference_images: personaIds } : undefined,
        },
      })
      const created = data.run || {}
      let final = created
      const wait = Math.max(0, Math.min(90, Number(args.wait_seconds) || 0))
      if (wait > 0 && created.id) {
        const deadline = Date.now() + wait * 1000
        while (Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          try {
            const next = await getRun(supervisor, created.id)
            final = next.run || final
            if (['succeeded', 'failed', 'canceled'].includes(final.status)) break
          } catch {
            break
          }
        }
      }
      const selection = final.selection || created.selection || {}
      let analysis = { shots: 0, product: '', cast: [], preserve: [] }
      if (wait > 0 && final.id) {
        try {
          const doc = await getAnalysis(supervisor, final.id)
          const shots = (doc.remake_plan && doc.remake_plan.shots) || []
          const products = shots.map((shot) => String((shot.product || {}).name || '').trim()).filter(Boolean)
          const casts = shots.flatMap((shot) => (shot.cast || []).map((item) => String(item.description || '').trim())).filter(Boolean)
          analysis = {
            shots: shots.length,
            product: products[0] || '',
            cast: [...new Set(casts)].slice(0, 4),
            preserve: ((doc.remake_plan || {}).global || {}).preserve || [],
          }
        } catch { /* analysis is best-effort */ }
      }
      return {
        run_id: final.id || created.id || '',
        status: final.status || created.status || 'queued',
        selected_model: selection.model || '',
        selection_mode: selection.mode || '',
        selection_reason: selection.reason || '',
        analysis,
        video_path: (final.result || {}).video || '',
        error: final.error || '',
      }
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_create_image',
    description:
      'Create an image from a text prompt with optional reference images. The engine picks the image model '
      + 'automatically; use this for posters, product shots and concept images. Returns a run id; poll with adclip_get_run.',
    parameters: {
      prompt: { type: 'string', required: true, description: 'Complete image description: subject, composition, style, lighting.' },
      aspect: { type: 'string', enum: ['1:1', '9:16', '16:9', '4:3', '3:4', '2:3', '3:2'], description: 'Optional; defaults to 1:1.' },
      area: { type: 'string', enum: ['1K', '2K', '4K'], description: 'Optional output area; defaults to 2K.' },
      reference_images: { type: 'array', items: { type: 'string' }, description: 'Optional; the first absolute image path or asset id is used as reference.' },
      wait_seconds: { type: 'integer', description: '0 returns immediately; 1–90 waits up to that many seconds.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
          selected_model: { type: 'string', required: true },
          selection_mode: { type: 'string', required: true },
          image_path: { type: 'string' },
          asset_id: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: summaryText(value) }],
    },
    async execute(args) {
      await ensureEngine(supervisor)
      const referenceIds = []
      for (const value of (args.reference_images || []).slice(0, 1)) referenceIds.push(await uploadAsset(supervisor, value, 'image'))
      const data = await createImage(supervisor, {
        prompt: String(args.prompt || ''),
        aspect: String(args.aspect || '1:1'),
        area: String(args.area || '2K'),
        reference_asset_id: referenceIds[0] || '',
      })
      const created = data.run || {}
      let final = created
      const wait = Math.max(0, Math.min(90, Number(args.wait_seconds) || 0))
      if (wait > 0 && created.id) {
        const deadline = Date.now() + wait * 1000
        while (Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
          try {
            const next = await getRun(supervisor, created.id)
            final = next.run || final
            if (['succeeded', 'failed', 'canceled'].includes(final.status)) break
          } catch { break }
        }
      }
      return compactRun(final, false)
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_list_assets',
    description: 'List AdClip assets (uploaded images, videos, audio) so the agent can reuse a reference instead of asking the user to re-upload.',
    parameters: {
      kind: { type: 'string', enum: ['image', 'video', 'audio'], description: 'Optional asset kind filter.' },
      limit: { type: 'integer', description: '1–60; defaults to 20.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          assets: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string', required: true },
                name: { type: 'string' },
                kind: { type: 'string' },
                path: { type: 'string' },
                duration_s: { type: 'number' },
                width: { type: 'integer' },
                height: { type: 'integer' },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.assets.map((a) => `${a.id} · ${a.kind} · ${a.name}`).join('\n') || '没有素材' }],
    },
    async execute(args) {
      const data = await listAssets(supervisor, { kind: String(args.kind || ''), limit: Number(args.limit) || 20 })
      return {
        assets: (data.assets || []).map((asset) => ({
          id: asset.id,
          name: asset.name || '',
          kind: asset.kind || '',
          path: asset.path || '',
          duration_s: Number(asset.duration_s) || 0,
          width: Number(asset.width) || 0,
          height: Number(asset.height) || 0,
        })),
      }
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_list_personas',
    description: 'List saved AdClip personas so the agent can reuse an approved person in a video.',
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          personas: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string', required: true },
                name: { type: 'string' },
                gender: { type: 'string' },
                age: { type: 'string' },
                body_type: { type: 'string' },
                ethnicity: { type: 'string' },
              },
            },
          },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.personas.map((p) => `${p.id} · ${p.name}`).join('\n') || '没有模特' }],
    },
    async execute() {
      const data = await listPersonas(supervisor)
      return {
        personas: (data.personas || []).map((persona) => ({
          id: persona.id,
          name: persona.name || '',
          gender: persona.gender || '',
          age: persona.age || '',
          body_type: persona.body_type || '',
          ethnicity: persona.ethnicity || '',
        })),
      }
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_create_video',
    description:
      'Create a free-form video from a text description and optional reference images. The engine picks the '
      + 'model automatically and defaults to 9:16 / 8s / 720p when the user did not specify a format. '
      + 'Returns a run id; poll with adclip_get_run.',
    parameters: {
      brief: { type: 'string', required: true, description: 'What the video should show: subject, scene, action, camera, product.' },
      reference_images: { type: 'array', items: { type: 'string' }, description: 'Optional absolute image paths or AdClip asset ids (max 4).' },
      aspect: { type: 'string', enum: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9'], description: 'Optional; defaults to 9:16.' },
      duration: { type: 'integer', description: 'Optional seconds; defaults to 8.' },
      resolution: { type: 'string', enum: ['480p', '720p', '1080p'], description: 'Optional; defaults to 720p.' },
      subtitle: { type: 'string', enum: ['off', 'sidecar'], description: 'Optional; defaults to off.' },
      wait_seconds: { type: 'integer', description: '0 returns immediately; 1–90 waits up to that many seconds.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
          selected_model: { type: 'string', required: true },
          selection_mode: { type: 'string', required: true },
          video_path: { type: 'string' },
          image_path: { type: 'string' },
          asset_id: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: summaryText(value) }],
    },
    async execute(args) {
      await ensureEngine(supervisor)
      const imageIds = []
      for (const value of (args.reference_images || []).slice(0, 4)) imageIds.push(await uploadAsset(supervisor, value, 'image'))
      const advanced = { model: 'auto' }
      if (args.aspect) advanced.aspect = String(args.aspect)
      if (args.duration) advanced.duration = Number(args.duration)
      if (args.resolution) advanced.resolution = String(args.resolution)
      if (args.subtitle) advanced.subtitle = String(args.subtitle)
      const data = await createRun(supervisor, {
        scenario: 'text-to-video',
        inputs: { brief: String(args.brief || ''), reference_image_asset_id: imageIds[0] || null },
        advanced,
      })
      const created = data.run || {}
      let final = created
      const wait = Math.max(0, Math.min(90, Number(args.wait_seconds) || 0))
      if (wait > 0 && created.id) {
        const deadline = Date.now() + wait * 1000
        while (Date.now() < deadline) {
          await new Promise((resolve) => setTimeout(resolve, 2000))
          try {
            const next = await getRun(supervisor, created.id)
            final = next.run || final
            if (['succeeded', 'failed', 'canceled'].includes(final.status)) break
          } catch {
            break
          }
        }
      }
      return compactRun(final, false)
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_stitch_videos',
    description:
      'Stitch two or more local videos in order. This is the only stitching surface; the AdClip UI does not expose '
      + 'stitching. Returns the completed stitch run.',
    parameters: {
      clips: { type: 'array', required: true, items: { type: 'string' }, description: 'Absolute video paths or AdClip asset ids, in order (at least 2).' },
      aspect: { type: 'string', enum: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9'], description: 'Output aspect; default 9:16.' },
      resolution: { type: 'string', enum: ['480p', '720p', '1080p'], description: 'Output resolution; default 720p.' },
      fit: { type: 'string', enum: ['blur_pad', 'black_pad', 'crop'], description: 'Fit mode; default blur_pad.' },
      transition: { type: 'string', enum: ['cut', 'fade'], description: 'Transition; default cut.' },
      audio: { type: 'string', enum: ['keep', 'mute'], description: 'Audio handling; default keep.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
          selected_model: { type: 'string' },
          selection_mode: { type: 'string' },
          video_path: { type: 'string' },
          image_path: { type: 'string' },
          asset_id: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.video_path ? `拼接完成：${value.video_path}` : '拼接完成' }],
    },
    async execute(args) {
      await ensureEngine(supervisor)
      const clips = Array.isArray(args.clips) ? args.clips : []
      if (clips.length < 2) throw new Error('至少需要两段视频才能拼接')
      const assetIds = []
      for (const value of clips) assetIds.push(await uploadAsset(supervisor, value, 'video'))
      const data = await stitchVideos(supervisor, {
        clips: assetIds.map((asset_id) => ({ asset_id, in_s: 0 })),
        output: { aspect: String(args.aspect || '9:16'), resolution: String(args.resolution || '720p') },
        fit: String(args.fit || 'blur_pad'),
        transition: String(args.transition || 'cut'),
        audio: String(args.audio || 'keep'),
      })
      return compactRun(data.run || {}, false)
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_get_run',
    description: 'Read an AdClip run: status, progress, selected model, final video path and QA summary. Use after adclip_remake_video.',
    parameters: {
      run_id: { type: 'string', required: true, description: 'Run id returned by adclip_remake_video.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
          step: { type: 'string', required: true },
          progress: { type: 'number', required: true },
          error: { type: 'string' },
          selected_model: { type: 'string' },
          selection_mode: { type: 'string' },
          video_path: { type: 'string' },
          image_path: { type: 'string' },
          asset_id: { type: 'string' },
          srt_path: { type: 'string' },
          qa_summary: { type: 'json' },
          analysis_only: { type: 'boolean' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: summaryText(value) }],
    },
    async execute(args) {
      const data = await getRun(supervisor, String(args.run_id))
      return compactRun(data.run || {})
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_list_capabilities',
    description: 'List the AdClip model capability registry for inspection: video/image generation models, Doubao-Seed-2.1 text/vision rows with their capability tags, and the vision fallback ladder (scheduling.vision). Not for manual model selection; adclip_remake_video chooses automatically.',
    parameters: {
      kind: { type: 'string', enum: ['video', 'image', 'text', 'vision'], description: 'Optional model kind filter.' },
      remake_only: { type: 'boolean', description: 'Only show models that can participate in a remake.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          models: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string', required: true },
                label: { type: 'string', required: true },
                provider: { type: 'string', required: true },
                tier: { type: 'string', required: true },
                available: { type: 'boolean', required: true },
                enabled: { type: 'boolean', required: true },
                inputs: { type: 'json' },
                params: { type: 'json' },
                outputs: { type: 'json' },
                supports: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          text_models: { type: 'array', items: { type: 'json' } },
          scheduling: { type: 'json' },
        },
      },
      render: (_args, value) => {
        const lines = value.models.map((m) => `${m.id} · ${m.tier} · ${m.available ? '可用' : '不可用'}`)
        const texts = (value.text_models || []).map((m) => `${m.id} · ${(m.tags || []).join('/')} · ${m.available ? '可用' : '不可用'}`)
        const chain = ((value.scheduling || {}).vision || []).map((m, index) => `${index + 1}. ${m.label}${m.available ? '' : '（不可用）'}`)
        return [{
          type: 'text',
          text: [
            lines.length ? lines.join('\n') : '没有生成模型',
            texts.length ? `文本/视觉模型：\n${texts.join('\n')}` : '',
            chain.length ? `视觉降级链：${chain.join(' → ')}` : '',
          ].filter(Boolean).join('\n'),
        }]
      },
    },
    async execute(args) {
      const data = await listCapabilities(supervisor)
      const kind = String(args.kind || '')
      const remakeOnly = Boolean(args.remake_only)
      const models = (data.models || [])
        .filter((m) => !kind || m.kind === kind)
        .filter((m) => !remakeOnly || ['full', 'reference', 'generation'].includes((m.remake || {}).tier))
        .map((m) => ({
          id: m.id,
          label: m.label || m.id,
          provider: m.provider || '',
          tier: (m.remake || {}).tier || '',
          available: Boolean(m.available),
          enabled: m.enabled !== false,
          inputs: m.io || {},
          params: m.params || {},
          outputs: m.output || {},
          supports: (m.remake || {}).supports || [],
        }))
      const textModels = ['', 'text', 'vision'].includes(kind)
        ? (data.text_models || []).map((m) => ({
            id: m.id,
            label: m.label || m.id,
            provider: m.provider || '',
            ark_model: m.ark_model || '',
            tags: m.tags || [],
            available: Boolean(m.available),
            status: m.status || '',
            reason: m.reason || '',
          }))
        : []
      return { models, text_models: textModels, scheduling: data.scheduling || { vision: [] } }
    },
  })))


  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_get_analysis',
    description: 'Read the reference breakdown for an AdClip run: shots, camera/scene/action, product, cast and the preserve/replace contract.',
    parameters: {
      run_id: { type: 'string', required: true, description: 'Run id returned by adclip_remake_video.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          available: { type: 'boolean', required: true },
          mode: { type: 'string' },
          degraded: { type: 'boolean' },
          provider: { type: 'string' },
          model: { type: 'string' },
          reason: { type: 'string' },
          shots: { type: 'array', required: true, items: { type: 'json' } },
          product: { type: 'string' },
          cast: { type: 'array', items: { type: 'string' } },
          preserve: { type: 'array', items: { type: 'string' } },
          warnings: { type: 'array', items: { type: 'string' } },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.available
          ? `拆解：${value.shots.length} 镜 · 商品 ${value.product || '—'} · 人物 ${(value.cast || []).join('、') || '—'} · 视觉 ${value.provider || '启发式'}${value.model ? '/' + value.model : ''}`
          : '还没有拆解数据',
      }],
    },
    async execute(args) {
      const doc = await getAnalysis(supervisor, String(args.run_id))
      const plan = doc.remake_plan || {}
      const shots = plan.shots || []
      const products = shots.map((shot) => String((shot.product || {}).name || '').trim()).filter(Boolean)
      const casts = shots.flatMap((shot) => (shot.cast || []).map((item) => String(item.description || '').trim())).filter(Boolean)
      return {
        available: Boolean(doc.available),
        mode: (doc.analysis || {}).mode || '',
        degraded: Boolean((doc.analysis || {}).degraded),
        provider: (doc.analysis || {}).provider || '',
        model: (doc.analysis || {}).model || '',
        reason: (doc.analysis || {}).reason || '',
        shots,
        product: products[0] || '',
        cast: [...new Set(casts)].slice(0, 4),
        preserve: (plan.global || {}).preserve || [],
        warnings: (plan.global || {}).warnings || [],
      }
    },
  })))

  disposers.push(ctx.tools.register(defineTool({
    name: 'adclip_cancel_run',
    description: 'Cancel a queued or running AdClip run.',
    parameters: {
      run_id: { type: 'string', required: true },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          run_id: { type: 'string', required: true },
          status: { type: 'string', required: true },
        },
      },
      render: (_args, value) => [{ type: 'text', text: `${value.run_id}: ${value.status}` }],
    },
    async execute(args) {
      await cancelRun(supervisor, String(args.run_id))
      return { run_id: String(args.run_id), status: 'canceled' }
    },
  })))

  return () => {
    for (const dispose of disposers) {
      try { dispose?.() } catch { /* already gone */ }
    }
  }
}

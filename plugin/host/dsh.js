/** Read the host's configured LLM catalogue and, optionally, run a text call.
 *
 * DSH already owns model routing and credentials. AdClip should not ask the user
 * to re-enter an LLM key for copy/analysis when a DSH model is configured.
 * Video generation is different: DSH exposes LLM calls, not video tasks.
 */
export function createDshBridge(ctx) {
  const llm = ctx.get('llm')
  const defaults = ctx.get('agentDefaultModel')

  async function list() {
    if (!llm) return { available: false, providers: [], reason: 'llm service not mounted' }
    const providers = []
    for (const provider of llm.listProviders()) {
      try {
        const models = await llm.listModels(provider.id)
        providers.push({ id: provider.id, name: provider.name, models })
      } catch (error) {
        providers.push({ id: provider.id, name: provider.name, models: [], error: String(error?.message || error) })
      }
    }
    let selection = null
    try { selection = defaults?.currentSelection?.() || null } catch { selection = null }
    return { available: true, providers, selection }
  }

  async function chat({ provider, model, system, messages, maxTokens = 1200 }) {
    if (!llm) throw new Error('DSH llm service is not mounted')
    let selectedProvider = provider
    let selectedModel = model
    if ((!selectedProvider || !selectedModel) && defaults?.currentSelection) {
      const selection = defaults.currentSelection()
      selectedProvider = selectedProvider || selection.provider
      selectedModel = selectedModel || selection.model
    }
    if (!selectedProvider || !selectedModel) {
      const first = (await list()).providers.find((p) => (p.models || []).length)
      if (!first) throw new Error('no DSH model is configured')
      selectedProvider = first.id
      selectedModel = first.models[0].id
    }
    const request = {
      provider: selectedProvider,
      model: selectedModel,
      system,
      maxTokens,
      messages: (messages && messages.length ? messages : [{ role: 'user', content: [{ type: 'text', text: '你好' }] }]),
    }
    let text = ''
    for await (const chunk of llm.stream(request)) {
      if (chunk.type === 'text-delta') text += chunk.text
      if (chunk.type === 'finish' && chunk.reason && chunk.reason.kind === 'error') {
        throw new Error(chunk.reason.failure?.message || 'DSH model call failed')
      }
    }
    return { provider: selectedProvider, model: selectedModel, text }
  }

  async function vision({ frames, prompt, maxTokens = 1200 }) {
    if (!llm) throw new Error('DSH llm service is not mounted')
    const attachments = ctx.get('attachments')
    if (!attachments) throw new Error('DSH attachment service is not mounted')
    const configuredMax = Math.min(12, Number(attachments.imageLimits?.maxImagesPerMessage) || 12)
    const requested = Array.isArray(frames) ? frames.slice(0, configuredMax) : []
    if (!requested.length) throw new Error('vision frames are required')
    if (!requested.every((frame) => frame && typeof frame.data === 'string' && frame.data.length > 0)) {
      throw new Error('vision frames need base64 data')
    }
    const catalogue = await list()
    const models = (catalogue.providers || []).flatMap((provider) =>
      (provider.models || []).map((model) => ({
        provider: provider.id,
        id: model.id,
        name: model.name || model.id,
        image: (model.inputModalities || []).includes('image'),
      })),
    )
    const imageModels = models.filter((model) => model.image)
    if (!imageModels.length) throw new Error('no DSH model accepts image input')
    let selection = null
    try { selection = defaults?.currentSelection?.() || null } catch { selection = null }
    const current = selection && imageModels.find((model) => model.provider === selection.provider && model.id === selection.model)
    const preferred = current
      || imageModels.find((model) => model.id === 'deepseek-flash')
      || imageModels[0]
    const admitted = await attachments.admitPromptContent([
      { type: 'text', text: String(prompt || '') },
      ...requested.map((frame, index) => ({
        type: 'image',
        mediaType: String(frame.mediaType || 'image/jpeg'),
        data: String(frame.data),
        name: String(frame.name || `${frame.id || `frame${index}`}.jpg`),
      })),
    ])
    const system = '你是广告分镜视觉标签器。只输出 JSON，不要解释，不要 markdown。'
    let text = ''
    for await (const chunk of llm.stream({
      provider: preferred.provider,
      model: preferred.id,
      system,
      messages: [{ role: 'user', content: admitted }],
      maxTokens,
    })) {
      if (chunk.type === 'text-delta') text += chunk.text
      if (chunk.type === 'finish' && chunk.reason && chunk.reason.kind === 'error') {
        throw new Error(chunk.reason.failure?.message || 'DSH vision call failed')
      }
    }
    return { provider: preferred.provider, model: preferred.id, text }
  }

  return { list, chat, vision }
}

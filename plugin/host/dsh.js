/** Read the host's configured LLM catalogue and, optionally, run a text call.
 *
 * DSH already owns model routing and credentials. Ad+ should not ask the user
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

  return { list, chat }
}

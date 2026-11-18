# 模型能力与目录

## 一句话

所有模型都在 `src/adclip/catalog.py` 里声明；每行的能力、输入、输出、参数、复刻等级和默认值在 `src/adclip/capabilities.py` 里定义。设置页显示成能力/参数详情，生成页按能力过滤；爆款复刻不再让用户选模型，由 `src/adclip/remake_planner.py` 按注册表自动选型。

## 能力词表（固定）

| 能力 | 含义 |
|---|---|
| `text_to_video` | 文生视频 |
| `image_to_video` | 图生视频（需要上传参考图） |
| `reference_to_video` | 参考视频重制（爆款复刻） |
| `text_to_image` | 文生图片 |
| `image_to_image` | 参考图生图（从素材库选一张参考图） |

每行还可以声明 `native_audio`、`durations`、`resolutions`、`aspects`、`areas`、`default_area`、`requires`（环境变量形式的 key）、`adapter_ready`、`tags`（仅展示）、`reason`（仅 tooltip）。

`capabilities.py` 额外给出：

| 字段 | 含义 |
|---|---|
| `io` | 输入类型、角色、数量、时长、大小上限 |
| `params` | 可调参数（时长、分辨率、比例、音频、水印等）和枚举/范围/默认值 |
| `output` | 视频/音频/图片输出 |
| `remake.tier` | `full` / `reference` / `generation` / `image_only` |
| `remake.supports` | `reference_video`、`person_replace`、`product_replace`、`audio_preserve` 等 |
| `remake.real_person_reference` | `allowed` / `restricted` / `unknown` |
| `remake.cost_weight` / `priority` | 内部选型权重，不展示金额 |
| `default_params` | 可被 Settings 覆盖的默认参数 |

## 可用性与启用

- `available` = `adapter_ready` 且 `requires` 里的 key 都已配置（`demo` 这类无 key 的行除外）。
- `enabled` 来自 `data/model_prefs.json` 的 id 列表；某个 kind 在列表里一个 id 都没有时视为"该类全部启用"（兼容旧偏好文件）。
- 设置页的勾选只影响生成页的候选，不影响历史任务。

## 生成页的过滤规则

| 页面 | 过滤条件 |
|---|---|
| 爆款复刻 | 自动选型：`full` → `reference` → `generation`；用户不选模型 |
| 自由创作（视频） | `text_to_video`；只有 `image_to_video` 的模型继续走"必须上传图"分支 |
| 自由创作（文生图片） | `kind == "image"` 且 `text_to_image` |

爆款复刻的候选顺序：

1. `minimax.h3`（`full`）：参考视频 + 参考图 + 原声，完整复刻。
2. Seedance 2.5 / 2.0（`reference`）：H3 不可用且允许参考生成时；真人参考仍受方舟风控。
3. Seedance 2.0 Fast / Mini（`generation`）：不把真人参考视频发给模型，只按分析/脚本重建。
4. 没有视频模型：只返回拆解（`analysis_only`）。

Hailuo 2.3 Fast 只有图生视频，不进入复刻候选。

## 加一个模型

1. 在 `catalog.py` 的 `VIDEO_ROWS` / `IMAGE_ROWS` 里加一行：`id`、`kind`、`provider`、`model`（厂商侧 id）、`capabilities`、参数域、`requires`、`adapter_ready`。
2. 在 `capabilities.py` 加同 id 的 `io/params/output/remake/quality/default_params`；设置页、自动选型和 DSH 工具会读取它。
3. 同厂商已有适配器（ark / kling / minimax）时只做这两步即可。
4. 新厂商才需要适配器：
   - 视频：`src/adclip/providers/<name>.py` 实现 `generate(...)`，在 `pipeline/generate.py::PROVIDERS` 注册 provider 名；
   - 图片：实现 `generate(prompt, *, model, aspect, area, output, reference=None)`，在 `pipeline/image_runner.py::IMAGE_PROVIDERS` 注册。

## Doubao-Seed-2.1（火山方舟）文本 / 视觉

这三个模型不是视频/图片生成模型，因此**不在** `VIDEO_ROWS` / `IMAGE_ROWS` 里，
而是 `src/adclip/providers/ark_text.py` 的 `ROWS`，由 `catalog.text_rows()` 暴露：

| 行 id | 方舟 model | 能力标签 | 上下文 |
|---|---|---|---|
| `ark.doubao-seed-2.1-pro` | `doubao-seed-2-1-pro-260915` | 多模态模型 / 深度思考 / 视觉理解 | 1M |
| `ark.doubao-seed-2.1-turbo` | `doubao-seed-2-1-turbo-260628` | 同上 | — |
| `ark.doubao-seed-2.1-lite` | `doubao-seed-2-1-lite-260915` | 同上 | — |

调用方式：`POST {ARK_BASE}/chat/completions`（`https://ark.cn-beijing.volces.com/api/v3`），
`Authorization: Bearer $ARK_API_KEY`，图片用 `content` 里的
`{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,..."}}`，
深度思考用 `thinking: {"type":"enabled"|"disabled"}`（pro/turbo 默认开启，视觉链路强制关闭）。

引擎路由：

| 路由 | 用途 |
|---|---|
| `GET /text/models` | 三个模型 + `available/status/reason/checked_at` |
| `POST /text/chat` | 自由创作对话（只接受 `provider=ark`），返回 `{text,provider,model,usage}` |
| `POST /text/models/probe` | 1 token 探测是否开通，结果缓存到 `data/text_models_state.json`（`ok` 24h，`not_open` 10 分钟）。刚开通时方舟会有几台副本仍回 `ModelNotOpen`，`chat()` 自动重试 3 次（1.5s/4s），且已确认 `ok` 的模型不会被单次 404 降级 |

模型未开通时方舟返回 `404 ModelNotOpen`：引擎把它翻译成“模型未开通，请去控制台开通”，
缓存状态后视觉链跳过它，文本生成回落 DSH，不阻塞任何 run。

## 参考片拆解视觉链

`catalog.vision_chain()` 是唯一定义，顺序固定：

1. `minimax.m3`（`MINIMAX_API_KEY`）
2. `ark.doubao-seed-2.1-pro` → `turbo` → `lite`（`ADSTUDIO_VISION_ARK_ORDER` 可改，已判定
   `not_open` 的会跳过）
3. `dsh.vision`（Host `/adplus/api/dsh/vision`，选第一个 `inputModalities` 含 `image` 的 DSH 模型）
4. `heuristic`（永远可用）

任何一步成功即停止；失败只累计原因，最终 `analysis.provider/model` 记录实际来源，
`analysis.warnings` 记录降级原因。同一条链通过 `GET /capabilities` 的
`scheduling.vision`、`adclip_list_capabilities` 工具和设置页展示，改顺序只改
`catalog.vision_chain()`。

## DSH 工具

`plugin/host/tools.js` 通过 `@deepseek-ai/dsh-tools` 的 `defineTool` 暴露：

- `adclip_remake_video`：唯一复刻入口，自动选型，返回 run id。
- DSH 视觉回退：MiniMax-M3 不可用时，Host `/dsh/vision` 自动选 `inputModalities` 含 `image` 的 DSH 模型，处理关键帧标签。
- `adclip_create_image`：图片生成入口，自动选图片模型。
- `adclip_create_video`：自由创作视频入口，未指定格式时默认 9:16 / 8s / 720p。
- `adclip_list_assets` / `adclip_list_personas`：让 agent 复用已上传素材/模特。
- `adclip_stitch_videos`：唯一拼接入口，UI 不再暴露拼接。
- `adclip_get_run`：状态、进度、选中模型、成片路径、QA 摘要。
- `adclip_get_analysis`：整片拆解（分镜、商品、人物、保留/替换），同时回传
  `provider/model/degraded`，让 agent 知道这次是谁做的视觉标签。
- `adclip_list_capabilities`：只读能力注册表；`kind=text|vision` 时可查
  Doubao 行与 `scheduling.vision` 降级链。
- `adclip_cancel_run`：取消任务。

`plugin/index.js` 注入三段系统提示词：`adclip:remake-guidance`（爆款复刻保留契约）、
`adclip:vision-guidance`（视觉链顺序 + 用 `provider/model` 汇报，不要问用户选模型）、
`adclip:free-create-guidance`（图片/视频/拼接/素材工具）。三段互不混写。

## 无价格约束

本仓库不新增价格、报价、计费 UI 或 API。`cost_weight` 只是内部排序权重，不代表金额。

## 测试模式

`ADCLIP_TEST_MODE=1` 时目录里会额外注入一条 `test.synthetic`（provider `synthetic`），生成走本地合成视频，`tests/smoke.py` 用它端到端跑而不需要真实 key。产品环境不会出现这一行。

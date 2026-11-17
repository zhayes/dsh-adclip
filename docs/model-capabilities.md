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

## DSH 工具

`plugin/host/tools.js` 通过 `@deepseek-ai/dsh-tools` 的 `defineTool` 暴露：

- `adclip_remake_video`：唯一复刻入口，自动选型，返回 run id。
- `adclip_create_image`：图片生成入口，自动选图片模型。
- `adclip_create_video`：自由创作视频入口，未指定格式时默认 9:16 / 8s / 720p。
- `adclip_list_assets` / `adclip_list_personas`：让 agent 复用已上传素材/模特。
- `adclip_stitch_videos`：唯一拼接入口，UI 不再暴露拼接。
- `adclip_get_run`：状态、进度、选中模型、成片路径、QA 摘要。
- `adclip_get_analysis`：整片拆解（分镜、商品、人物、保留/替换）。
- `adclip_list_capabilities`：只读能力注册表。
- `adclip_cancel_run`：取消任务。

`plugin/index.js` 同时注入一段“AdClip 爆款复刻模式”系统提示词：保持镜头/场景/动作/构图/节奏/声音，只换人物/商品，显式要求除外；不要在对话里询问用户选模型。

## 无价格约束

本仓库不新增价格、报价、计费 UI 或 API。`cost_weight` 只是内部排序权重，不代表金额。

## 测试模式

`ADCLIP_TEST_MODE=1` 时目录里会额外注入一条 `test.synthetic`（provider `synthetic`），生成走本地合成视频，`tests/smoke.py` 用它端到端跑而不需要真实 key。产品环境不会出现这一行。

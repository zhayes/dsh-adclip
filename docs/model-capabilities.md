# 模型能力与目录

## 一句话

所有模型都在 `src/adclip/catalog.py` 里声明；每行带 `kind`（`video` / `image`）和 `capabilities`，设置页显示成标签，生成页按能力过滤。**没有任何地方按模型 id 判断能力。**

## 能力词表（固定）

| 能力 | 含义 |
|---|---|
| `text_to_video` | 文生视频 |
| `image_to_video` | 图生视频（需要上传参考图） |
| `reference_to_video` | 参考视频重制（爆款复刻） |
| `text_to_image` | 文生图片 |
| `image_to_image` | 参考图生图（从素材库选一张参考图） |

每行还可以声明 `native_audio`、`durations`、`resolutions`、`aspects`、`areas`、`default_area`、`requires`（环境变量形式的 key）、`adapter_ready`、`tags`（仅展示）、`reason`（仅 tooltip）。

## 可用性与启用

- `available` = `adapter_ready` 且 `requires` 里的 key 都已配置（`demo` 这类无 key 的行除外）。
- `enabled` 来自 `data/model_prefs.json` 的 id 列表；某个 kind 在列表里一个 id 都没有时视为"该类全部启用"（兼容旧偏好文件）。
- 设置页的勾选只影响生成页的候选，不影响历史任务。

## 生成页的过滤规则

| 页面 | 过滤条件 |
|---|---|
| 爆款复刻 | `reference_to_video` |
| 自由创作（视频） | `text_to_video`；只有 `image_to_video` 的模型继续走"必须上传图"分支 |
| 自由创作（文生图片） | `kind == "image"` 且 `text_to_image` |

## 加一个模型

1. 在 `catalog.py` 的 `VIDEO_ROWS` / `IMAGE_ROWS` 里加一行：`id`、`kind`、`provider`、`model`（厂商侧 id）、`capabilities`、参数域、`requires`、`adapter_ready`。
2. 同厂商已有适配器（ark / kling / minimax）时只做这一步即可，设置页、生成页、过滤全部自动生效。
3. 新厂商才需要适配器：
   - 视频：`src/adclip/providers/<name>.py` 实现 `generate(...)`，在 `pipeline/generate.py::PROVIDERS` 注册 provider 名；
   - 图片：实现 `generate(prompt, *, model, aspect, area, output, reference=None)`，在 `pipeline/image_runner.py::IMAGE_PROVIDERS` 注册。

## 测试模式

`ADCLIP_TEST_MODE=1` 时目录里会额外注入一条 `test.synthetic`（provider `synthetic`），生成走本地合成视频，`tests/smoke.py` 用它端到端跑而不需要真实 key。产品环境不会出现这一行。

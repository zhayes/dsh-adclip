# UI references and current layout

## What we borrowed

- **Shopify product media grid**: multiple product images, square thumbnails,
  add tile, remove-on-hover. Replaced the single oversized product image.
- **Creatify / Arcads ad creation**: two primary asset slots, one plain-language
  brief, advanced settings kept out of the main path, one primary action.
- **Tencent Cloud MPS scene page**: scenario tabs and a form-first task page,
  not a project/step wizard.
- **Canva asset panel**: small media tiles with an obvious add affordance.
- **Linear / Stripe forms**: section numbering, utility labels, tabular numbers
  for durations/parameters, calm surfaces, one accent for active state.
- **DSH theme tokens**: containers/controls inherit `--dsw-alias-*`; the warm
  amber is a scene/index accent, not a second theme.

## Current structure

```text
SCENE 01 / VIRAL REMAKE
爆款复刻
[素材 01]  reference 9:16 drop, product media grid 3x3, asset guidance
[需求 02]  brief textarea, char count, rights checkbox
[设置 03]  mode / duration / aspect, resolution / model
[模特 04]  gender / age / body / ethnicity
[action]   demo/model note + primary start button
[示例 05]  price / talking-head / unboxing starter prompts
```

`docs/images/ui-recreate-v2.png` is a static React SSR preview at
1512x1126. The live page gets the real engine badge and real media thumbnails.

## What not to copy

- Do not copy Tencent's console/API-doc density.
- Do not put pricing or quote steps in the main path.
- Do not turn the form into a chat; the assistant is a drawer.
- Do not use a full-screen media library when a compact grid is enough for
  the first 9 product images.

## Result page (2026-11 layout pass)

- The result is a dedicated view, not a card stacked above the creation form.
- Top: back, title/status, then a 9:16 stage on the left and a compact
  "成片操作 / 成片信息 / 质量检查" rail on the right.
- Actions are icon+label buttons: 修改参数, 再生成, 下载. "修改参数" opens a
  right drawer with 比例/清晰度/时长; "应用并重生成" is disabled until a value
  actually changes.
- "再生成" means same parameters, new take. "修改参数" means a new version with
  deliberately changed generation settings. The distinction is stated in the
  rail so the two controls do not look redundant.
- Storyboard is a vertical list: frame on the left, function/time/dialogue/action
  on the right, per-row 编辑 button. Editing opens inline chat for that shot
  instead of a detached assistant panel.
- Detail also keeps the original brief and the reference/product/persona inputs
  in a dedicated 创作输入 section, so a generated version is reproducible.
- Preview: [result-layout.png](images/result-layout.png),
  [result-edit-drawer.png](images/result-edit-drawer.png).

## Persona library

- New 模特 tab: reusable AI/real personas, Tencent-compatible gender/age/body/ethnicity,
  optional exact age/height/hair/outfit/temperament/voice tone, role, and explicit
  consent gating for real people.
- Preview: [persona-library.png](images/persona-library.png).

## Per-shot replacement

- "应用到这一镜" now calls `POST /runs/{id}/segments/{segment_id}/replace`.
- The result panel polls the same run while `step=segment|stitch|qa`; progress is
  staged (generate → stitch → QA).
- If a replacement exists, the action rail shows "回滚上一镜"; it restores the
  previous final from `versions/` and removes the last edit entry.

## Prompt-first text-to-video (2026-11)

Commercial references: Kling's current guide puts prompt and reference assets first
(up to 15 references, prompt expansion, 3-30s, Auto aspect), with duration/resolution
as secondary controls; Pika/Runway follow the same prompt-plus-reference model.
AdClip therefore replaces the field-heavy form with one composer:

- one large prompt;
- one attachment strip for images/videos;
- model selector + hidden 参数;
- aspect/duration/resolution are extracted from the prompt when written
  (`9:16`, `8秒`, `1080p`, `竖屏`, `精细`), with a DSH `deepseek-flash` JSON parser
  as the primary path and regex as fallback. The parser handles phrases such as
  `大概十秒` and also detects stitch intent.
- `最近生成` is removed from the creation page; tasks live in 任务;
- video attachments + wording such as 拼接/拼起来 triggers `/stitch`; no separate
  stitch form.

Preview: [text-composer.png](images/text-composer.png).

## Persona modal

- Persona library is a card grid; 新建/编辑 opens a centered modal.
- Modal groups fields: 基础, 人物, 风格; real-person consent stays explicit.
- Preview: [persona-modal.png](images/persona-modal.png).

### Parameter precedence

- Manual edits made in 参数 are tracked per field (`aspect`, `duration`,
  `resolution`, `generation_mode`).
- Precedence is: **manual field > explicit prompt value > default**.
- When a manual value differs from a prompt-detected value, the composer shows a
  warning such as `比例手动 16:9 覆盖描述 9:16`; it never silently picks the
  prompt value.
- The model selector is always manual because model selection is not extracted
  from the prompt.

## Settings / provider keys

- Settings is provider-first: MiniMax, 火山方舟 and Kling cards each hold their key
  and the models supported by that adapter.
- Saving/clearing a key refreshes the App model catalogue automatically; the
  card shows 可用/待 key and native-audio status for each model.
- Vendor discovery is best-effort: MiniMax `/v1/models` returns text models (shown
  as 厂商文本模型), Ark tries `/api/v3/models` when a key exists, and Kling has no
  model-list endpoint. Video models remain the adapter-supported list because the
  vendor APIs do not consistently expose video-model discovery.
- A separate refresh button reloads the catalogue without saving a key.
- DeepSeek is no longer a separate video card; DSH models now cover text/analysis.
- Preview: [settings-models.png](images/settings-models.png).

## Model enablement

- Every model row in Settings has an 启用 checkbox; provider cards have 全选/全不选.
- Preferences persist in the plugin's data directory’s `model_prefs.json`.
- Generation dropdowns and Auto selection only consider models that are both
  enabled and available. Disabling a model removes it from future generation,
  but not from Settings or historical runs.
- Preview: [settings-models.png](images/settings-models.png).

## Text model selection

- Settings is video-only: it no longer lists DSH providers or text models.
- Recreate and text-to-video both show a compact 文本 model selector under the
  input. Options come from `/adplus/api/dsh/models`; default is the DSH current
  selection (`deepseek-flash` when available).
- The selected `{ provider, model }` is stored in `run.advanced.text_model` and
  used for gag/script and DSH polish. DSH failure falls back to MiniMax M3.
- Media-like DSH ids (Veo/Seedance/Wan/image/video) are filtered out by id pattern
  because DSH does not expose output modality in its catalogue.

## Stacked provider cards

- Video providers are stacked vertically instead of a two-column grid.
- Each provider has a collapsible 模型 section; collapsed view shows the enabled
  model chips and `已启用 x / y`; 展开 exposes checkboxes and availability.
- Saving a key automatically expands that provider's model section.

## Free create / image generation

- Top nav label is now 自由创作; internal page has 文生视频 / 文生图片 tabs.
- 文生图片 is enabled only when `/image/models` has an available image model
  (MiniMax H3 Image / Highspeed with a MiniMax key).
- The image composer is prompt-first: model, aspect and area; no video parameters.
- Image runs use `scenario=text-to-image`, appear in 任务, and open a dedicated
  image result page with download / retry / prompt copy.
- Preview: [free-create.png](images/free-create.png),
  [image-tab.png](images/image-tab.png).

## Task and asset management

- Tasks: server-side pagination, title search, date range, status filter, inline
  rename, created/finished/duration display, and batch export of succeeded runs.
- Assets: server-side pagination, name search, kind filter, SHA-256 upload dedupe,
  exact-hash duplicate hiding, and Finder reveal.
- Create tabs stay mounted while switching top tabs.
- Data lives under the stable user data directory, not the plugin package.

# Progress / handoff

## 提示词改回“手写体”（不再给模型算语速）

- 实测：单独把“画面一段话 + 时间戳台词列表”丢给模型，它自己就能念快、不漏句；
  反而是我们加了「每秒 4–5 个字」「每句在 X 秒前说完」「句间 0.1 秒换气」之后，
  模型要么拖慢、要么被我们的字数上限改掉台词。
- `render_generation` 现在每个镜头只有：
  `【镜头 n｜起–止s｜时长】相机` + 一行 `画面：场景，动作，构图。` + 可选 `表演：表情；语气。`
  + `台词（必须与画面动作、口型同步）：` + `[mm:ss.xx–mm:ss.xx] 台词` 列表。
  全局只保留一句「共 N 句，按上面的时间与顺序说完，不要省略、合并或提前收尾」+ 价格提示。
- 删除了【语速】块、换气/结束时间叮嘱；`timing.pace_label` 不再进入提示词。
- `_timed_lines()` 保留参考时间窗与完整台词，不再按字数裁剪；如果某句确实超出模型
  可念速度，由 QA 的「台词时长」报 warn，不再静默改词。

## 生成前确认提示词（awaiting_confirm）

- 爆款复刻在“改编脚本”之后停下来：`runner.STEPS` 新增 `confirm`，run 状态变为
  `awaiting_confirm`，进度 0.32，**不调用视频模型**。
- `POST /runs/{id}/confirm` → `runner.confirm()` 写入 `advanced.prompt_confirmed` 并以
  `resume=True` 继续：跳过 analyze/gag/script（不重复花文字模型 token），
  直接从 generate 跑到 qa。
- 提示词预览用现有的 `GET /runs/{id}/prompt`（不产生费用），可在确认前编辑保存
  （`/prompt-override`）。
- UI：任务详情顶部出现“提示词已生成，等待你确认”卡片（含 AWAITING CONFIRM 标签 +
  预览/确认按钮）；任务列表卡片的状态徽标显示「待确认」并在标题下提示。
- 自由创作不重复确认（用户在提案卡上已经确认过），只对 `viral-remake` 生效。

## 台词：只改要求的词，其余原样保留

- `_rewrite_in_place` 的提示词不再给每句字数上限，改为：
  “只改用户明确要求改的词；用户没提到的句子原样输出，一个字都不要改”。
  实测输出：`你们都在抢啊？` / `抢这个厚实又暖和的豆豆云朵被呢？` /
  `系统标错了，现在只要七十多。` — 只有商品名和价格变了。
- `_timed_lines()` 不再按时间窗裁剪台词，只对齐时间窗；原片念得完的句子不该被我们改短。
  若某句确实超出模型可念速度，QA 的「台词时长」会报 warn，由用户在确认环节决定。
- 移除了 `_clip_level_fit()`（全片字数裁剪），它正是“改台词”的另一个来源。

## 台词改为“按拆解逐句改写”（rewrite-in-place）

- `script._rewrite_in_place()`：拆解已经知道每句说了什么、在第几秒。现在把
  `[时间窗] 原文（≤N字）` 整表交给文字模型，要求**一句对一句**地改：行数、顺序、
  时间窗都不变，只换商品名/价格/卖点，保留句式、钩子结构和收口。省掉了“先自由写
  脚本再挤进时间窗”那一步，句子不会再被截成“冬天如果你盖，还冷的话，我亲自”。
- 返回行数与拆解行数不一致时直接放弃改写路径（否则又要重新排期），回到自由生成。
- 提示词里的字数上限 = 时间窗 × `BUDGET_CPS(4.0)`（= 模型实测念速）；超过 15% 才裁。
  实测改写结果：
  `[0.0–4.0] 冬天盖豆豆云朵被还冷，我亲自去暖被窝` /
  `[4.5–5.5] 都抢啊？` / `[5.5–7.5] 抢豆豆云朵被呢？` /
  `[7.5–10.5] 系统标错了现在只要七十多`
- 没装 ASR / 没有拆解台词时，仍走原来的自由生成路径。

## 台词预算与参考时间窗对齐

- **对白时间窗直接沿用拆解结果。** `_timed_lines()` 把每行的起止设成原片那一句的
  真实时间窗，保留原片的停顿/抢拍；行数偏多时先把相邻行用逗号合并到 ASR 行数
  （不丢字），行数偏少时用 `_merge_windows()` 把相邻 ASR 窗口合并成一段，边界仍是
  拆解的首尾。窗口只按镜头边界裁剪，不再统一提前 `TAIL_S`；某句确实念不完由 QA
  `dialogue_timing` 报 warn，而不是改写时间。
- 提示词删掉了「全部台词必须在约 X 秒前说完；说完后不要留长时间空白画面。」：
  模型不会按秒数执行，逐句时间窗已经是拆解的真实起止；在快语速原片上这句还与
  「不要拖慢」互相矛盾，只会增加提示词长度。
  窗口内只用 `MAX_CPS=5.5` 做物理兜底，真正的长度控制靠两道预算：
  - 每镜预算 `span × BUDGET_CPS(4.0)`（脚本提示词里的字数上限 + 行时窗）；
  - **全片预算** `(片长-0.45) × 4.0`：成片模型是“一口气念完”的节奏，实测
    三条真实成片分别落在 4.0–4.4 字/秒，超过这个总数就会把最后几个字说到切点之后。
    超了只按比例缩前几句，最后一句（价格/收口）保持完整。
- 实测证据：一条 11.07s 的成片 ASR 为 44 字 / 11.0s，与预算正好持平，最后“七十多”
  被切；把总数控到 42 后留出 0.5s 余量。
- `_cut()` 只在靠近上限（85% 以后）找断点，不会为了一个逗号多砍一大截；
  并会在「的/了/呢/啊」处断句。
- 分镜面板的时间轴以**成片实际时长**为准（之前用请求时长 12s，导致分镜显示
  0–4.9s / 4.9–12.0s，而提示词里的台词是 0–4.5s / 4.5–11.1s，看起来像对不上）。

## 语气复刻：语速实测 + 表情/语气解析

- 语速不再写死。`timing.measured_cps()` 从 ASR 的 `dialogue_rows` 算出参考片实际语速
  （字/秒），`timing.fit_cps()` 把它夹到 [3.2, 5.5]，脚本预算、镜头时长分配、提示词全部用它。
  提示词现在是“【语速】原片约每秒 7.4 个字，偏快（像直播叫卖）；用同样的语气和节奏复刻”，
  每个镜头还会单独写 `语气：… 语速偏快`。预算仍以 5.5 字/秒封顶：写超出物理上限的台词
  正是最后一句被切的原因。
- 拆解新增两个字段：`expression`（可见表情/情绪）和 `tone`（说话语气），
  `VISION_PROMPT`、`_normalize_rows`、`_aggregate_visual`、`_remake_plan`（`expression`/`tone`/`pace_cps`）
  一路带到 `build_spec`，最终渲染成每个镜头的 `表情：` 和 `语气：` 两行。
  实测（DSH 视觉桥 deepseek-flash）：`expression: 睁眼张嘴，略显惊讶`、`tone: 急切解释`。
  拆解面板也会显示“表情/语气/语速”一行。`CACHE_VERSION` → `6`（旧的拆解没有这两个字段）。
- `render_generation` 不再输出“按每秒 4–5 个字念”；脚本提示词还多了一条
  “台词要能连得上参考片的语气：原片快的就写短句、可叫卖式”。

## 拆解继承 / 缓存签名 / 参数清理

- `render_generation` 现在按镜头输出：每个镜头一块，带自己的景别·运镜·角度、场景、动作、
  构图、衔接、转场和台词时间。之前把所有镜头压成一句 `【场景】/【动作】/【镜头】`，
  两镜换场景（卧室 → 家纺店内）时提示词会丢掉第二镜的信息。人物的书面描述只在
  “保留人物”时才列出，替换人物时改为要求人数/站位一致。
- 分析缓存 key 增加视觉链签名 `vision.chain_signature()`（`minimax` / `ark:lite,turbo,pro`
  / `dsh` 的组合）。停用某个提供方后 key 变了，不会再重放它产出的旧拆解——之前
  “已停用 Doubao 但界面还显示 doubao 模型”就是命中了旧缓存（`analysis.cached`）。
  拆解面板现在也会标「缓存结果」。`CACHE_VERSION` → `5`。
- 台词时长：`fit_lines` 的预算用 `timing.speak_span()`（镜头时长减去 `TAIL_S=0.45`），
  所以每句都会在切点前留出余量；ASR 真实时间戳只在结束点早于切点时复用，
  否则改用 `schedule()`。渲染前再按 5.5 字/秒的物理上限兜一次。
  提示词也改成“句间只留 0.1 秒换气、切换处不要停、每秒 4 个字”，
  之前写的“每句停 0.2–0.5 秒”会让模型在镜头切换处空一拍。
- 删掉了从未被读取的 `advanced` 字段：`fidelity`、`language`、`native_audio`、`music`、
  `aigc_label`、`subtitle_size`，以及 `generation_mode`（“快速/精细”从来没改变生成方式）；
  对应的“字幕字号”“背景音乐”“精细模式”意图规则一并移除。

## 文本 / 视觉模型的启用开关

- 「已开通」是方舟侧的开关，「启用」是 AdClip 自己的开关：`POST /settings/text_models`
  把勾选结果存到 `model_prefs.json` 的 `enabled_text_models`。这份列表是精确的，
  三个都取消就真的没有 Ark 文本/视觉模型，视觉链跳过它们、文本生成回落到 DSH。
  从未保存过时该键不存在，三行保持默认全开（不破坏老配置）。
- `ark_text.models()` 返回 `enabled`，`vision_models()/chat()/llm.chat()` 全部遵守；
  只有激活探针（`probe`）故意绕过（`require_enabled=False`），这样停用的模型
  仍然能显示是否开通。`catalog.vision_chain()` 的档位会把停用模型标成不可用，
  原因写“已在设置里停用”。设置页每一行右侧新增「启用」勾选，卡片头部有全选/全不选。
- 自由创作的文本模型选择器只列启用中的 Ark 行。

## 台词时长 / 同音字校对 / 画面文字检查

- **台词时长**：`pipeline/timing.py` 现在是唯一口径。`char_budget()` 给出一个 beat
  能念完的字数（自然语速 4 字/秒，上限 5.5 字/秒，1.2 倍宽限），`fit_lines()`
  超预算时**按比例缩短每一句而不是丢掉整句**（价格句/收口句不会再被静默删掉），
  `schedule()` 把最后一句结束点提前 `TAIL_S`，保证切镜头时不切断字尾，
  `overflow()` 供 QA 判断。`script.build_script` 的提示词直接给模型每个 beat 的字数上限，
  `rewrite_shot` 同样按上限收紧。
- **同音字校对**（`media/asr.py::refine`）：不是写死模型——先用 DSH 当前默认文本模型，
  再降级 Ark lite → turbo → pro。真正的失败原因是 `max_tokens=1200` 被推理模型的
  思考过程吃光，桥返回空文本，校正静默降级。现在默认 3000
  （`ADSTUDIO_ASR_CLEANUP_MAX_TOKENS`），`llm._chat_dsh` 遇到空文本会用更大预算重试一次，
  并且失败会写进 `analysis.asr.cleanup/error` 与 warnings，不再静默。
- **画面文字 / 水印**：`ark` 的 `watermark: false` 一直生效（实测输出没有平台水印）。
  提示词里不再点名“水印/logo”，避免把词面量渲进画面；真正兜底的是 QA 新增
  `text_overlay`：抽样两帧走视觉链，检测到叠加文字（例如模型自绘字幕、商品标签）就 warn。
- **QA `dialogue_timing`**：用渲染器同样的 `timed_lines` 校验每句槽位是否够念完，
  并给出整体 cps。
- **分镜 UI**：台词不再被 `-webkit-line-clamp:2` 截断，按行显示并带每句起止时间
  （`storyboard.json` 的 `segments[].lines`）。

## Implemented in this slice

- Doubao-Seed-2.1（方舟 pro/turbo/lite）接入文本与视觉：`providers/ark_text.py`、
  `GET /text/models`、`POST /text/chat`、`POST /text/models/probe`；视觉链变为
  MiniMax-M3 → Doubao → DSH 视觉桥 → 启发式，并经 `scheduling.vision`、
  `adclip_list_capabilities`、`adclip_get_analysis`、设置页暴露给 DSH 调度。

- New `src/adclip/` FastAPI service, no legacy imports.
- DSH plugin installed and active (`main:adplus`, `sidebar.panellist:adplus`).
- Demo pipeline: upload → analyze → script → generate → post → QA.
- Storyboard API/view, derived versions, two-clip stitch backend (DSH tool only) with black/blur/crop fit.
- Persona CRUD API + inline persona fields + saved-persona picker + a
  dedicated 模特库 tab for create/edit/delete and real-person consent.
- Single-shot replacement is verified with both demo and MiniMax H3: the H3
  replacement took ~2.5 min, produced a new version, and rollback restored the
  prior final.
- ASR transcript + MiniMax M3 vision tags on up to six keyframes are wired into
  the gag/script prompts; `ADSTUDIO_ASR=0` / `ADSTUDIO_VISION=0` disable them.
- Provider key settings API + UI (`data/settings.json`, mode 0600).
- Ark Seedance adapter and Kling official adapter (implemented, unverified
  without real keys; they become selectable after the key is saved).
- MiniMax H3 adapter is connected and **verified with a real key**: text-to-video,
  2K output, native Chinese dialogue, post-normalized to 720p. Hailuo 2.3 Fast
  image-to-video is verified too, but produces no audio track (silent visual
  fallback; text-to-video is rejected by the provider).
- Gag/script generation now uses the DSH `deepseek-flash` bridge first, with
  MiniMax M3 as fallback. The same MiniMax key is still reused for video, with a
  deterministic fallback.
- DSH LLM catalogue bridge (`/adplus/api/dsh/models`) and `/adplus/api/dsh/chat`
  are loaded and verified: `/models` returns 51 models across deepseek-official,
  deepseek-account and suanli; `/chat` returned `成功`. The brief composer shows
  the DSH polish action. Video generation still needs a video provider key.
- Post-only derive for export bitrate/fps/trim; does not call a video model.
- UI redesign: 3x3 product media grid, sectioned form, structured brief composer,
  visible primary action, example starters, docs screenshot.
- Free-create page with 文生视频 / 文生图片 tabs. Image generation uses MiniMax
  H3 Image through `/images`; runs appear in tasks with a dedicated image result.
- Result page layout pass: side action rail, icon actions, change-only parameter
  drawer, and a vertical storyboard list with per-shot inline editing.
- Prompt-first text-to-video composer: attachments, model selector, hidden
  parameters, prompt-derived aspect/duration/resolution, and stitch intent from
  video attachments plus wording. 最近生成 removed from the creation page.
- Prompt intent parsing now calls the DSH `deepseek-flash` bridge for structured
  JSON (aspect/duration/resolution/mode/stitch); regex remains a fallback.
- Text composer parameter precedence is manual field > prompt value > default,
  with an explicit conflict notice when a manual value overrides the prompt.
- Persona library cards + centered create/edit modal grouped into 基础/人物/风格.
- Settings is provider-first: key + supported models per vendor; save/clear or
  refresh updates availability, native-audio flags and reasons automatically.
- Best-effort vendor discovery: MiniMax text models via `/v1/models`; Ark tries
  `/api/v3/models`; Kling has no list endpoint. Video models stay adapter-authoritative.
- Per-model enablement is persisted in `data/model_prefs.json`; Settings exposes
  checkboxes and per-provider select-all; generation only uses enabled+available models.
- Text model selection moved into the creation composer (from DSH); Settings is
  video-only. Selected `{provider, model}` is stored per run and used by gag/script.
- Persona wins over reference cast: reference-derived “男子/女性/老人” wording is
  normalized to the selected persona in gag, script and provider prompts. A real
  Ark Fast run with female persona produced three women.
- Smoke test now uses an isolated temp data dir and covers post-only derive.
- Model capability registry (`capabilities.py`) covers all current Settings models
  with inputs/outputs/params/remake tier/defaults; Settings can inspect and save
  per-model defaults. Viral remakes auto-select H3 first, then Seedance
  reference/generation, then analysis-only; the Recreate page no longer offers a
  model picker. H3 reference runs use the MiniMax Files API and
  `mm_file://` content; the pipeline supports a full H3 reference branch.
- The plugin registers DSH agent tools (`adclip_remake_video`, `adclip_get_run`,
  `adclip_get_analysis`, `adclip_list_capabilities`, `adclip_cancel_run`) and a
  system-prompt section for the remake preservation contract.
- The remake page no longer attaches a text-model polish control or example
  prompts. Uploaded reference videos and product images open a click-to-zoom
  preview modal. "自由创作" is now a description → plan → confirm conversation
  with one text-model selector and no image/video parameter controls; text
  defaults to 9:16/8s/720p for video and 1:1/2K for images. Only explicit
  generation requests get a proposal; normal chat never starts a run. Stitching
  is exposed only as `adclip_stitch_videos`; DSH also gets
  `adclip_create_image`, `adclip_create_video`, `adclip_list_assets` and
  `adclip_list_personas`. The remake and free-create prompt sections are
  separate so the remake contract is unchanged.
- Reference keyframe vision now falls back from MiniMax-M3 to an image-capable
  DSH model through `/adplus/api/dsh/vision`; frames arrive as durable
  `ImageBlock` attachments, use the shared storyboard prompt, and still degrade
  to heuristic analysis if no image model/bridge is available. Frame count is
  adaptive by duration (roughly one every 2.5s, min 4, max 12) with up to four
  refine frames for low-confidence or long beats.
- Image and free-video generation now fall back through the enabled model
  capability registry. A provider-level error (insufficient balance, auth,
  rate limit, 402/403/429) skips that provider and the next compatible model
  finishes the same run; attempts and a UI warning are stored on the result.
- H3 runs now generate gag/script text. `audio_mode=regenerate` strips the
  reference audio, sends a silent reference to H3 and feeds sequential shot
  lines into the prompt; `preserve` keeps the source track and post replaces the
  H3 audio with the reference audio, eliminating old/new voice overlap.
  Preserve is person-only; replacing the product forces regenerate. Remake
  duration/aspect follow the probed reference and post trims to it, so the
  output cannot drift with the old manual controls. Storyboard
  edits on H3 create a derived whole-clip rerun instead of a per-shot splice;
  non-H3 edit failures restore the prior successful state and set
  `last_edit_error`. Startup repair restores older runs wrongly marked failed by
  the `segment not found` edit bug.

## Pending

- Kling real-key bake-off and prompt tuning. Ark Seedance 2.0 Mini/Fast are
  verified in a real account (native Chinese audio, 720p); Ark 2.5/2.0 remain
  unverified on this account.
- Volcengine Jimeng adapter.
- Post-only subtitle burn/music (local ffmpeg has neither libass nor drawtext;
  SRT remains a sidecar; music replacement is not wired).
- Provider keychain migration; Windows packaging; DSH page visual verification.

## Verification

- `PYTHONPATH=src .venv/bin/python tests/smoke.py` passes.
- `node --check` passes for plugin client and host files.
- Slot registration and proxy/media paths verified; browser rendering not directly
  verified (no browser-control tool in this session).

## Management / durability pass

- Stable user data dir: `~/Library/Application Support/AdPlusStudio/data`
  (platform-specific defaults), with one-time copy from `engineRoot/data`.
  Legacy data is never deleted; migration marker is written.
- Task API now supports offset/limit, title search, date range, status filter,
  rename, and multi-run ZIP export.
- Assets API now supports offset/limit/search/kind and SHA-256 dedupe on upload;
  asset list also hides exact-hash duplicates.
- Host route `/adplus/api/reveal` opens a data path in Finder.
- Recreate and Free Create tabs stay mounted while switching tabs, preserving
  prompt, attachments, persona and parameter state.

# Progress / handoff

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

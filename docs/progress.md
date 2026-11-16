# Progress / handoff

## Implemented in this slice

- New `src/adclip/` FastAPI service, no legacy imports.
- DSH plugin installed and active (`main:adplus`, `sidebar.panellist:adplus`).
- Demo pipeline: upload → analyze → script → generate → post → QA.
- Storyboard API/view, derived versions, two-clip stitch with black/blur/crop fit.
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

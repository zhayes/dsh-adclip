# AGENTS.md

Guidance for agents working in this repository. Read this before changing the
plugin, engine, prompts, or release artifacts.

## Project

**AdClip** is a DSH plugin plus a local Python/FastAPI engine for short ad-video
workflows. It has two user-facing scenarios:

1. **爆款复刻 / viral remake** — preserve a reference video's camera, scene,
   action, composition, rhythm and audio; replace only the chosen people and/or
   product unless the user explicitly overrides a scene element.
2. **自由创作 / free create** — a normal AI chat page. The user chats or asks for
   an image/video; only an explicit generation request produces a proposal card,
   and a run starts only after the user confirms it.

The engine also owns image generation, asset/persona management, run history,
QA, storyboard edits and video stitching.

Current package versions:

| Piece | Version |
| --- | --- |
| DSH plugin (`plugin/package.json`) | `0.5.22` |
| Python engine (`adclip.api.VERSION`) | `0.1.15` |

Do not bump versions unless you are actually releasing. A client-only change
still needs a plugin version bump and reinstall to reach the running DSH profile.

## Runtime shape

```
DSH client
  ├─ plugin/client.js          React UI (custom AdClip pages)
  ├─ plugin/host/tools.js      DSH agent tools
  ├─ plugin/host/proxy.js      /adplus/api/* and /adplus/media/* -> engine
  └─ plugin/host/supervisor.js starts/stops the Python engine
        └─ FastAPI engine (src/adclip/api.py)
             ├─ pipeline (analyze / script / generate / post / qa / replace)
             ├─ providers (MiniMax, Ark/Seedance, Kling, image providers)
             ├─ media (ffmpeg, ASR, vision, subtitles, stitch, H3 Files API)
             └─ data dir (runs, assets, personas, settings, context)
```

- The UI calls the Host proxy at `/adplus/api/...`.
- DSH tools call the engine directly. In `plugin/host/tools.js`, `API` is `''`;
  do **not** prepend `/adplus/api` there.
- Engine runtime data defaults to
  `~/Library/Application Support/AdPlusStudio/data` on macOS. Tests set
  `ADSTUDIO_DATA_DIR` to a temporary directory.
- The plugin starts or restarts the engine. Do not start a second engine unless
  explicitly asked.
- The supervisor passes the live Host URL to the sidecar as `DSH_WEB_URL` and
  `ADSTUDIO_DSH_CHAT_URL`, so the engine uses the DSH text model/config of the
  *current* Host instead of the old default port.

## Repository map

```
plugin/
  index.js                 DSH apply(): supervisor, proxy, tools, prompt sections
  client.js                AdClip React UI and all page CSS
  host/tools.js            adclip_* agent tools
  host/proxy.js            Host proxy + /dsh/models, /dsh/chat, /dsh/vision
  host/supervisor.js       Python engine lifecycle, health and preflight
  host/dsh.js              DSH llm catalogue, text chat, image-attachment vision bridge
  host/preflight.js        ffmpeg/Python/dependency checks
  package.json             plugin metadata/version/dsh bundle declaration
  cordis.patch.yml         DSH bundle patch
  locale/                  en/zh strings

src/adclip/
  api.py                   FastAPI routes, run creation, settings, export
  models.py                Run / RunStep / StoryboardSegment / request models
  params.py                scenarios, defaults, auto timing/audio helpers
  catalog.py               model rows + live availability/enablement
  capabilities.py          static model capability specs (inputs/params/remake)
  settings.py              persisted model settings/default params
  store.py                 runs/assets/personas JSON persistence, repair helpers
  remake_planner.py        capability-driven H3/Seedance/analysis selection
  intents.py               rule-first assistant changes for storyboard chat
  personas.py              persona CRUD
  image_params.py          image-model view over catalog
  llm.py                   DSH/MiniMax/Doubao(Ark) text bridge
  media/
    ffmpeg.py              probe, normalize, trim, concat, audio strip/replace
    asr.py                 faster-whisper transcription/word timestamps
    vision.py              MiniMax-M3 → Doubao(Ark) → DSH keyframe labels
    subtitle.py            SRT generation
    stitch.py              ordered clip plans, fit modes, audio keep/mute
    minimax_files.py       MiniMax Files API upload for H3 references
  pipeline/
    analyze.py             skeleton + analysis + remake_plan
    script.py              gag/script generation, per-shot rewrite
    remake.py              H3 preservation prompt, spoken lines, audio mode
    generate.py            video model selection + fallback + H3 reference
    image_runner.py        image model selection + fallback
    post.py                normalize, trim to reference, H3 audio replacement
    qa.py                  duration/aspect/audio/口播/overlap checks
    segment.py             storyboard builder
    replace.py             per-shot edit/replace + transactional restore
    runner.py              run state machine
    persona.py             prompt-safe person description
  providers/               model adapters

tests/                     Python/Node checks; see below
scripts/                   staging/publishing/tarball/install helpers
docs/                      architecture, capabilities, UX, progress, install
dist/                      staged plugin artifacts (ignored)
```

## Current feature behavior

### Viral remake

- `remake_planner.py` selects in this order when no explicit model is requested:
  1. MiniMax H3 (`full`, reference replacement),
  2. Seedance reference/generation models,
  3. `analysis_only`.
- H3 is the only `full` remake model. H3 requires a 4–15s reference and uploads
  through the Files API (`mm_role` references; `mm_file://...` content).
- H3 runs generate `gag.json` and `script.json` even though H3 is one-shot.
- H3 audio:
  - `audio_mode=regenerate` (default): reference audio is stripped, H3 receives a
    silent reference, and spoken lines are put into the prompt.
  - `audio_mode=preserve`: H3 uses the reference audio, but post replaces the
    H3 audio with the reference track. Preserve is **person-only**; replacing a
    product forces regenerate so the old product name/price cannot remain.
- Remake duration/aspect are automatic: the engine probes the actual source,
  updates `Run.selection` after analysis, and post trims the output to the
  reference duration/aspect. Do not reintroduce a manual duration/aspect drift.
- Storyboard edit for H3 creates a **new derived run** with the shot
  instruction in `explicit_overrides`; it never mutates the successful parent.
- Non-H3 storyboard edit/replace is transactional: failure restores the prior
  successful run and records `last_edit_error`.
- On startup, `store.repair_segment_edit_failures()` repairs the historical
  `ValueError: segment not found` failure signature when a valid final video and
  shippable QA exist.

### Free create

- One page, one **text-model picker**; no image/video model or parameter
  controls, no stitch UI.
- Normal chat returns a reply only. The model returns a JSON contract with
  `action: none|image|video`. Only `image`/`video` with a complete prompt shows a
  generation proposal card. The user must click it (or say generate) before a
  run starts.
- Image proposal defaults: `1:1`, `2K`.
- Video proposal defaults: `9:16`, `8s`, `720p`.
- Image generation calls `POST /images`; video calls `POST /runs`
  (`scenario=text-to-video`).
- `text-to-video` applies scenario defaults in `api.create_run`, so a run with
  no `advanced` object still lands on 9:16 / 8s / 720p / `model=auto`.
- Attachments are images only (max 4, first is primary).
- Stitching is **not** exposed in the UI. It is the DSH tool
  `adclip_stitch_videos`; the backend `/stitch` and `/stitch/plan` routes remain.

### Vision fallback

- Fallback ladder, first success wins:
  1. MiniMax-M3 (`MINIMAX_API_KEY`),
  2. Doubao-Seed-2.1 pro/turbo/lite on Volcengine Ark (`ARK_API_KEY`,
     `ADSTUDIO_VISION_ARK_ORDER`, default `pro,turbo,lite`; cached
     `ModelNotOpen` models are skipped),
  3. the Host `/adplus/api/dsh/vision` bridge (an image-capable DSH model),
  4. heuristic analysis.
- The DSH bridge admits JPEG frames through `ctx.attachments` and sends
  `ImageBlock` content to the first DSH model whose `inputModalities` includes
  `image` (currently `deepseek-flash`); it never picks a text-only model.
- All paths share `src/adclip/media/vision.py`'s `VISION_PROMPT`: per-frame
  shot size, camera, people/action, product/visibility, scene, composition,
  on-screen text, continuity, confidence and unclear fields.
- Failure never blocks analysis; `analysis.provider/model` records the actual
  source (`minimax`, `ark`, `dsh`) and `analysis.warnings` carries the degraded
  reason.
- `catalog.vision_chain()` is the single ladder definition. It is exposed
  through `GET /capabilities` (`scheduling.vision`), the
  `adclip_list_capabilities` tool and the Settings page; keep those in sync.
- DSH attachments persist; frame budget is adaptive (roughly one every 2.5s, min 4, max 12) with up to four refine frames for low-confidence/long beats, and MiniMax stays first.

### Text/vision models (Doubao-Seed-2.1)

- `src/adclip/providers/ark_text.py` owns the three Ark rows
  (`ark.doubao-seed-2.1-pro|turbo|lite`), their capability tags
  (`多模态模型/深度思考/视觉理解`, 1M context), `thinking.type` control and the
  `ModelNotOpen` handling.
- These rows are **not** in `catalog.rows()`; `catalog.text_rows()` feeds
  `GET /text/models`, `GET /capabilities` (`text_models`) and the picker. The
  video/image registry stays at 13 rows.
- Engine routes: `GET /text/models`, `POST /text/chat` (ark only),
  `POST /text/models/probe`. They are reached through the existing
  `/adplus/api/*` proxy, so `plugin/host/proxy.js` needs no change.
- Activation (`已开通`) and enablement are separate switches. `POST
  /settings/text_models` persists `enabled_text_models` in `model_prefs.json`;
  the list is exact, so disabling all three really removes Ark text/vision and
  the engine falls back to DSH. Before the first save the key is absent and every
  row stays on. `ark_text.models()`, `vision_models()`, `chat()` and
  `llm.chat()` all honour it; the activation probe bypasses it on purpose
  (`require_enabled=False`) so a disabled row can still be checked.
- `llm.py` order is DSH → MiniMax → Ark by default; an explicit
  `text_model.provider == "ark"` (from `run.advanced.text_model`) puts Ark
  first and falls back to DSH.
- Activation state is cached in `data/text_models_state.json` (24h for `ok`, 10min for `not_open`). Right after activation Ark serves stale replicas that still answer `ModelNotOpen`, so `chat()` retries twice (1.5s/4s) and a proven `ok` row is never downgraded by a single 404.

### Model fallback

- Image runs and free/video generation walk the enabled capability registry
  instead of trusting one model.
- On provider-level errors containing balance/quota/auth/rate-limit markers
  (`insufficient balance`, `402/403/429`, etc.), the same provider is skipped
  and the next compatible model continues the **same run**.
- Non-provider errors also advance to the next model. All failures produce a
  combined error listing every attempt.
- Results carry `result.attempts` and `result.warnings`; the image result page
  displays a fallback warning.
- H3 reference generation is still a single selected path; the runtime fallback
  work covers image generation and standard/free video generation.

### DSH tools

Registered from `plugin/host/tools.js`:

- `adclip_remake_video`
- `adclip_create_image`
- `adclip_create_video`
- `adclip_stitch_videos`
- `adclip_get_run`
- `adclip_get_analysis`
- `adclip_list_capabilities`
- `adclip_list_assets`
- `adclip_list_personas`
- `adclip_cancel_run`

Tool rules:
- Never ask the user to pick an image/video model; the engine auto-selects.
- `adclip_stitch_videos` is the only stitching surface.
- Reuse uploaded assets/personas via the list tools instead of asking for
  re-uploads.
- Remake requests must go to `adclip_remake_video`, not free-create tools.

### Prompt sections

`plugin/index.js` uses three separate system-prompt sections:

- `adclip:remake-guidance` (order 3000) — remake preservation contract only.
- `adclip:vision-guidance` (order 3005) — the reference-frame vision ladder and
  the rule to report `provider/model` instead of asking the user.
- `adclip:free-create-guidance` (order 3010) — image/video/stitch/asset tools.

Keep them separate. Do not add free-create instructions to the remake section;
doing so changes remake behavior and risks the preservation contract.

### UI behavior / visual invariants

- Page subtitles use `.adp-lede` with `white-space: nowrap`, ellipsis.
- macOS: the plugin detects whether the DSH center column is pushed right
  (sidebar open). When open, `AdClip` + `AI AD VIDEO STUDIO` show; when collapsed,
  only the brand is hidden. `AI AD VIDEO STUDIO` itself must remain visible.
- Remake media (reference video/product images) opens a click-to-zoom modal;
  do not reintroduce upload-on-click when an asset exists.
- Free create uses a borderless custom model picker with a `✦` agent icon and an
  inline SVG chevron; do not replace it with a native select that has a fixed
  width or a remote chevron.

## Invariants and constraints

- **Capability-first, not model-id-first.** Read `catalog.py` and
  `capabilities.py`; the UI/tool callers should not hardcode model ids except in
  catalogue rows and tests.
- **Do not add model rows** for models that are not in the current Settings
  catalogue unless explicitly asked. The registry covers the current 13 models
  (plus `test.synthetic` in test mode).
- **No pricing/billing UI.** `cost_weight`/`priority` are internal ordering
  hints only.
- **Keep Python/ffmpeg architecture.** Do not migrate the engine to Node.
- **No model question in the agent conversation.** Auto-select and report the
  selected model/path.
- **H3 is one-shot.** Do not build per-shot H3 stitching; use a derived whole
  rerun for edits.
- **`audio_mode=preserve` is not valid for product replacement.** The engine
  enforces this; keep the UI and tools consistent.
- **Automatic remake timing.** Do not expose manual duration/aspect controls for
  viral remake.
- **Do not mix staging/runtime data.** Tests use `ADSTUDIO_DATA_DIR`; the live
  app uses the Application Support directory.
- **Never commit secrets.** Provider keys live in Settings/env, not source.

## Development commands

Use the repository virtualenv:

```bash
cd /Users/chad/adstudio
PYTHONPATH=src .venv/bin/python tests/smoke.py
```

Useful checks:

```bash
PYTHONPATH=src .venv/bin/python tests/capabilities.py
PYTHONPATH=src .venv/bin/python tests/minimax_h3.py
PYTHONPATH=src .venv/bin/python tests/remake_h3.py
PYTHONPATH=src .venv/bin/python tests/segment_edit.py
PYTHONPATH=src .venv/bin/python tests/fallback.py
PYTHONPATH=src .venv/bin/python tests/ark_text.py
PYTHONPATH=src .venv/bin/python tests/script_rules.py
PYTHONPATH=src .venv/bin/python tests/timing_fit.py
PYTHONPATH=src .venv/bin/python tests/provider_payloads.py
PYTHONPATH=src .venv/bin/python tests/smoke.py
node --check plugin/client.js
node --check plugin/index.js
node --check plugin/host/tools.js
node tests/preflight.mjs
```

Test mode env used by the Python tests:

```
ADCLIP_TEST_MODE=1
ADSTUDIO_ASR=0
ADSTUDIO_VISION=0
ADSTUDIO_TEXT_PROVIDER=minimax
```

`ADSTUDIO_TEXT_PROVIDER=minimax` avoids slow DSH bridge calls in tests; the
synthetic model is used when no real provider key is present. Do not treat test
mode output as production quality.

## Local plugin reload

After changing `plugin/client.js` or Host files, stage and reinstall from the
local source, then refresh the DSH page:

```bash
rm -rf dist/dsh-adclip
node scripts/stage-plugin.mjs --out dist/dsh-adclip --name @chad.dev/dsh-adclip
```

Then use the DSH plugin manager UI/CLI to remove and reinstall the bundle, or run
the publish script. Host tools/sidecar changes require a DSH restart or engine
restart. Engine-only changes can be applied with:

```bash
curl -X POST http://127.0.0.1:54557/adplus/api/engine/restart \
  -H 'content-type: application/json' -d '{}'
```

The port above is the current Web GUI; derive it from the current DSH URL if it
differs.

## Release

The release script stages a self-contained package (engine included) and
publishes it publicly:

```bash
node scripts/publish-npm.mjs --name @chad.dev/dsh-adclip
```

- It defaults to `@<npm-user>/dsh-adclip`.
- npm publish requires 2FA; pass `--otp <code>` if prompted.
- It bumps nothing automatically. Bump `plugin/package.json` first.
- npm/pnpm 11 may delay `pnpm add <name>` for 24 hours due to
  `minimumReleaseAge`; the tarball script is the immediate-install alternative:

```bash
node scripts/release-tarball.mjs
```

Publishing is an external side effect. Only run it when the user explicitly asks
for a release.

## Debugging checklist

1. **Tool returns `Not Found`** — check that `plugin/host/tools.js` uses engine
   paths (`API=''`), not `/adplus/api`.
2. **UI changes not visible** — version was not bumped/reinstalled, or the DSH
   page needs a refresh. `pnpm run dev:web` is not part of this repo's normal
   loop.
3. **Engine old behavior** — restart the engine from the Host and check
   `/adplus/health` version.
4. **Image fails with insufficient balance** — the fallback should try another
   enabled image provider; check `result.attempts` and provider keys.
5. **Remake edit marks a successful run failed** — confirm the transactional
   restore/repair code is present; do not edit a run in place for H3.
6. **Audio overlap** — check whether the reference was silent for regenerate,
   whether preserve post-mux ran, and inspect `result.audio_mode/audio_source`.
7. **Sidebar/brand collision** — the macOS safe padding and sidebar-open
   detection are in `client.js`; subtitles must stay single line.

## Known limitations / next work

- Real H3 generation/audio quality has not been exhaustively validated with paid
  runs; QA `audio_copy`/`audio_overlap` are best-effort.
- Runtime fallback for H3 reference generation is not implemented; H3 remains a
  single selected path.
- Image fallback uses the catalog's available/enabled rows; if every provider
  has low balance, the run still fails with all attempts listed.
- Free-create chat is a browser-side JSON-contract conversation, not the DSH
  native Conversation target. The registered DSH tools are the agent-facing
  surface.
- `scripts/probe_seedance_edit.py` and other probe scripts are developer tools,
  not imported by the app.

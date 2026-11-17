# AdClip

AI 广告短视频（30 秒以内）for DSH: viral remakes, text to video, storyboard edits, personas and stitching.

- New directory only. The legacy `adplus/`, `app/`, `frontend/` and
  `vendor/openmontage/` are not imported.
- FastAPI service: analysis, script, video generation, image generation, post,
  QA, stitch, personas, runs and storyboard.
- DSH plugin: `plugin/`, installed with `plugin_manager.install_bundle`.
  Install/upgrade/uninstall for other machines: [`docs/INSTALL.md`](docs/INSTALL.md).
  `node scripts/stage-plugin.mjs` builds the self-contained package to publish.
- Free-create page: 文生视频 + 文生图片 (MiniMax H3 Image).
- No pricing, quotes or billing endpoints/UI.

## Run

```bash
PYTHONPATH=src .venv/bin/python -m adclip.api --port 8787
```

## Test

```bash
PYTHONPATH=src .venv/bin/python tests/smoke.py
PYTHONPATH=src .venv/bin/python tests/capabilities.py
PYTHONPATH=src .venv/bin/python tests/minimax_h3.py
PYTHONPATH=src .venv/bin/python tests/remake_h3.py
PYTHONPATH=src .venv/bin/python tests/segment_edit.py
PYTHONPATH=src .venv/bin/python tests/script_rules.py
node tests/preflight.mjs        # first-run environment checks (all platforms)
```

## First slice

Text analysis uses the DSH `llm` bridge first (`/adplus/api/dsh/chat`, default
`deepseek-flash`), then falls back to MiniMax M3 when the bridge is unavailable.
The text model is selected in the creation composer (from DSH) and stored per run;
Settings manages the video and image providers/models this plugin drives itself.
Every model declares its capabilities (`text_to_video`, `image_to_video`,
`text_to_image`, …); generation pages filter on those, so adding a model is one
catalogue row — see [`docs/model-capabilities.md`](docs/model-capabilities.md).
Without a provider key the generation pages stay empty and point at Settings.
MiniMax H3
text-to-video is verified with a real key, including native Chinese dialogue;
the same MiniMax key drives M3 gag/script generation. Hailuo 2.3 Fast is
image-to-video only. Ark Seedance 2.0 Mini/Fast are verified with a real key (native Chinese
dialogue); Ark Seedance 2.5/2.0 and Kling still need account-specific checks.

## 字幕与参数优先级

- 字幕只以 SRT 旁挂文件交付，**从不烧录进画面**；「生成设置 → 字幕」默认不启用。
- 创作页描述里写明的参数（比例 / 时长 / 清晰度 / 模式 / 字幕 / 厂商）**优先于控件**；控件只作为描述没提到时的默认值，提交前界面会列出「描述优先」的具体差异。
- 创建后的对话指令（如「关闭字幕」）直接作用于该条 run，并生成新版本。

## Data location

The DSH plugin sets `ADSTUDIO_DATA_DIR` to a stable user directory:

- macOS: `~/Library/Application Support/AdPlusStudio/data`
- Windows: `%APPDATA%/AdPlusStudio/data`
- Linux: `~/.local/share/adplus-studio/data`

On first startup the engine copies the repository `data/` directory into that
location. The legacy directory is left untouched. Do not put runtime data back
inside the plugin package.

## Remake selection and DSH tools

A viral remake no longer asks the operator to pick a model. `src/adclip/capabilities.py`
defines every current model's inputs, outputs, parameters, remake tier and
defaults; `src/adclip/remake_planner.py` chooses at run time:

1. `minimax.h3` when available — reference video + reference images + source
   audio, preserving camera/scene/action/composition/rhythm and replacing only
   the requested people/products;
2. Seedance reference/generation models when H3 is unavailable;
3. analysis-only when no video model is usable. Hailuo 2.3 Fast is image-to-video
   only and is not a remake candidate.

The plugin exposes `adclip_remake_video`, `adclip_create_video`, `adclip_stitch_videos`, `adclip_get_run`, `adclip_get_analysis`,
`adclip_list_capabilities` and `adclip_cancel_run` to the DSH agent, plus a
system-prompt section that states the preservation contract and tells the agent
not to ask the user for a model. Settings shows each model's capability contract
and lets the operator save default parameters. There is no pricing or billing
surface; the planner uses internal cost weights only.

H3 reference material is uploaded through the MiniMax Files API
(`video_generation_input`) and referenced as `mm_file://{file_id}`. H3 accepts a
4–15 second reference and outputs native audio. H3 runs still generate a
script. `audio_mode=regenerate` (default) strips the reference audio before H3
and puts the shot lines into the prompt so the product/price copy is spoken;
`audio_mode=preserve` keeps the source audio and the post step replaces the
H3-generated track with the reference track, so the two voices cannot overlap.
Preserve is only exposed when the product is unchanged (person-only replacement);
a product replacement forces regenerate because the source track still names the
old product. Viral-remake duration and aspect follow the reference automatically;
the engine probes the actual source, trims the output to that duration and uses
the reference aspect, so the old manual duration control cannot drift. Because H3 edits whole clips, a storyboard edit creates a new derived run
with the shot instruction in `explicit_overrides`; it never rewrites the
successful parent run. Failed non-H3 segment edits restore the last deliverable
and record `last_edit_error` instead of marking the run failed.

## Reference analysis

`analyze` uses ffmpeg cut detection, a heuristic beat grid, and optional local
Chinese ASR. ASR needs the `asr` optional dependency:

```bash
pip install -e '.[asr]'
```

It is on by default when `faster-whisper` is importable. The first run downloads
the `small` model. Disable it with `ADSTUDIO_ASR=0`; choose another model with
`ADSTUDIO_ASR_MODEL=base|small|medium`. The transcript is attached to
`skeleton.json` and fed into the gag/script prompts.

When `MINIMAX_API_KEY` is present, up to six keyframes are sent to MiniMax M3 for
visual tags (shot size, action, people, product, scene, on-screen text). These
tags are also fed into the gag/script prompts. Disable with `ADSTUDIO_VISION=0`.
Vision is best-effort and never blocks a run.

See `docs/` for architecture, model bake-off, operator scenarios, UI references,
progress/handoff and next steps. The redesigned 爆款复刻 page is previewed at
`docs/images/ui-recreate-v2.png`.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

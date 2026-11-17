# AdClip architecture (first slice)

```text
DSH Web (plugin client, React)
  -> /adplus/api/* (Host proxy, token/loopback)
  -> /adplus/media (Host proxy -> engine media)
  -> AdClip engine (FastAPI, 127.0.0.1, dynamic port)
       runs/<id>/run.json
       capabilities.py + remake_planner.py: model contract and auto selection
       pipeline: analyze -> (H3 reference | gag/script/generate) -> post -> qa
       media/stitch.py, media/ffmpeg.py

DSH agent
  -> plugin host tools (adclip_remake_video, adclip_create_video, adclip_stitch_videos, adclip_get_run, ...)
  -> same engine API (one operation, two callers)
```

The engine is new code under `src/adclip/`. It does not import `adplus`,
`vendor/openmontage` or their tools. The first slice intentionally uses a local
`demo` provider so the full UI, storyboard, edits, personas and stitching can be
exercised without paid credentials. Real provider adapters are the next step.

Model capabilities and call parameters live in `capabilities.py`; `catalog.py`
remains the row source. Viral remakes are auto-selected (H3 full, then Seedance
fallback) and never ask the operator for a model. The plugin registers DSH
tools against the same engine, so the UI and the agent share one implementation.

Post production normalizes the clip and decides subtitles from the run's own
setting: `advanced.subtitle = "off"` (default) delivers no SRT at all, while
`"sidecar"` writes `artifacts/subtitles.srt`. Subtitles are never burned in —
the shipped ffmpeg build has no libass/drawtext.

## Host setup layer

`plugin/host/preflight.js` runs the first-run checks in the Host process, not in
the engine: Python, the private venv, `ffmpeg`, `ffprobe`, the engine sources and
the data directory. It has to live there because the most common failure is a
missing interpreter, and an engine that cannot start cannot report that.

The result is cached on the supervisor and rides along with `/adplus/health`, so
the Web UI renders a setup page without extra round trips. `/adplus/api/setup`,
`/setup/recheck` and `/setup/state` answer before the engine-availability guard,
which is what lets the page work while the engine is down. Choices persist in
`<data>/.engine/setup.json`; the same code and the same checks serve macOS,
Windows and Linux, only the remediation commands differ.

Key constraints:
- No pricing/quote/billing code or UI.
- No TTS/Wav2Lip; native-audio models are the target.
- One run owns its storyboard/versions; no project/version/shot object.
- `data/runs/<id>/run.json` is the source of truth; no database yet.

# AdClip architecture (first slice)

```text
DSH Web (plugin client, React)
  -> /adplus/api/* (Host proxy, token/loopback)
  -> /adplus/media (Host proxy -> engine media)
  -> AdClip engine (FastAPI, 127.0.0.1, dynamic port)
       runs/<id>/run.json
       pipeline: analyze -> gag -> script -> generate -> post -> qa
       media/stitch.py, media/ffmpeg.py
```

The engine is new code under `src/adclip/`. It does not import `adplus`,
`vendor/openmontage` or their tools. The first slice intentionally uses a local
`demo` provider so the full UI, storyboard, edits, personas and stitching can be
exercised without paid credentials. Real provider adapters are the next step.

Key constraints:
- No pricing/quote/billing code or UI.
- No TTS/Wav2Lip; native-audio models are the target.
- One run owns its storyboard/versions; no project/version/shot object.
- `data/runs/<id>/run.json` is the source of truth; no database yet.

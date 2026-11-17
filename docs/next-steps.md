# Next implementation steps

1. Real provider adapters (Ark Seedance 2.5 first), contract tests and bake-off.
2. Analysis: keep the current ffmpeg/M3 breakdown as the fallback and add a
   whole-video evidence pass when a suitable provider is available; the H3
   replacement path already accepts the reference video directly.
3. Fine mode: true segment generation, replacement and rollback.
4. Post-only derive: subtitles/music/bitrate without re-running the pipeline.
5. Persona library and storyboard segment chat polish.
6. DSH manual page verification (light/dark, zh/en, upload/preview, storyboard).
7. Packaging: `uv`/PyInstaller sidecar, first-run model/ffmpeg checks.

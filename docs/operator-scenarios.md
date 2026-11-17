# Operator scenarios (first slice)

| Operator says / does | Current behaviour |
|---|---|
| Upload reference + product, write brief, start | Auto-selects H3 first, then Seedance fallback; returns storyboard/result |
| Change aspect/resolution/duration | In H3 reference mode aspect/duration follow the reference; other modes derive a new run |
| "字幕大一点 / 换轻音乐 / 文件小一点" | Assistant returns post changes; apply currently re-runs the demo pipeline |
| "口播重新说 / 保留原声" | H3 regenerate strips reference audio; preserve is person-only and muxes the reference track back in post; changing the product forces regenerate |
| "模特换成女性 / 年龄大一点 / 身材壮一点" | Assistant returns persona changes; stored on the derived run |
| "拼一起 / 长广告插中间" | Use the DSH `adclip_stitch_videos` tool; the UI no longer exposes stitching |
| "分镜" | Shows analysis segments and the reference remake plan; H3 edits rerun the whole clip as a new version |
| "自由创作" | Normal AI chat; only explicit image/video requests get a proposal; one text-model selector; defaults 9:16 / 8s / 720p for video, 1:1 / 2K for images |
| "素材预览" | Click a reference video or product thumbnail to open a modal; video plays, image zooms, Esc/backdrop closes |
| "这一镜重做" | H3 derives a whole-clip rerun; other modes replace one slot and keep the prior result on failure |

The remake path no longer asks for a model: the capability registry and the
planner choose H3/Seedance automatically. The DSH agent can start and poll the
same runs through `adclip_remake_video`/`adclip_get_run`.

Not yet implemented: batch fission, per-model reference adapters for Seedance,
OCR-driven on-screen text replacement, and a native Node-only runtime.

# Operator scenarios (first slice)

| Operator says / does | Current behaviour |
|---|---|
| Upload reference + product, write brief, start | Creates a demo run and returns storyboard/result |
| Change aspect/resolution/duration | Derives a new run and regenerates |
| "字幕大一点 / 换轻音乐 / 文件小一点" | Assistant returns post changes; apply currently re-runs the demo pipeline |
| "模特换成女性 / 年龄大一点 / 身材壮一点" | Assistant returns persona changes; stored on the derived run |
| "拼一起 / 长广告插中间" | Text tab offers a two-clip stitch plan and applies it |
| "分镜" | Shows analysis segments; selected segment can be sent to the assistant |
| "这一镜重做" | Segment endpoint derives a fine-mode run (first slice reruns the demo pipeline) |

Not yet implemented: real native-audio providers, LLM/VLM analysis, post-only
derive without re-running, fine-grained segment replacement with rollback,
persona library UI, batch fission.

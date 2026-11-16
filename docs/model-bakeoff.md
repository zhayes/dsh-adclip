# Model bake-off (pending)

First slice: `demo` provider by default, plus minimal Ark Seedance and Kling
official adapters. Both are implemented against the official task shapes but
have not been run with real keys; each becomes selectable when its key is saved
in Settings (or set in the environment).


Before enabling real providers, run the bake-off:

- 3 scripts: two-person price joke, single-person testimonial, product demo.
- 4 candidates: Seedance 2.5 (Ark), Kling v3, MiniMax, Veo 3.1 (Sora 2 optional).
- 2 seeds each, 9:16, 720p, 10-12s.
- Evaluate Chinese dialogue, lip-sync, character/product consistency, motion,
  duration/aspect compliance and failure rate.

At least two models must produce audible, on-script Chinese dialogue. Do not add
TTS/Wav2Lip as a fallback; switch models instead.

## 2026-11-16 MiniMax probe (real key)

- **MiniMax H3** (`MiniMax-H3`, v2 task API, 2K) succeeded with a 4s
  text-to-video prompt. The downloaded clip had a real AAC audio track and the
  ASR returned Chinese dialogue from the prompt:
  `这个真的很好喝` / `你一定要试试`. This confirms native Chinese dialogue on H3.
- **MiniMax-Hailuo-2.3-Fast** rejected a text-to-video request:
  `model MiniMax-Hailuo-2.3-Fast does not support Text-to-Video mode`.
  Treat it as **image-to-video only**; do not use it for text-to-video.
- A real viral-remake run on H3 succeeded (720p after post, 4.5s output,
  audio present). The current demo script still produces product-description
  lines; the next step is LLM/VLM script rewriting before the final bake-off.
- H3's 2K output is normalized to the requested 720p by the post step.

## End-to-end H3 + LLM script check

- MiniMax M3 text model writes the gag/script; MiniMax H3 generates native audio.
- Final 4s viral run (720p after post) produced audible Chinese:
  `这点心不油腻，追剧正合适` / `活动价19.9元，快抢`.
- No TTS/Wav2Lip; no duplicate text-model key (same MiniMax key).
- Compliance prompt now forbids inventing an original/comparison price; only the
  user-provided activity price is used.

## ASR-assisted analysis check

- A MiniMax H3 clip with the line `这点心不油腻，追剧正合适 / 活动价19.9元，快抢`
  was uploaded as the reference.
- Local faster-whisper (`small`, CPU int8) transcribed it as
  `这点心不由逆 追剧正合适` / `活动价19.9元 快抢` (one recognition error), and the
  transcript was attached to the skeleton.
- MiniMax M3 then wrote new short dialogue using the transcript plus the brief:
  `追剧零食，就选不油腻的` / `活动价19.9元，快抢`.
- ASR is optional (`ADSTUDIO_ASR=0` disables it; `ADSTUDIO_ASR_MODEL` selects the
  model). VLM/visual action extraction is still heuristic.

## ASR + VLM analysis check

- H3 speech clip used as reference; faster-whisper produced a transcript and M3
  tagged keyframes with shot size, action, people, product, scene and on-screen
  text (`19.9`).
- The visual tags were accurate enough to feed the script prompt: e.g. left
  woman points at the price sign, right woman smiles/listens, two women at a
  bakery counter.
- M3 then wrote `这点心追剧正合适` / `不油腻，追剧零食` / `活动价19.9元，快抢！`.
- Vision and ASR are best-effort and can be disabled independently.

## Single-shot replacement check

- Demo run with two storyboard slots: `s0` replaced, final duration stayed 4.0s,
  version incremented, backup stored under `versions/`, rollback restored the
  prior final and cleared `segment_edits`.
- Real MiniMax H3 run: `s0` replaced through the same endpoint. The H3 call took
  about 2.5 minutes; the result remained 4.5s/720p and `segment_edits` recorded
  the model and backup. This is true per-slot replacement, not a new full run.

## Hailuo 2.3 Fast image-to-video check

- Real `MiniMax-Hailuo-2.3-Fast` image-to-video run succeeded with a product image
  as the first frame and a 6s target. Final duration was 5.867s at 720x1280.
- The output had **no audio track** (QA audio=fail). This model is image-to-video
  only and should be used as a silent visual/fallback, not for native dialogue.
- H3 remains the native-audio/dialogue route.

## DSH-driven gag/script check

- With the DSH Host bridge loaded, a reference run used `deepseek-flash` for both
  `gag.json` and `script.json` (`source.model = deepseek-flash`).
- The generated script was:
  `看，活动价19.9。` / `这个价可以啊。` / `不油腻，追剧吃刚好。` /
  `那赶紧拿一包。`
- This is the same bridge used by “DSH 润色”; no duplicate text key is required.
  MiniMax M3 remains the fallback when DSH is unavailable.

## Ark Seedance 2.0 Mini / Fast entries

Added adapter and catalogue entries for the two models currently enabled on the
user's Ark account:

| UI id | Default Ark model id | Label |
| --- | --- | --- |
| `ark.seedance-2.0-mini` | `doubao-seedance-2-0-mini-260615` | Seedance 2.0 Mini |
| `ark.seedance-2.0-fast` | `doubao-seedance-2-0-fast-260128` | Seedance 2.0 Fast |

Both use the existing Ark content-task adapter, request native audio, and are
marked unavailable until `ARK_API_KEY` is present. Because Ark model IDs can
include a date suffix that differs by account/region, the adapter accepts
`ARK_MODEL_SEEDANCE_2_0_MINI` and `ARK_MODEL_SEEDANCE_2_0_FAST` overrides.

`auto` currently tries 2.5/2.0 before mini/fast; on an account that only has
mini/fast, select one of those explicitly until the account-specific model
discovery is wired into the auto resolver.

## Real Ark Seedance 2.0 Mini / Fast bake-off

- Both models were run with a real `ARK_API_KEY`, a reference clip, product image,
  DSH `deepseek-flash` script and 5s target at 720p/9:16.
- **Fast**: succeeded in ~3 min, 5.1s, audio present; ASR heard Chinese dialogue:
  `追距零时背上这个 吃着不油腻挺清爽 看着还真不错` /
  `活动价19.9元 喜欢的话快抢 那我赶紧下手`.
- **Mini**: succeeded in ~2.3 min, 5.1s, audio present; ASR heard:
  `这点心不油腻 追居吃正合适` / `看这价格真挺划算` /
  `活动价19.9元 快抢` / `那我赶紧捶两包`.
- Both are marked `已实测` in the catalogue. 2.5/2.0 remain unverified on this
  account and stay disabled in the UI.

## Persona vs reference-cast regression

- A 12s Ark Fast run had `persona.gender=female` but produced three men. The
  reference VLM described “三名男子”, the script copied that into the shot
  action, and the provider prompt contained both “女性” and “三名男子”. The
  action description won.
- Fixed by normalizing reference-derived people against the selected persona in
  `gag`, `script` and `generate` prompts. For female personas, “男子/男性/男人”
  becomes “女性”； male personas get the inverse; youth personas replace
  “老人/中年” with “青年”.
- Verified with a real Ark Fast 5s run: three women, product packs visible,
  native Chinese audio, QA 5/5. Reference frame:
  [ark-female-persona.jpg](images/ark-female-persona.jpg).
- Existing already-generated male versions are not altered; use 再生成 to create
  a new version with the fixed persona prompt.

## MiniMax H3 Image check

- `POST /v1/images/generations` with the existing MiniMax key and
  `MiniMax-H3-Image` succeeded on the first real call.
- Prompt: a 1:1 chickpea product image on a cream background, soft studio light.
- Output: 1024×1024 JPEG, ~10s, stored as a run artifact and an asset.
- Result: [h3-image-test.jpg](images/h3-image-test.jpg).

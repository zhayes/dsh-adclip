"""Lightweight Chinese ASR for reference clips.

faster-whisper is optional: if it is not installed (or ADSTUDIO_ASR=0), the
analysis pipeline falls back to the transcript-free path. Audio is decoded by
ffmpeg to PCM first because the installed PyAV/Python combination does not
accept faster-whisper's container options directly.

Failures are never silent: `LAST_ERROR` carries the reason, `status()` reports
installation and model state, and the analysis pipeline copies both into
`skeleton.analysis.asr` and its warnings.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .ffmpeg import FFMPEG

_MODEL = None
_MODEL_NAME = ""
LAST_ERROR = ""
LAST_MODEL = ""
LAST_LINES = 0
LAST_NOTE = ""
# Whisper often answers Chinese speech in Traditional characters; this prompt
# biases it to Simplified without any extra dependency.
_INITIAL_PROMPT = "以下是普通话内容，请全部使用简体中文转写，不要使用繁体字。"


def disabled() -> bool:
    return os.environ.get("ADSTUDIO_ASR", "1") == "0"


def installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def model_name() -> str:
    return os.environ.get("ADSTUDIO_ASR_MODEL", "small")


def available() -> bool:
    return not disabled() and installed()


def _pip_command() -> str:
    return f'"{sys.executable}" -m pip install faster-whisper'


def _hf_hint() -> str:
    if sys.platform == "win32":
        return '网络受限时先在 PowerShell 执行 $env:HF_ENDPOINT="https://hf-mirror.com" 再重启 DSH'
    return "网络受限时先执行 export HF_ENDPOINT=https://hf-mirror.com 再重启 DSH"


def status() -> dict[str, Any]:
    """Everything the UI and the tools need to explain an empty transcript."""
    ready = available()
    reason = ""
    hint = ""
    if disabled():
        reason = "已关闭（ADSTUDIO_ASR=0）"
    elif not installed():
        reason = "未安装 faster-whisper"
        hint = f"在引擎虚拟环境安装：{_pip_command()}；首次识别会下载约 500 MB 模型。" + _hf_hint()
    elif LAST_ERROR:
        reason = LAST_ERROR
        hint = _hf_hint()
    return {
        "available": ready,
        "installed": installed(),
        "disabled": disabled(),
        "model": model_name(),
        "loaded": _MODEL is not None and _MODEL_NAME == model_name(),
        "last_error": LAST_ERROR,
        "last_lines": LAST_LINES,
        "reason": reason,
        "hint": hint,
        "command": _pip_command(),
        "platform": sys.platform,
        "model_hint": (
            "可用 ADSTUDIO_ASR_MODEL=medium 提高中文准确率（首次多下载约 1.5GB，速度更慢）"
            if model_name() in {"tiny", "base", "small"}
            else ""
        ),
    }


def _load_model():
    global _MODEL, _MODEL_NAME
    name = model_name()
    if _MODEL is not None and _MODEL_NAME == name:
        return _MODEL
    from faster_whisper import WhisperModel

    _MODEL = WhisperModel(name, device="cpu", compute_type="int8")
    _MODEL_NAME = name
    return _MODEL


def _pcm(path: str | Path) -> bytes:
    proc = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"audio decode failed: {proc.stderr[-300:]!r}")
    return proc.stdout


def _audio(path: str | Path, *, max_seconds: float):
    """Decoded mono float PCM up to `max_seconds`, or a reason string."""
    import numpy as np

    audio = np.frombuffer(_pcm(path), dtype=np.float32)
    if audio.size < 1600:
        return None, "参考片没有可用人声（音轨为空或过短）"
    limit = int(max(1.0, float(max_seconds)) * 16000)
    if audio.size > limit:
        audio = audio[:limit]
    return audio, ""


def _segment_rows(model, audio, *, vad: bool, prompt_hint: str = "") -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "language": os.environ.get("ADSTUDIO_ASR_LANGUAGE", "zh"),
        "beam_size": 5,
        "condition_on_previous_text": not vad,
        "initial_prompt": _INITIAL_PROMPT + (prompt_hint or ""),
    }
    if vad:
        kwargs["vad_filter"] = True
        kwargs["vad_parameters"] = {"min_silence_duration_ms": 500}
    segments, _info = model.transcribe(audio, **kwargs)
    rows: list[dict[str, Any]] = []
    for seg in segments:
        text = str(seg.text or "").strip()
        if text:
            rows.append({"start_s": round(float(seg.start), 3), "end_s": round(float(seg.end), 3), "text": text})
    return rows


def _covered(rows: list[dict[str, Any]]) -> float:
    return sum(max(0.0, float(row["end_s"]) - float(row["start_s"])) for row in rows)


def _needs_retry(rows: list[dict[str, Any]], seconds: float) -> bool:
    """A short transcript on a longer clip usually means VAD ate the speech."""
    if seconds < 4.0:
        return False
    if not rows:
        return True
    covered = _covered(rows)
    if covered < seconds * 0.45:
        return True
    # One long block usually means several sentences were merged or VAD cut
    # the clip in half; a second pass without VAD segments it properly.
    longest = max(float(row["end_s"]) - float(row["start_s"]) for row in rows)
    return len(rows) <= 4 and longest > max(3.5, seconds * 0.35)


def transcribe_words(path: str | Path, *, max_seconds: float = 60.0) -> list[dict[str, Any]]:
    """Word-level timestamps for overlap/QA checks; best-effort like transcribe()."""
    global LAST_ERROR, LAST_MODEL, LAST_LINES, LAST_NOTE
    LAST_ERROR, LAST_LINES, LAST_NOTE = "", 0, ""
    if not available() or not Path(path).is_file():
        LAST_ERROR = "ASR 不可用" if not available() else "素材不存在"
        return []
    try:
        audio, reason = _audio(path, max_seconds=max_seconds)
        if audio is None:
            LAST_ERROR = reason
            return []
        model = _load_model()
        segments, _info = model.transcribe(
            audio,
            language=os.environ.get("ADSTUDIO_ASR_LANGUAGE", "zh"),
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
            word_timestamps=True,
            initial_prompt=_INITIAL_PROMPT,
        )
        rows = []
        for seg in segments:
            for word in seg.words or []:
                text = str(word.word or "").strip()
                if text:
                    rows.append({"start_s": round(float(word.start), 3), "end_s": round(float(word.end), 3), "text": text})
        LAST_MODEL = model_name()
        LAST_LINES = len(rows)
        return rows
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR = f"{type(exc).__name__}: {str(exc)[:240]}"
        return []


def _json_lines(text: str) -> list[str] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except Exception:
        return None
    lines = data.get("lines") if isinstance(data, dict) else None
    return lines if isinstance(lines, list) else None


def _with_timeout(call, seconds: float) -> str:
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(call).result(timeout=max(2.0, seconds))
    finally:
        pool.shutdown(wait=False)


def _cleanup_max_tokens() -> int:
    """Reasoning models burn the visible-text budget on their trace.

    The cleanup answer is tiny, but a thinking model needs room before it emits
    any JSON; a small budget returns empty text and the subtitles stay wrong.
    """
    try:
        return max(600, int(os.environ.get("ADSTUDIO_ASR_CLEANUP_MAX_TOKENS", "3000")))
    except ValueError:
        return 3000


def _cleanup_attempts(system: str, prompt: str, text_model: dict[str, Any] | None):
    """Current text model first, then Ark models by cost.

    The Host's DSH text model is the default (whatever the user configured), so
    the cleanup never pins one vendor. Ark is the fallback ladder when DSH is
    unavailable or returns something unparsable.
    """
    from .. import llm
    from ..providers import ark_text

    override = os.environ.get("ADSTUDIO_ASR_CLEANUP_MODEL", "").strip()
    if override:
        def _ark_override() -> str:
            result = ark_text.chat(
                system,
                [{"role": "user", "content": prompt}],
                model=override,
                max_tokens=1200,
                temperature=0,
                thinking=False,
                timeout=20.0,
            )
            return str(result.get("text") or "")

        yield override, _ark_override
        return

    yield "当前文本模型", lambda: llm.chat(
        system, prompt, max_tokens=_cleanup_max_tokens(), temperature=0, text_model=text_model
    )
    if ark_text.available():
        for short in ("lite", "turbo", "pro"):
            row = ark_text.row_for(short)
            if not row or not ark_text.enabled(row):
                continue

            def _ark(row: dict[str, Any] = row) -> str:
                result = ark_text.chat(
                    system,
                    [{"role": "user", "content": prompt}],
                    model=str(row["id"]),
                    max_tokens=1200,
                    temperature=0,
                    thinking=False,
                    timeout=20.0,
                )
                return str(result.get("text") or "")

            yield str(row.get("label") or row.get("short") or row["id"]), _ark


def refine(
    rows: list[dict[str, Any]],
    *,
    hint: str = "",
    text_model: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Fix homophones with the current text model, without rewriting sentences.

    Small ASR models confuse characters that sound alike (冬天/通天, 云朵/云杆).
    The model may only correct characters and punctuation: the line count and
    the timing are never changed. Attempts run under one deadline so analysis
    can never hang on a slow provider.
    """
    global LAST_NOTE, LAST_ERROR
    if not rows or os.environ.get("ADSTUDIO_ASR_CLEANUP", "1") != "1":
        return rows
    try:
        system = "你是中文带货字幕校对员。只输出 JSON，不要解释。"
        listing = "\n".join(f"{index + 1}. {row['text']}" for index, row in enumerate(rows))
        prompt = f"""商品/卖点提示：{hint or '无'}
语音转写（共 {len(rows)} 行）：
{listing}

只修正同音字、错别字和标点：结合商品/卖点把明显读不通的词换成最可能的同音词（例如“通天”→“冬天”），不要改写句式，不要增删或合并行。只输出 JSON：{{"lines":["第1行","第2行", ...]}}，必须正好 {len(rows)} 行。"""
        deadline = time.monotonic() + float(os.environ.get("ADSTUDIO_ASR_CLEANUP_TIMEOUT", "45"))
        errors: list[str] = []
        for label, call in _cleanup_attempts(system, prompt, text_model):
            remaining = deadline - time.monotonic()
            if remaining < 2.0:
                errors.append("deadline")
                break
            try:
                text = _with_timeout(call, remaining)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}: {type(exc).__name__}: {exc}"[:200])
                continue
            lines = _json_lines(text)
            if lines is None or len(lines) != len(rows):
                errors.append(f"{label}: bad lines")
                continue
            out = []
            for row, value in zip(rows, lines):
                fixed = str(value or "").strip()
                out.append({**row, "text": fixed or str(row.get("text") or "")})
            LAST_NOTE = (LAST_NOTE + "；" if LAST_NOTE else "") + f"已用{label}校正同音字"
            return out
        LAST_ERROR = ("cleanup: " + (" | ".join(errors) or "skipped"))[:200]
        return rows
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR = f"cleanup: {type(exc).__name__}: {str(exc)[:160]}"
        return rows


def transcribe(path: str | Path, *, max_seconds: float = 60.0, prompt_hint: str = "") -> list[dict[str, Any]]:
    global LAST_ERROR, LAST_MODEL, LAST_LINES, LAST_NOTE
    LAST_ERROR, LAST_LINES, LAST_NOTE = "", 0, ""
    if not Path(path).is_file():
        LAST_ERROR = "素材不存在"
        return []
    if disabled():
        LAST_ERROR = "ASR 已关闭（ADSTUDIO_ASR=0）"
        return []
    if not installed():
        LAST_ERROR = "未安装 faster-whisper"
        return []
    try:
        audio, reason = _audio(path, max_seconds=max_seconds)
        if audio is None:
            LAST_ERROR = reason
            return []
        model = _load_model()
        rows = _segment_rows(model, audio, vad=True, prompt_hint=prompt_hint)
        seconds = float(audio.size) / 16000.0
        if _needs_retry(rows, seconds):
            alternative = _segment_rows(model, audio, vad=False, prompt_hint=prompt_hint)
            if len(alternative) > len(rows) or _covered(alternative) > _covered(rows) * 1.1:
                rows = alternative
                LAST_NOTE = "VAD 只识别出部分台词，已改用无 VAD 模式重试"
        LAST_MODEL = model_name()
        LAST_LINES = len(rows)
        return rows
    except Exception as exc:  # noqa: BLE001
        LAST_ERROR = f"{type(exc).__name__}: {str(exc)[:240]}"
        return []

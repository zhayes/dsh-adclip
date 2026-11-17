#!/usr/bin/env python3
"""Probe whether an Ark Seedance model accepts a video-edit (replace) task.

Cost control: it only submits a 480p / 4s task and tries to cancel/delete it
immediately. No download, no polling by default (`--wait` opts in).

  ARK_API_KEY=... python scripts/probe_seedance_edit.py --models mini,fast
  python scripts/probe_seedance_edit.py --models 2.5 --wait

The reference video must be a public 4-30s MP4 URL; real-person footage is
rejected by Ark's privacy filter unless it is a trusted/authorized asset, so
use a synthetic or cartoon clip for a capability probe.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE = os.environ.get("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
MODELS = {
    "2.5": "doubao-seedance-2-5-260628",
    "2.0": "doubao-seedance-2-0-260128",
    "mini": "doubao-seedance-2-0-mini-260615",
    "fast": "doubao-seedance-2-0-fast-260128",
}
# Only 2.5 advertises the explicit edit task type; 2.0 relies on prompt intent.
EXPLICIT_EDIT = {"2.5"}


def api_key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if key:
        return key
    settings = Path.home() / "Library/Application Support/AdPlusStudio/data/settings.json"
    try:
        key = str(json.loads(settings.read_text()) .get("ARK_API_KEY") or "").strip()
    except (OSError, json.JSONDecodeError):
        key = ""
    if not key:
        sys.exit("ARK_API_KEY is not set")
    return key


def payload(model: str, video: str, image: str, prompt: str) -> dict:
    content = [
        {"type": "text", "text": prompt},
        {"type": "video_url", "video_url": {"url": video}, "role": "reference_video"},
    ]
    if image:
        content.append({"type": "image_url", "image_url": {"url": image}, "role": "reference_image"})
    body = {
        "model": MODELS[model],
        "content": content,
        "ratio": "adaptive",
        "duration": -1,
        "resolution": "480p",
        "generate_audio": False,
        "watermark": False,
    }
    if model in EXPLICIT_EDIT:
        body["omni_reference_task_type"] = "edit"
    return body


def probe(client: httpx.Client, model: str, args: argparse.Namespace) -> str:
    body = payload(model, args.video, args.image, args.prompt)
    res = client.post(f"{BASE}/contents/generations/tasks", json=body)
    if res.status_code >= 400:
        error = res.json().get("error") if res.text.startswith("{") else None
        detail = (error or {}).get("code") or res.text[:300].replace("\n", " ")
        message = (error or {}).get("message") or ""
        return f"{model:5s} rejected HTTP {res.status_code}: {detail} {message[:300]}"
    task_id = res.json().get("id")
    if not args.wait:
        # The task is already running; cancelling keeps the probe cheap.
        cancel = client.delete(f"{BASE}/contents/generations/tasks/{task_id}")
        state = "cancelled" if cancel.status_code < 400 else f"cancel HTTP {cancel.status_code}"
        return f"{model:5s} ACCEPTED task={task_id} ({state})"
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(4)
        task = client.get(f"{BASE}/contents/generations/tasks/{task_id}").json()
        status = str(task.get("status") or "").lower()
        if status in {"succeeded", "failed", "cancelled", "expired"}:
            return f"{model:5s} {status.upper()} task={task_id} error={task.get('error')}"
    return f"{model:5s} still running after 300s task={task_id}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="mini,fast")
    parser.add_argument("--video", default="https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_720_10s_1MB.mp4")
    parser.add_argument("--image", default="https://interactive-examples.mdn.mozilla.net/media/cc0-images/grapefruit-slice-332-332.jpg")
    parser.add_argument("--prompt", default="把视频中的主体替换为参考图1中的物体，保留原视频的镜头、动作、构图和背景")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}; pick from {list(MODELS)}")

    headers = {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0), headers=headers) as client:
        for model in models:
            print(probe(client, model, args))


if __name__ == "__main__":
    main()

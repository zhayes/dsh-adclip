"""Provider seam shared by real adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class ProviderError(RuntimeError):
    """A provider call failed with a user-actionable reason."""


class ProviderNotConfigured(ProviderError):
    """The provider key or adapter is not ready."""


class Provider:
    id = "base"

    def generate(
        self,
        prompt: str,
        *,
        images: list[Path | str] | None = None,
        duration: int = 8,
        resolution: str = "720p",
        aspect: str = "9:16",
        model: str = "",
        output: Path,
        return_last_frame: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> Path:
        """Render one clip.

        `images` mixes local files (sent as data URIs) with public URLs and
        `asset://` ids, which models that refuse photoreal faces need: the only
        face they trust is the one they produced themselves. `return_last_frame`
        asks for that artifact; `meta` receives it as `last_frame_url` and a
        locally saved `last_frame_path`, because the URL expires in about a day.
        """
        raise NotImplementedError

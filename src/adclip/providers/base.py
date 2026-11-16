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
        images: list[Path] | None = None,
        duration: int = 8,
        resolution: str = "720p",
        aspect: str = "9:16",
        model: str = "",
        output: Path,
    ) -> Path:
        raise NotImplementedError

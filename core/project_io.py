from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import PaletteLayer
from core.objects import ArtworkObject


def save_project_file(
    path: Path,
    source_image: Path,
    layers: list[PaletteLayer],
    cleanup_settings: dict[str, Any],
    version: str,
    artwork_objects: list[ArtworkObject] | None = None,
) -> None:
    data = {
        "application": "ForgePrep",
        "version": version,
        "source_image": str(source_image),
        "color_count": len(layers),
        "cleanup": cleanup_settings,
        "layers": [layer.to_dict() for layer in layers],
        "objects": [
            artwork_object.to_dict()
            for artwork_object in (artwork_objects or [])
        ],
    }

    path.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )


def load_project_file(
    path: Path,
) -> tuple[
    Path,
    list[PaletteLayer],
    dict[str, Any],
    list[ArtworkObject],
]:
    data = json.loads(path.read_text(encoding="utf-8"))

    source_image = Path(data["source_image"])
    layers = [
        PaletteLayer.from_dict(item)
        for item in data["layers"]
    ]
    cleanup = dict(data.get("cleanup", {}))
    artwork_objects = [
        ArtworkObject.from_dict(item)
        for item in data.get("objects", [])
    ]

    return source_image, layers, cleanup, artwork_objects

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from models import PaletteLayer


def default_target_luminances(color_count: int) -> list[int]:
    """
    Produce evenly spaced starter brightness targets.

    These are authoring bands, not calibrated physical TD values.
    """
    if color_count <= 1:
        return [128]

    low = 20
    high = 235
    step = (high - low) / (color_count - 1)

    return [
        int(round(low + index * step))
        for index in range(color_count)
    ]


def normalize_target_luminances(
    values: list[int] | None,
    color_count: int,
) -> list[int]:
    defaults = default_target_luminances(color_count)

    if not values:
        return defaults

    normalized = defaults[:]

    for index in range(min(len(values), color_count)):
        normalized[index] = max(
            0,
            min(255, int(values[index])),
        )

    return normalized


def build_hueforge_input(
    assignment_map: np.ndarray,
    target_luminances: list[int],
) -> Image.Image:
    """
    Convert palette assignments to controlled grayscale luminance bands.

    HueForge can then interpret the authored brightness bands consistently.
    """
    targets = np.asarray(
        target_luminances,
        dtype=np.uint8,
    )

    clipped = np.clip(
        assignment_map,
        0,
        len(targets) - 1,
    )

    grayscale = targets[clipped]

    return Image.fromarray(
        grayscale.astype(np.uint8),
        mode="L",
    ).convert("RGB")


def build_false_color_preview(
    assignment_map: np.ndarray,
    layers: list[PaletteLayer],
) -> Image.Image:
    palette = np.asarray(
        [layer.color for layer in layers],
        dtype=np.uint8,
    )

    clipped = np.clip(
        assignment_map,
        0,
        len(palette) - 1,
    )

    return Image.fromarray(
        palette[clipped],
        mode="RGB",
    )


def write_hueforge_profile(
    path: Path,
    source_name: str,
    layers: list[PaletteLayer],
    target_luminances: list[int],
    object_assignments: list[object],
) -> None:
    data = {
        "application": "ForgePrep",
        "profile_type": "HueForge authoring targets",
        "source_image": source_name,
        "important_note": (
            "Target luminance values are starter authoring bands. "
            "Final physical output still depends on filament transmission "
            "distance, layer height, base thickness, swap heights, and stack order."
        ),
        "filament_stack": [
            {
                "position": index + 1,
                "layer_name": layer.name,
                "display_color_rgb": list(layer.color),
                "filament": layer.filament,
                "target_luminance": int(target_luminances[index]),
            }
            for index, layer in enumerate(layers)
        ],
        "manufacturing_groups": [
            {
                "name": artwork_object.name,
                "target_position": artwork_object.layer_index + 1,
                "target_layer": (
                    layers[artwork_object.layer_index].name
                    if 0 <= artwork_object.layer_index < len(layers)
                    else "Unassigned"
                ),
                "pixel_count": artwork_object.pixel_count,
            }
            for artwork_object in object_assignments
        ],
    }

    path.write_text(
        json.dumps(data, indent=4),
        encoding="utf-8",
    )

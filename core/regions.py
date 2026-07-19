from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
from PIL import Image

from core.analysis import connected_components


NEIGHBORS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


@dataclass
class Region:
    """One connected region belonging to a palette layer."""

    layer_index: int
    region_number: int
    coordinates: list[tuple[int, int]]

    @property
    def size(self) -> int:
        return len(self.coordinates)


def find_regions(
    assignment_map: np.ndarray,
    layer_index: int,
) -> list[Region]:
    """Return a layer's connected regions, largest first."""
    components = connected_components(
        assignment_map == layer_index
    )

    components.sort(key=len, reverse=True)

    return [
        Region(
            layer_index=layer_index,
            region_number=index + 1,
            coordinates=component,
        )
        for index, component in enumerate(components)
    ]


def neighboring_layer_counts(
    assignment_map: np.ndarray,
    region: Region,
) -> Counter[int]:
    """Count the palette layers touching a region."""
    height, width = assignment_map.shape
    counts: Counter[int] = Counter()

    region_points = set(region.coordinates)

    for y, x in region.coordinates:
        for offset_y, offset_x in NEIGHBORS:
            next_y = y + offset_y
            next_x = x + offset_x

            if not (
                0 <= next_y < height
                and 0 <= next_x < width
            ):
                continue

            if (next_y, next_x) in region_points:
                continue

            neighbor_layer = int(
                assignment_map[next_y, next_x]
            )

            if neighbor_layer != region.layer_index:
                counts[neighbor_layer] += 1

    return counts


def best_neighbor_layer(
    assignment_map: np.ndarray,
    region: Region,
) -> int | None:
    """Return the layer most strongly surrounding a region."""
    counts = neighboring_layer_counts(
        assignment_map,
        region,
    )

    if not counts:
        return None

    return counts.most_common(1)[0][0]


def merge_region(
    assignment_map: np.ndarray,
    region: Region,
    target_layer_index: int | None = None,
) -> tuple[np.ndarray, int | None]:
    """
    Merge one region into a target layer.

    When target_layer_index is None, the most common neighboring layer
    is selected automatically.
    """
    target = target_layer_index

    if target is None:
        target = best_neighbor_layer(
            assignment_map,
            region,
        )

    if target is None or target == region.layer_index:
        return assignment_map.copy(), None

    updated = assignment_map.copy()

    for y, x in region.coordinates:
        updated[y, x] = target

    return updated, target


def create_region_overlay(
    reduced_image: Image.Image,
    region: Region,
) -> Image.Image:
    """
    Create a preview with the selected region highlighted in yellow.

    The remaining artwork is dimmed so the region is easy to locate.
    """
    source = np.asarray(
        reduced_image.convert("RGB"),
        dtype=np.uint8,
    )

    dimmed = (
        source.astype(np.float32) * 0.28
    ).astype(np.uint8)

    for y, x in region.coordinates:
        dimmed[y, x] = (255, 225, 0)

    return Image.fromarray(dimmed, mode="RGB")

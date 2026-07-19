from __future__ import annotations

from collections import Counter

import numpy as np

from core.analysis import connected_components


NEIGHBORS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
)


def remove_tiny_islands(
    assignment_map: np.ndarray,
    layer_count: int,
    threshold: int,
) -> tuple[np.ndarray, int]:
    cleaned = assignment_map.copy()
    removed_count = 0
    height, width = cleaned.shape

    for layer_index in range(layer_count):
        components = connected_components(cleaned == layer_index)

        for component in components:
            if len(component) > threshold:
                continue

            boundary_labels: list[int] = []

            for y, x in component:
                for offset_y, offset_x in NEIGHBORS:
                    next_y = y + offset_y
                    next_x = x + offset_x

                    if 0 <= next_y < height and 0 <= next_x < width:
                        label = int(cleaned[next_y, next_x])

                        if label != layer_index:
                            boundary_labels.append(label)

            if not boundary_labels:
                continue

            replacement = Counter(boundary_labels).most_common(1)[0][0]

            for y, x in component:
                cleaned[y, x] = replacement

            removed_count += 1

    return cleaned, removed_count


def fill_small_holes(
    assignment_map: np.ndarray,
    layer_count: int,
    threshold: int,
) -> tuple[np.ndarray, int]:
    cleaned = assignment_map.copy()
    filled_count = 0
    height, width = cleaned.shape

    for layer_index in range(layer_count):
        inverse_mask = cleaned != layer_index
        components = connected_components(inverse_mask)

        for component in components:
            if len(component) > threshold:
                continue

            touches_edge = any(
                y == 0
                or x == 0
                or y == height - 1
                or x == width - 1
                for y, x in component
            )

            if touches_edge:
                continue

            for y, x in component:
                cleaned[y, x] = layer_index

            filled_count += 1

    return cleaned, filled_count

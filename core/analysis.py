from __future__ import annotations

from collections import deque

import numpy as np

from models import LayerAnalysis, PaletteLayer


def connected_components(
    binary_mask: np.ndarray,
) -> list[list[tuple[int, int]]]:
    height, width = binary_mask.shape
    visited = np.zeros(binary_mask.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    neighbors = (
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    )

    for y in range(height):
        for x in range(width):
            if not binary_mask[y, x] or visited[y, x]:
                continue

            queue: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            component: list[tuple[int, int]] = []

            while queue:
                current_y, current_x = queue.popleft()
                component.append((current_y, current_x))

                for offset_y, offset_x in neighbors:
                    next_y = current_y + offset_y
                    next_x = current_x + offset_x

                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and binary_mask[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))

            components.append(component)

    return components


def analyze_assignment(
    assignment_map: np.ndarray,
    layers: list[PaletteLayer],
    tiny_threshold: int,
) -> list[LayerAnalysis]:
    results: list[LayerAnalysis] = []

    for index, layer in enumerate(layers):
        pixel_count = int(np.count_nonzero(assignment_map == index))
        coverage = pixel_count / assignment_map.size * 100

        components = connected_components(assignment_map == index)
        sizes = [len(component) for component in components]

        results.append(
            LayerAnalysis(
                layer_number=index + 1,
                name=layer.name,
                pixel_count=pixel_count,
                coverage_percentage=coverage,
                connected_regions=len(sizes),
                tiny_regions=sum(
                    1 for size in sizes if size <= tiny_threshold
                ),
                smallest_region=min(sizes) if sizes else 0,
                largest_region=max(sizes) if sizes else 0,
            )
        )

    return results

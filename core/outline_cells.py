from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
from PIL import Image


FOUR_NEIGHBORS = (
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
)


@dataclass
class OutlineCell:
    """
    One area enclosed by the selected outline layer.

    Cells are built using four-way connectivity so diagonal contact does not
    leak through a one-pixel corner.
    """

    cell_number: int
    coordinates: list[tuple[int, int]]
    dominant_layer_index: int
    touches_edge: bool

    @property
    def size(self) -> int:
        return len(self.coordinates)


def find_outline_cells(
    assignment_map: np.ndarray,
    outline_layer_index: int,
) -> list[OutlineCell]:
    """
    Segment every non-outline pixel into enclosed cells.

    The selected outline layer acts as an impermeable wall.
    """
    passable = assignment_map != outline_layer_index
    height, width = passable.shape
    visited = np.zeros(passable.shape, dtype=bool)

    cells: list[OutlineCell] = []

    for y in range(height):
        for x in range(width):
            if not passable[y, x] or visited[y, x]:
                continue

            queue: deque[tuple[int, int]] = deque([(y, x)])
            visited[y, x] = True
            coordinates: list[tuple[int, int]] = []
            touches_edge = False
            layer_counts: dict[int, int] = {}

            while queue:
                current_y, current_x = queue.popleft()
                coordinates.append((current_y, current_x))

                if (
                    current_y == 0
                    or current_x == 0
                    or current_y == height - 1
                    or current_x == width - 1
                ):
                    touches_edge = True

                current_layer = int(
                    assignment_map[current_y, current_x]
                )
                layer_counts[current_layer] = (
                    layer_counts.get(current_layer, 0) + 1
                )

                for offset_y, offset_x in FOUR_NEIGHBORS:
                    next_y = current_y + offset_y
                    next_x = current_x + offset_x

                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and passable[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))

            dominant_layer = max(
                layer_counts,
                key=layer_counts.get,
            )

            cells.append(
                OutlineCell(
                    cell_number=0,
                    coordinates=coordinates,
                    dominant_layer_index=dominant_layer,
                    touches_edge=touches_edge,
                )
            )

    cells.sort(key=lambda item: item.size, reverse=True)

    for index, cell in enumerate(cells, start=1):
        cell.cell_number = index

    return cells


def reassign_cell(
    assignment_map: np.ndarray,
    cell: OutlineCell,
    target_layer_index: int,
) -> np.ndarray:
    """Assign an entire enclosed cell to one palette layer."""
    updated = assignment_map.copy()

    for y, x in cell.coordinates:
        updated[y, x] = target_layer_index

    cell.dominant_layer_index = target_layer_index
    return updated


def create_cell_overlay(
    reduced_image: Image.Image,
    cell: OutlineCell,
) -> Image.Image:
    """Dim the artwork and highlight one enclosed cell in yellow."""
    source = np.asarray(
        reduced_image.convert("RGB"),
        dtype=np.uint8,
    )

    overlay = (
        source.astype(np.float32) * 0.25
    ).astype(np.uint8)

    for y, x in cell.coordinates:
        overlay[y, x] = (255, 225, 0)

    return Image.fromarray(overlay, mode="RGB")

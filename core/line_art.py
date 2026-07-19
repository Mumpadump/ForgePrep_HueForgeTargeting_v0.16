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
class LineArtStats:
    outline_pixels: int
    outline_percentage: float
    enclosed_cells: int
    edge_leaks: int
    smallest_cell: int
    largest_cell: int


def luminance_array(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    return (
        rgb[:, :, 0] * 0.299
        + rgb[:, :, 1] * 0.587
        + rgb[:, :, 2] * 0.114
    )


def detect_dark_lines(
    image: Image.Image,
    threshold: int,
) -> np.ndarray:
    """
    Detect likely line art directly from the original image.

    Pixels at or below the luminance threshold are treated as outline.
    """
    threshold = max(0, min(255, int(threshold)))
    return luminance_array(image) <= threshold


def binary_dilate(
    mask: np.ndarray,
    iterations: int = 1,
) -> np.ndarray:
    result = mask.astype(bool).copy()

    for _ in range(max(0, int(iterations))):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        expanded = np.zeros_like(result)

        for offset_y in range(3):
            for offset_x in range(3):
                expanded |= padded[
                    offset_y:offset_y + result.shape[0],
                    offset_x:offset_x + result.shape[1],
                ]

        result = expanded

    return result


def binary_erode(
    mask: np.ndarray,
    iterations: int = 1,
) -> np.ndarray:
    result = mask.astype(bool).copy()

    for _ in range(max(0, int(iterations))):
        padded = np.pad(result, 1, mode="constant", constant_values=False)
        eroded = np.ones_like(result)

        for offset_y in range(3):
            for offset_x in range(3):
                eroded &= padded[
                    offset_y:offset_y + result.shape[0],
                    offset_x:offset_x + result.shape[1],
                ]

        result = eroded

    return result


def repair_line_mask(
    mask: np.ndarray,
    close_iterations: int,
    thicken_iterations: int,
) -> np.ndarray:
    """
    Repair small line gaps, then optionally thicken the outline.

    Closing is dilation followed by erosion. It can bridge narrow gaps while
    approximately preserving the original line thickness.
    """
    repaired = mask.astype(bool).copy()

    if close_iterations > 0:
        repaired = binary_dilate(repaired, close_iterations)
        repaired = binary_erode(repaired, close_iterations)

    if thicken_iterations > 0:
        repaired = binary_dilate(repaired, thicken_iterations)

    return repaired


def find_non_line_cells(
    line_mask: np.ndarray,
) -> list[tuple[list[tuple[int, int]], bool]]:
    """
    Return non-line cells and whether each cell touches the image edge.
    """
    passable = ~line_mask.astype(bool)
    height, width = passable.shape
    visited = np.zeros(passable.shape, dtype=bool)
    cells: list[tuple[list[tuple[int, int]], bool]] = []

    for start_y in range(height):
        for start_x in range(width):
            if not passable[start_y, start_x] or visited[start_y, start_x]:
                continue

            queue: deque[tuple[int, int]] = deque([(start_y, start_x)])
            visited[start_y, start_x] = True
            coordinates: list[tuple[int, int]] = []
            touches_edge = False

            while queue:
                y, x = queue.popleft()
                coordinates.append((y, x))

                if (
                    y == 0
                    or x == 0
                    or y == height - 1
                    or x == width - 1
                ):
                    touches_edge = True

                for offset_y, offset_x in FOUR_NEIGHBORS:
                    next_y = y + offset_y
                    next_x = x + offset_x

                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and passable[next_y, next_x]
                        and not visited[next_y, next_x]
                    ):
                        visited[next_y, next_x] = True
                        queue.append((next_y, next_x))

            cells.append((coordinates, touches_edge))

    cells.sort(key=lambda item: len(item[0]), reverse=True)
    return cells


def analyze_line_mask(
    line_mask: np.ndarray,
) -> LineArtStats:
    cells = find_non_line_cells(line_mask)
    enclosed_sizes = [
        len(coordinates)
        for coordinates, touches_edge in cells
        if not touches_edge
    ]
    edge_leaks = sum(
        1
        for _coordinates, touches_edge in cells
        if touches_edge
    )

    outline_pixels = int(np.count_nonzero(line_mask))
    total_pixels = int(line_mask.size)

    return LineArtStats(
        outline_pixels=outline_pixels,
        outline_percentage=(
            outline_pixels / total_pixels * 100
            if total_pixels
            else 0.0
        ),
        enclosed_cells=len(enclosed_sizes),
        edge_leaks=edge_leaks,
        smallest_cell=min(enclosed_sizes) if enclosed_sizes else 0,
        largest_cell=max(enclosed_sizes) if enclosed_sizes else 0,
    )


def line_mask_image(
    line_mask: np.ndarray,
) -> Image.Image:
    """
    Return a black-line-on-white-background preview.
    """
    pixels = np.where(
        line_mask,
        0,
        255,
    ).astype(np.uint8)

    return Image.fromarray(pixels, mode="L")


def comparison_overlay(
    original_image: Image.Image,
    original_mask: np.ndarray,
    repaired_mask: np.ndarray,
) -> Image.Image:
    """
    Overlay line-analysis status on the original artwork.

    Existing line pixels are green.
    Newly added repair pixels are red.
    """
    source = np.asarray(
        original_image.convert("RGB"),
        dtype=np.uint8,
    ).copy()

    dimmed = (
        source.astype(np.float32) * 0.35
    ).astype(np.uint8)

    unchanged = original_mask & repaired_mask
    added = repaired_mask & ~original_mask

    dimmed[unchanged] = (40, 220, 90)
    dimmed[added] = (255, 55, 55)

    return Image.fromarray(dimmed, mode="RGB")

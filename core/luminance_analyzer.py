from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class LuminanceLevel:
    index: int
    center: int
    minimum: int
    maximum: int
    pixel_count: int

    @property
    def display_name(self) -> str:
        return f"Level {self.index + 1}"


@dataclass
class LuminanceAnalysis:
    luminance_image: np.ndarray
    level_map: np.ndarray
    quantized_luminance: np.ndarray
    levels: list[LuminanceLevel]
    histogram: np.ndarray

    def create_grayscale_preview(self) -> Image.Image:
        return Image.fromarray(
            self.quantized_luminance.astype(np.uint8),
            mode="L",
        ).convert("RGB")

    def create_false_color_preview(
        self,
        colors: Sequence[tuple[int, int, int]],
    ) -> Image.Image:
        if len(colors) != len(self.levels):
            raise ValueError(
                f"Expected {len(self.levels)} colors, got {len(colors)}."
            )

        height, width = self.level_map.shape
        output = np.zeros((height, width, 3), dtype=np.uint8)

        for level_index, color in enumerate(colors):
            output[self.level_map == level_index] = color

        return Image.fromarray(output, mode="RGB")

    def create_level_mask(self, level_index: int) -> Image.Image:
        if not 0 <= level_index < len(self.levels):
            raise IndexError("Level index is outside the valid range.")

        mask = np.where(
            self.level_map == level_index,
            255,
            0,
        ).astype(np.uint8)

        return Image.fromarray(mask, mode="L")


def rgb_to_luminance(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    luminance = (
        0.2126 * rgb[:, :, 0]
        + 0.7152 * rgb[:, :, 1]
        + 0.0722 * rgb[:, :, 2]
    )
    return np.clip(np.rint(luminance), 0, 255).astype(np.uint8)


def analyze_luminance(
    image: Image.Image,
    number_of_levels: int,
    max_iterations: int = 100,
) -> LuminanceAnalysis:
    if number_of_levels < 2:
        raise ValueError("At least two luminance levels are required.")
    if number_of_levels > 16:
        raise ValueError("A maximum of 16 levels is supported.")

    luminance = rgb_to_luminance(image)
    histogram = np.bincount(
        luminance.ravel(),
        minlength=256,
    ).astype(np.int64)

    centers = _initial_centers(histogram, number_of_levels)
    centers = _weighted_kmeans(
        histogram,
        centers,
        max_iterations,
    )
    centers = np.sort(
        np.clip(np.rint(centers), 0, 255)
    ).astype(np.uint8)
    centers = _ensure_unique_centers(centers)

    boundaries = _centers_to_boundaries(centers)
    level_map = np.digitize(
        luminance,
        boundaries,
        right=False,
    ).astype(np.uint8)

    quantized = centers[level_map]
    levels: list[LuminanceLevel] = []

    for index, center in enumerate(centers):
        minimum = 0 if index == 0 else int(boundaries[index - 1])
        maximum = (
            255
            if index == len(centers) - 1
            else int(boundaries[index] - 1)
        )
        levels.append(
            LuminanceLevel(
                index=index,
                center=int(center),
                minimum=minimum,
                maximum=maximum,
                pixel_count=int(np.count_nonzero(level_map == index)),
            )
        )

    return LuminanceAnalysis(
        luminance_image=luminance,
        level_map=level_map,
        quantized_luminance=quantized,
        levels=levels,
        histogram=histogram,
    )


def _initial_centers(
    histogram: np.ndarray,
    number_of_levels: int,
) -> np.ndarray:
    total = int(histogram.sum())
    if total == 0:
        return np.linspace(0, 255, number_of_levels)

    cumulative = np.cumsum(histogram)
    return np.array(
        [
            float(
                np.searchsorted(
                    cumulative,
                    ((index + 0.5) / number_of_levels) * total,
                )
            )
            for index in range(number_of_levels)
        ],
        dtype=np.float64,
    )


def _weighted_kmeans(
    histogram: np.ndarray,
    centers: np.ndarray,
    max_iterations: int,
) -> np.ndarray:
    values = np.arange(256, dtype=np.float64)
    centers = centers.astype(np.float64).copy()

    for _ in range(max_iterations):
        assignments = np.argmin(
            np.abs(values[:, None] - centers[None, :]),
            axis=1,
        )
        new_centers = centers.copy()

        for index in range(len(centers)):
            mask = assignments == index
            weights = histogram[mask]
            if weights.sum():
                new_centers[index] = np.average(
                    values[mask],
                    weights=weights,
                )

        if np.allclose(new_centers, centers, atol=0.1):
            centers = new_centers
            break

        centers = new_centers

    return centers


def _ensure_unique_centers(centers: np.ndarray) -> np.ndarray:
    adjusted = centers.astype(np.int16).copy()

    for index in range(1, len(adjusted)):
        if adjusted[index] <= adjusted[index - 1]:
            adjusted[index] = adjusted[index - 1] + 1

    if adjusted[-1] > 255:
        adjusted -= adjusted[-1] - 255

    for index in range(len(adjusted) - 2, -1, -1):
        if adjusted[index] >= adjusted[index + 1]:
            adjusted[index] = adjusted[index + 1] - 1

    return np.clip(adjusted, 0, 255).astype(np.uint8)


def _centers_to_boundaries(centers: np.ndarray) -> np.ndarray:
    return (
        np.floor(
            (
                centers[:-1].astype(np.float32)
                + centers[1:].astype(np.float32)
            )
            / 2.0
        ).astype(np.uint8)
        + 1
    )

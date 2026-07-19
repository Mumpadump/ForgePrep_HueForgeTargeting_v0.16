from __future__ import annotations

import numpy as np
from PIL import Image


def rgb_to_hex(color: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = value.strip().lstrip("#")

    if len(cleaned) != 6:
        raise ValueError("Enter six hexadecimal characters, such as #D95B86.")

    try:
        return (
            int(cleaned[0:2], 16),
            int(cleaned[2:4], 16),
            int(cleaned[4:6], 16),
        )
    except ValueError as error:
        raise ValueError("Hex colors may contain only 0–9 and A–F.") from error


def readable_text_color(color: tuple[int, int, int]) -> str:
    red, green, blue = color
    brightness = (red * 299 + green * 587 + blue * 114) / 1000
    return "black" if brightness > 145 else "white"


def perceived_brightness(color: tuple[int, int, int]) -> float:
    red, green, blue = color
    return red * 0.299 + green * 0.587 + blue * 0.114


def suggest_palette(
    image: Image.Image,
    color_count: int,
) -> list[tuple[int, int, int]]:
    analysis_image = image.convert("RGB").copy()
    analysis_image.thumbnail((900, 900), Image.Resampling.LANCZOS)

    quantized = analysis_image.quantize(
        colors=color_count,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )

    palette_data = quantized.getpalette()
    color_counts = quantized.getcolors(
        maxcolors=analysis_image.width * analysis_image.height
    )

    if palette_data is None or color_counts is None:
        raise RuntimeError("The detected palette could not be read.")

    colors: list[tuple[int, int, int]] = []

    for _pixel_count, palette_index in color_counts:
        start = palette_index * 3
        values = palette_data[start:start + 3]

        if len(values) == 3:
            color = tuple(int(value) for value in values)

            if color not in colors:
                colors.append(color)

    colors.sort(key=perceived_brightness)
    return colors[:color_count]


def reduce_to_palette(
    image: Image.Image,
    palette: list[tuple[int, int, int]],
) -> tuple[Image.Image, np.ndarray]:
    if not palette:
        raise ValueError("The palette cannot be empty.")

    pixels = np.asarray(image.convert("RGB"), dtype=np.int32)
    palette_array = np.asarray(palette, dtype=np.int32)

    differences = pixels[:, :, None, :] - palette_array[None, None, :, :]
    distances = np.sum(differences * differences, axis=3)
    assignment_map = np.argmin(distances, axis=2)

    reduced_pixels = palette_array[assignment_map].astype(np.uint8)
    reduced_image = Image.fromarray(reduced_pixels, mode="RGB")

    return reduced_image, assignment_map


def image_from_assignment(
    assignment_map: np.ndarray,
    palette: list[tuple[int, int, int]],
) -> Image.Image:
    palette_array = np.asarray(palette, dtype=np.uint8)
    pixels = palette_array[assignment_map]
    return Image.fromarray(pixels, mode="RGB")


def create_mask(
    assignment_map: np.ndarray,
    layer_index: int,
) -> Image.Image:
    mask_array = np.where(
        assignment_map == layer_index,
        255,
        0,
    ).astype(np.uint8)

    return Image.fromarray(mask_array, mode="L")

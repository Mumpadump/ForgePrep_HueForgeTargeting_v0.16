from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import numpy as np

from core.luminance_analyzer import LuminanceAnalysis


class LuminanceHistogramWindow(tk.Toplevel):
    """Display the luminance histogram and detected manufacturing ranges."""

    def __init__(
        self,
        parent: tk.Misc,
        analysis: LuminanceAnalysis,
    ) -> None:
        super().__init__(parent)

        self.analysis = analysis
        self.title("Luminance Histogram")
        self.geometry("940x560")
        self.minsize(760, 460)
        self.transient(parent)

        self.canvas = tk.Canvas(
            self,
            background="white",
            highlightthickness=1,
            highlightbackground="#999999",
        )
        self.canvas.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(12, 6),
        )

        ttk.Label(
            self,
            text=(
                "The vertical bands show the detected luminance families. "
                "Histogram height represents pixel frequency."
            ),
            anchor="center",
        ).pack(fill="x", padx=12, pady=(0, 12))

        self.canvas.bind("<Configure>", self._draw)

    def _draw(self, event=None) -> None:
        self.canvas.delete("all")

        width = max(self.canvas.winfo_width(), 300)
        height = max(self.canvas.winfo_height(), 240)

        left = 55
        right = 20
        top = 35
        bottom = 55

        chart_width = width - left - right
        chart_height = height - top - bottom

        histogram = self.analysis.histogram.astype(np.float64)
        if histogram.max() > 0:
            histogram /= histogram.max()

        # Draw detected level bands.
        for index, level in enumerate(self.analysis.levels):
            x1 = left + (level.minimum / 255.0) * chart_width
            x2 = left + ((level.maximum + 1) / 256.0) * chart_width

            gray = int(
                235 if index % 2 == 0 else 215
            )
            fill = f"#{gray:02x}{gray:02x}{gray:02x}"

            self.canvas.create_rectangle(
                x1,
                top,
                x2,
                top + chart_height,
                fill=fill,
                outline="",
            )

            self.canvas.create_text(
                (x1 + x2) / 2,
                top + 14,
                text=f"Level {index + 1}",
                font=("Segoe UI", 9, "bold"),
            )

            center_x = left + (level.center / 255.0) * chart_width
            self.canvas.create_line(
                center_x,
                top,
                center_x,
                top + chart_height,
                dash=(4, 3),
                width=1,
            )

        # Histogram polyline.
        points: list[float] = []
        for value in range(256):
            x = left + (value / 255.0) * chart_width
            y = top + chart_height - histogram[value] * chart_height
            points.extend((x, y))

        if len(points) >= 4:
            self.canvas.create_line(
                *points,
                fill="black",
                width=2,
                smooth=True,
            )

        # Axes.
        self.canvas.create_line(
            left,
            top + chart_height,
            left + chart_width,
            top + chart_height,
            width=2,
        )
        self.canvas.create_line(
            left,
            top,
            left,
            top + chart_height,
            width=2,
        )

        for value in (0, 32, 64, 96, 128, 160, 192, 224, 255):
            x = left + (value / 255.0) * chart_width
            self.canvas.create_line(
                x,
                top + chart_height,
                x,
                top + chart_height + 5,
            )
            self.canvas.create_text(
                x,
                top + chart_height + 20,
                text=str(value),
                font=("Segoe UI", 8),
            )

        self.canvas.create_text(
            left + chart_width / 2,
            height - 10,
            text="Luminance: 0 = black, 255 = white",
            font=("Segoe UI", 9),
        )

        self.canvas.create_text(
            16,
            top + chart_height / 2,
            text="Pixel\nfrequency",
            anchor="w",
            justify="center",
            font=("Segoe UI", 9),
        )

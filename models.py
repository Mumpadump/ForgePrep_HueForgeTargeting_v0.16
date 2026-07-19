from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PaletteLayer:
    name: str
    color: tuple[int, int, int]
    filament: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["color"] = list(self.color)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PaletteLayer":
        return cls(
            name=str(data.get("name", "Layer")),
            color=tuple(int(value) for value in data["color"]),
            filament=str(data.get("filament", "")),
        )


@dataclass
class LayerAnalysis:
    layer_number: int
    name: str
    pixel_count: int
    coverage_percentage: float
    connected_regions: int
    tiny_regions: int
    smallest_region: int
    largest_region: int

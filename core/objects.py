from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np


@dataclass
class ArtworkObject:
    """
    A user-defined object made from one or more connected regions.

    Objects are intentionally user-defined in v0.11. ForgePrep does not yet
    claim to understand semantic objects such as hats or faces automatically.
    """

    name: str
    layer_index: int
    coordinates: list[tuple[int, int]]

    @property
    def pixel_count(self) -> int:
        return len(self.coordinates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "layer_index": self.layer_index,
            "coordinates": [
                [int(y), int(x)]
                for y, x in self.coordinates
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtworkObject":
        return cls(
            name=str(data.get("name", "Object")),
            layer_index=int(data.get("layer_index", 0)),
            coordinates=[
                (int(point[0]), int(point[1]))
                for point in data.get("coordinates", [])
            ],
        )


def create_object_from_regions(
    name: str,
    layer_index: int,
    regions: list[object],
) -> ArtworkObject:
    coordinates: set[tuple[int, int]] = set()

    for region in regions:
        coordinates.update(region.coordinates)

    return ArtworkObject(
        name=name.strip() or "Object",
        layer_index=layer_index,
        coordinates=sorted(coordinates),
    )


def reassign_object(
    assignment_map: np.ndarray,
    artwork_object: ArtworkObject,
    target_layer_index: int,
) -> np.ndarray:
    updated = assignment_map.copy()

    for y, x in artwork_object.coordinates:
        if (
            0 <= y < updated.shape[0]
            and 0 <= x < updated.shape[1]
        ):
            updated[y, x] = target_layer_index

    artwork_object.layer_index = target_layer_index
    return updated


def object_mask(
    shape: tuple[int, int],
    artwork_object: ArtworkObject,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=bool)

    for y, x in artwork_object.coordinates:
        if 0 <= y < shape[0] and 0 <= x < shape[1]:
            mask[y, x] = True

    return mask

from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from PIL import Image

@dataclass
class ManufacturingMap:
    original_rgb: np.ndarray
    luminance: np.ndarray
    palette_index: np.ndarray
    edge_strength: np.ndarray
    outline_mask: np.ndarray
    object_id: np.ndarray
    confidence: np.ndarray

    @property
    def shape(self) -> tuple[int, int]:
        return self.palette_index.shape

def calculate_luminance(rgb: np.ndarray) -> np.ndarray:
    pixels = rgb.astype(np.float32)
    return pixels[:, :, 0] * 0.299 + pixels[:, :, 1] * 0.587 + pixels[:, :, 2] * 0.114

def calculate_edge_strength(rgb: np.ndarray) -> np.ndarray:
    pixels = rgb.astype(np.float32)
    horizontal = np.zeros(pixels.shape[:2], dtype=np.float32)
    vertical = np.zeros(pixels.shape[:2], dtype=np.float32)
    horizontal[:, 1:] = np.linalg.norm(pixels[:, 1:, :] - pixels[:, :-1, :], axis=2)
    vertical[1:, :] = np.linalg.norm(pixels[1:, :, :] - pixels[:-1, :, :], axis=2)
    strength = np.maximum(horizontal, vertical)
    maximum = float(strength.max())
    if maximum > 0:
        strength = strength / maximum * 255.0
    return strength.astype(np.uint8)

def build_object_id_map(shape: tuple[int, int], artwork_objects: list[object]) -> np.ndarray:
    object_id = np.full(shape, -1, dtype=np.int32)
    for index, artwork_object in enumerate(artwork_objects):
        for y, x in artwork_object.coordinates:
            if 0 <= y < shape[0] and 0 <= x < shape[1]:
                object_id[y, x] = index
    return object_id

def calculate_confidence(edge_strength: np.ndarray, outline_mask: np.ndarray, object_id: np.ndarray) -> np.ndarray:
    confidence = np.full(edge_strength.shape, 35.0, dtype=np.float32)
    confidence += edge_strength.astype(np.float32) / 255.0 * 35.0
    confidence[outline_mask] = np.maximum(confidence[outline_mask], 80.0)
    confidence[object_id >= 0] = 100.0
    return np.clip(confidence, 0, 100).astype(np.uint8)

def build_manufacturing_map(original_image: Image.Image, assignment_map: np.ndarray, artwork_objects: list[object], repaired_line_mask: np.ndarray | None = None, dark_line_threshold: int = 55) -> ManufacturingMap:
    rgb = np.asarray(original_image.convert('RGB'), dtype=np.uint8)
    luminance = calculate_luminance(rgb)
    edge_strength = calculate_edge_strength(rgb)
    outline_mask = repaired_line_mask.astype(bool) if repaired_line_mask is not None else luminance <= dark_line_threshold
    object_id = build_object_id_map(assignment_map.shape, artwork_objects)
    confidence = calculate_confidence(edge_strength, outline_mask, object_id)
    return ManufacturingMap(rgb, luminance, assignment_map.copy(), edge_strength, outline_mask, object_id, confidence)

def edge_preview(manufacturing_map: ManufacturingMap) -> Image.Image:
    return Image.fromarray(manufacturing_map.edge_strength, mode='L')

def confidence_preview(manufacturing_map: ManufacturingMap) -> Image.Image:
    confidence = manufacturing_map.confidence.astype(np.float32) / 100.0
    red = np.where(confidence < 0.5, 255, (1.0 - confidence) * 510)
    green = np.where(confidence > 0.5, 255, confidence * 510)
    blue = np.zeros_like(confidence)
    rgb = np.stack([red, green, blue], axis=2)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode='RGB')

def object_preview(manufacturing_map: ManufacturingMap) -> Image.Image:
    height, width = manufacturing_map.shape
    colors = np.array([(60,150,255),(255,210,40),(255,90,140),(100,220,120),(190,110,255),(255,145,50),(50,220,220),(230,230,230)], dtype=np.uint8)
    preview = np.full((height, width, 3), 35, dtype=np.uint8)
    assigned = manufacturing_map.object_id >= 0
    if np.any(assigned):
        indexes = manufacturing_map.object_id[assigned] % len(colors)
        preview[assigned] = colors[indexes]
    return Image.fromarray(preview, mode='RGB')

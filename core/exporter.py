from __future__ import annotations

import html
import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

from core.palette import create_mask, rgb_to_hex
from models import LayerAnalysis, PaletteLayer
from core.objects import ArtworkObject


def safe_filename(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value.strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or "Layer"


def create_html_report(
    source_name: str,
    source_image: Image.Image,
    layers: list[PaletteLayer],
    analysis: list[LayerAnalysis],
    mask_records: list[dict[str, object]],
    cleanup_summary: str,
    version: str,
) -> str:
    rows: list[str] = []

    for index, layer in enumerate(layers):
        record = mask_records[index]
        layer_analysis = analysis[index] if index < len(analysis) else None

        rows.append(
            "<tr>"
            f"<td>{index + 1}</td>"
            f"<td>{html.escape(layer.name)}</td>"
            f"<td><span class='swatch' "
            f"style='background:{rgb_to_hex(layer.color)}'></span>"
            f"{rgb_to_hex(layer.color)}</td>"
            f"<td>{html.escape(layer.filament or 'Not specified')}</td>"
            f"<td>{record['pixel_percentage']:.3f}%</td>"
            f"<td>{layer_analysis.connected_regions if layer_analysis else '—'}</td>"
            f"<td>{layer_analysis.tiny_regions if layer_analysis else '—'}</td>"
            "</tr>"
        )

    total_tiny = sum(item.tiny_regions for item in analysis)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ForgePrep Report — {html.escape(source_name)}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; max-width: 1050px; margin: 40px auto; padding: 0 24px; color: #222; }}
h1 {{ margin-bottom: 4px; }}
.summary {{ display: flex; gap: 16px; flex-wrap: wrap; margin: 24px 0; }}
.card {{ border: 1px solid #ccc; border-radius: 10px; padding: 14px 18px; min-width: 170px; }}
.value {{ font-size: 1.5rem; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ border-bottom: 1px solid #ddd; padding: 10px; text-align: left; }}
th {{ background: #f3f3f3; }}
.swatch {{ display: inline-block; width: 24px; height: 24px; vertical-align: middle; margin-right: 9px; border: 1px solid #777; }}
.note {{ border-left: 5px solid #c98700; background: #fff7df; padding: 14px; margin-top: 22px; }}
</style>
</head>
<body>
<h1>ForgePrep Production Report</h1>
<p>{html.escape(source_name)} • ForgePrep v{version}</p>

<div class="summary">
  <div class="card"><div>Image size</div><div class="value">{source_image.width} × {source_image.height}</div></div>
  <div class="card"><div>Final colors</div><div class="value">{len(layers)}</div></div>
  <div class="card"><div>Tiny regions</div><div class="value">{total_tiny if analysis else "—"}</div></div>
</div>

<p><strong>Cleanup:</strong> {html.escape(cleanup_summary)}</p>

<table>
<thead>
<tr><th>Layer</th><th>Name</th><th>Color</th><th>Filament</th><th>Coverage</th><th>Regions</th><th>Tiny regions</th></tr>
</thead>
<tbody>{''.join(rows)}</tbody>
</table>

<div class="note"><strong>Manufacturing note:</strong> Review each layer mask before SVG export.</div>
</body>
</html>
"""


def export_project(
    destination: Path,
    source_path: Path,
    source_image: Image.Image,
    reduced_image: Image.Image,
    assignment_map: np.ndarray,
    layers: list[PaletteLayer],
    analysis: list[LayerAnalysis],
    cleanup_settings: dict[str, object],
    cleanup_summary: str,
    version: str,
    artwork_objects: list[ArtworkObject] | None = None,
) -> Path:
    source_name = source_path.stem
    project_folder = destination / f"{source_name}_ForgePrep"
    masks_folder = project_folder / "Masks"

    masks_folder.mkdir(parents=True, exist_ok=True)

    reduced_filename = (
        f"{source_name}_{len(layers)}color_HueForge.png"
    )
    reduced_path = project_folder / reduced_filename
    reduced_image.save(reduced_path)

    mask_records: list[dict[str, object]] = []

    for index, layer in enumerate(layers):
        mask_filename = (
            f"{index + 1:02d}_{safe_filename(layer.name)}_Mask.png"
        )
        mask_path = masks_folder / mask_filename
        create_mask(assignment_map, index).save(mask_path)

        pixel_count = int(np.count_nonzero(assignment_map == index))
        percentage = pixel_count / assignment_map.size * 100

        mask_records.append(
            {
                "layer": index + 1,
                "name": layer.name,
                "filament": layer.filament,
                "hex": rgb_to_hex(layer.color),
                "rgb": list(layer.color),
                "mask_file": str(Path("Masks") / mask_filename),
                "pixel_count": pixel_count,
                "pixel_percentage": round(percentage, 3),
            }
        )

    manifest = {
        "application": "ForgePrep",
        "version": version,
        "source_image": str(source_path),
        "image_width_pixels": source_image.width,
        "image_height_pixels": source_image.height,
        "final_color_count": len(layers),
        "hueforge_image": reduced_filename,
        "cleanup": {
            **cleanup_settings,
            "summary": cleanup_summary,
        },
        "layers": mask_records,
        "analysis": [asdict(item) for item in analysis],
        "objects": [
            artwork_object.to_dict()
            for artwork_object in (artwork_objects or [])
        ],
    }

    manifest_path = (
        project_folder / f"{source_name}_ForgePrep_Project.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=4),
        encoding="utf-8",
    )

    report_path = (
        project_folder / f"{source_name}_ForgePrep_Report.html"
    )
    report_path.write_text(
        create_html_report(
            source_name=source_name,
            source_image=source_image,
            layers=layers,
            analysis=analysis,
            mask_records=mask_records,
            cleanup_summary=cleanup_summary,
            version=version,
        ),
        encoding="utf-8",
    )

    return project_folder

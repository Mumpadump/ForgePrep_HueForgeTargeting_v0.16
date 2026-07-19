# ForgePrep HueForge Targeting v0.16

This release splits ForgePrep into smaller files so each part has one job.

## Files

- `main.py` — starts ForgePrep
- `ui/app.py` — window and button behavior
- `core/palette.py` — palette suggestion and color reduction
- `core/cleanup.py` — tiny-island removal and hole filling
- `core/analysis.py` — connected-region statistics
- `core/exporter.py` — PNG, masks, JSON, and HTML report export
- `core/project_io.py` — save and load editable projects
- `models.py` — project data structures
- `settings.py` — application constants

## First-time setup

1. Extract the folder.
2. Double-click `setup_forgeprep.bat`.
3. Double-click `launch_forgeprep.bat`.

## Running from VS Code

```powershell
.\.venv\Scripts\python.exe main.py
```

## Current workflow

1. Open artwork.
2. Choose 2–8 colors.
3. Adjust layer colors and names.
4. Analyze artwork.
5. Remove tiny islands and fill small holes.
6. Export a HueForge-ready PNG, masks, JSON manifest, and HTML report.


## Region Explorer

Click **Region Explorer** after opening an image.

- Choose a palette layer.
- Show all regions or only regions below a pixel threshold.
- Select a region to highlight it in yellow.
- Merge the selected region into its most common neighboring layer.
- Choose a specific destination layer when automatic merging is not desired.
- Merge every currently displayed region in one action.

The main window's **Restore Uncleaned Preview** button restores the original
palette assignment and removes all interactive region edits.


## Object Explorer

Object Explorer adds a manual semantic layer above connected regions.

1. Choose the palette layer containing the object.
2. Select every connected region that belongs to the object.
3. Click **Create Object from Selected Regions**.
4. Name it, such as `Hat`, `Face`, `Antlers`, or `Background`.
5. Select the saved object and move it to another palette layer as one unit.

This solves an important limitation: two visual objects may use nearly the same
source color but still need separate manufacturing treatment.

Version 0.11 does **not** automatically recognize semantic objects. The user
defines them deliberately. Object definitions are saved in ForgePrep project
files and included in export manifests.


## Outline Cell Explorer

The Outline Cell Explorer uses a selected palette layer, normally black, as a
set of walls.

Every non-outline area enclosed by those walls becomes a selectable cell.

This is useful when a face and hat have similar colors but remain separated by
black comic line art:

1. Open **Outline Explorer**.
2. Select the black/outline layer.
3. Select an enclosed cell.
4. Assign the cell to a different palette layer, or turn it into a named object.

The engine uses four-way connectivity to reduce diagonal leakage through
one-pixel corners. It is still dependent on continuous outlines; gaps in the
line art can cause two intended objects to become one cell.


## Line Art Analyzer

Line Art Analyzer works from the original artwork rather than the reduced
palette image.

- Dark-line threshold controls which original pixels count as line art.
- Close gaps performs conservative binary closing.
- Thicken lines expands the outline after gap repair.
- Existing line pixels appear green in the repair overlay.
- Newly added repair pixels appear red.

After saving the repaired mask, open Outline Explorer and enable
**Use repaired line mask**.

This release does not automatically identify specific gaps or guarantee that
every repaired cell is a real semantic object. The repair preview must be
reviewed visually before it is used.


## Object Builder

Object Builder is the first click-based semantic editor in ForgePrep.

1. Create an object such as `Face`.
2. Click enclosed cells on the artwork to add them to the object.
3. Click a selected cell again to remove it.
4. Create other objects such as `Hat`, `Antlers`, and `Clothing`.
5. Reassign the entire object to a palette layer.

Yellow cells belong to the currently selected object. Blue cells belong to
other saved objects.

Object Builder uses the repaired line mask when available. It still depends on
the quality of the detected cells, but it no longer requires one visual object
to be a single connected region.


## Manufacturing Map

Version 0.15 introduces a shared per-pixel model containing original color, luminance, palette assignment, edge strength, outline membership, manufacturing-group ID, and confidence. Open **Manufacturing Map** to inspect edge strength, confidence, and saved groups. This is the foundation for Smart Brush, manufacturing scoring, SVG, and 3MF export.


## HueForge Color Targeting

Version 0.16 connects saved manufacturing groups directly to physical filament
intent.

Workflow:

1. Open artwork and generate the four-color preview.
2. Name each filament in the Final Manufacturing Palette.
3. Open Object Builder to create masks only where automatic palette reduction
   cannot distinguish areas reliably.
4. Open HueForge Targeting.
5. Select a group and assign it to the physical filament it must become.
6. Tune the four grayscale brightness bands.
7. Export the HueForge input PNG and matching JSON profile.

The Target Filament Preview shows the intended physical colors.

The Actual HueForge Input preview shows the grayscale bands HueForge receives.

Important: the brightness values in v0.16 are starter authoring bands. They ensure
clear separation in the source image, but they do not calculate physical
transmission-distance behavior. Final output still depends on the actual
filaments, TD values, layer height, base thickness, swap heights, and stack order.

## ForgePrep v0.18.1 — Luminance Manufacturing

- Added Build Luminance Map alongside Suggest Palette.
- Detects an exact requested number of brightness families.
- Reuses existing mask previews for luminance levels.
- Displays brightness centers, ranges, coverage, and separation rating.
- Keeps the original RGB workflow intact for comparison and fallback.


from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk



from PIL import Image, ImageTk

from core.analysis import analyze_assignment
from core.cleanup import fill_small_holes, remove_tiny_islands
from core.exporter import export_project
from core.palette import (
    create_mask,
    hex_to_rgb,
    image_from_assignment,
    readable_text_color,
    reduce_to_palette,
    rgb_to_hex,
    suggest_palette,
)
from core.project_io import load_project_file, save_project_file
from ui.region_explorer import RegionExplorer
from ui.object_explorer import ObjectExplorer
from ui.outline_explorer import OutlineExplorer
from ui.line_analyzer import LineArtAnalyzer
from ui.object_builder import ObjectBuilder
from ui.manufacturing_map_viewer import ManufacturingMapViewer
from ui.hueforge_targeting import HueForgeTargeting
from models import LayerAnalysis, PaletteLayer
from settings import (
    APP_VERSION,
    DEFAULT_COLOR_COUNT,
    DEFAULT_HOLE_THRESHOLD,
    DEFAULT_LAYER_COLORS,
    DEFAULT_LAYER_NAMES,
    DEFAULT_TINY_THRESHOLD,
    MAX_COLORS,
    MIN_COLORS,
    PREVIEW_SIZE,
)
from core.luminance_analyzer import (
    LuminanceAnalysis,
    analyze_luminance,
)

class ForgePrepApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root

        self.image_path: Path | None = None
        self.original_image: Image.Image | None = None
        self.reduced_image: Image.Image | None = None

        self.assignment_map = None
        self.original_assignment_map = None

        self.original_photo: ImageTk.PhotoImage | None = None
        self.output_photo: ImageTk.PhotoImage | None = None
        self.mask_photo: ImageTk.PhotoImage | None = None

        self.layers: list[PaletteLayer] = []
        self.layer_rows: list[dict[str, object]] = []
        self.analysis: list[LayerAnalysis] = []
        self.artwork_objects = []
        self.repaired_line_mask = None
        self.line_repair_settings = {}
        self.manufacturing_map = None
        self.hueforge_target_luminances = []

        self.selected_mask_index = 0
        self.preview_job: str | None = None

        self.color_count_var = tk.IntVar(value=DEFAULT_COLOR_COUNT)
        self.status_var = tk.StringVar(value="Open an image to begin.")
        self.layer_stats_var = tk.StringVar(
            value="Select a layer mask to inspect it."
        )

        self.remove_islands_var = tk.BooleanVar(value=True)
        self.fill_holes_var = tk.BooleanVar(value=True)
        self.island_threshold_var = tk.IntVar(
            value=DEFAULT_TINY_THRESHOLD
        )
        self.hole_threshold_var = tk.IntVar(
            value=DEFAULT_HOLE_THRESHOLD
        )
        self.cleanup_summary_var = tk.StringVar(
            value="Cleanup has not been applied."
        )

        self.build_window()
        self.create_default_layers(DEFAULT_COLOR_COUNT)

    def build_window(self) -> None:
        self.root.title(f"ForgePrep v{APP_VERSION}")
        self.root.geometry("1320x1040")
        self.root.minsize(1080, 850)

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text=f"ForgePrep v{APP_VERSION} — HueForge Targeting",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 10))

        toolbar = ttk.Frame(main)
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(
            toolbar,
            text="Open Image",
            command=self.open_image,
        ).pack(side="left", padx=(0, 6))

        ttk.Label(toolbar, text="Final colors:").pack(
            side="left", padx=(10, 4)
        )

        ttk.Spinbox(
            toolbar,
            from_=MIN_COLORS,
            to=MAX_COLORS,
            width=5,
            textvariable=self.color_count_var,
            command=self.change_color_count,
            state="readonly",
        ).pack(side="left")

        ttk.Button(
            toolbar,
            text="Suggest Palette",
            command=self.apply_suggested_palette,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Analyze Artwork",
            command=self.analyze_artwork,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Region Explorer",
            command=self.open_region_explorer,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Object Explorer",
            command=self.open_object_explorer,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Outline Explorer",
            command=self.open_outline_explorer,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Line Art Analyzer",
            command=self.open_line_analyzer,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Object Builder",
            command=self.open_object_builder,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Manufacturing Map",
            command=self.open_manufacturing_map,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="HueForge Targeting",
            command=self.open_hueforge_targeting,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Save Project",
            command=self.save_project,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Load Project",
            command=self.load_project,
        ).pack(side="left", padx=8)

        ttk.Button(
            toolbar,
            text="Export Project",
            command=self.export_current_project,
        ).pack(side="left", padx=8)

        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right")

        previews = ttk.Frame(main)
        previews.pack(fill="both", expand=True)

        self.original_label = self.make_preview_panel(
            previews,
            "Original Artwork",
            0,
        )
        self.output_label = self.make_preview_panel(
            previews,
            "Cleaned HueForge Preview",
            1,
        )
        self.mask_label = self.make_preview_panel(
            previews,
            "Selected Layer Mask",
            2,
        )

        analysis_frame = ttk.LabelFrame(
            main,
            text="Artwork Analysis",
            padding=8,
        )
        analysis_frame.pack(fill="x", pady=(10, 0))

        self.analysis_text = tk.Text(
            analysis_frame,
            height=7,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
        )
        self.analysis_text.pack(fill="x")

        cleanup_frame = ttk.LabelFrame(
            main,
            text="Artwork Cleanup",
            padding=10,
        )
        cleanup_frame.pack(fill="x", pady=(10, 0))

        cleanup_controls = ttk.Frame(cleanup_frame)
        cleanup_controls.pack(fill="x")

        ttk.Checkbutton(
            cleanup_controls,
            text="Remove tiny islands",
            variable=self.remove_islands_var,
        ).pack(side="left")

        ttk.Label(
            cleanup_controls,
            text="Maximum island size:",
        ).pack(side="left", padx=(8, 3))

        ttk.Spinbox(
            cleanup_controls,
            from_=1,
            to=250,
            width=6,
            textvariable=self.island_threshold_var,
        ).pack(side="left", padx=(0, 16))

        ttk.Checkbutton(
            cleanup_controls,
            text="Fill small holes",
            variable=self.fill_holes_var,
        ).pack(side="left")

        ttk.Label(
            cleanup_controls,
            text="Maximum hole size:",
        ).pack(side="left", padx=(8, 3))

        ttk.Spinbox(
            cleanup_controls,
            from_=1,
            to=250,
            width=6,
            textvariable=self.hole_threshold_var,
        ).pack(side="left", padx=(0, 16))

        ttk.Button(
            cleanup_controls,
            text="Generate Clean Preview",
            command=self.apply_cleanup,
        ).pack(side="left", padx=5)

        ttk.Button(
            cleanup_controls,
            text="Restore Uncleaned Preview",
            command=self.restore_uncleaned_preview,
        ).pack(side="left", padx=5)

        ttk.Label(
            cleanup_frame,
            textvariable=self.cleanup_summary_var,
            anchor="center",
        ).pack(fill="x", pady=(8, 0))

        palette_frame = ttk.LabelFrame(
            main,
            text="Final Manufacturing Palette",
            padding=10,
        )
        palette_frame.pack(fill="x", pady=(10, 0))

        header = ttk.Frame(palette_frame)
        header.pack(fill="x")

        for column, heading in enumerate(
            ["Layer", "Name", "Color", "Hex", "Filament", "Mask"]
        ):
            header.columnconfigure(column, weight=1)
            ttk.Label(
                header,
                text=heading,
                anchor="center",
                font=("Segoe UI", 9, "bold"),
            ).grid(
                row=0,
                column=column,
                sticky="ew",
                padx=3,
            )

        self.rows_frame = ttk.Frame(palette_frame)
        self.rows_frame.pack(fill="x", pady=(4, 0))

        ttk.Label(
            palette_frame,
            textvariable=self.layer_stats_var,
            anchor="center",
        ).pack(fill="x", pady=(8, 0))

    def make_preview_panel(
        self,
        parent: ttk.Frame,
        title: str,
        column: int,
    ) -> ttk.Label:
        parent.columnconfigure(column, weight=1)

        panel = ttk.LabelFrame(parent, text=title, padding=8)
        panel.grid(row=0, column=column, sticky="nsew", padx=4)

        label = ttk.Label(
            panel,
            text="No image loaded",
            anchor="center",
        )
        label.pack(fill="both", expand=True)

        return label

    def set_analysis_text(self, value: str) -> None:
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("1.0", value)
        self.analysis_text.configure(state="disabled")

    def create_default_layers(self, count: int) -> None:
        self.hueforge_target_luminances = []

        self.layers = [
            PaletteLayer(
                name=DEFAULT_LAYER_NAMES[index],
                color=DEFAULT_LAYER_COLORS[index],
            )
            for index in range(count)
        ]

        self.rebuild_rows()
        self.schedule_preview()

    def open_image(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select artwork",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )

        if not selected:
            return

        try:
            self.image_path = Path(selected)
            self.artwork_objects = []
            self.repaired_line_mask = None
            self.line_repair_settings = {}
            self.manufacturing_map = None
            self.hueforge_target_luminances = []

            with Image.open(self.image_path) as opened:
                self.original_image = opened.convert("RGB").copy()

            self.display_original()
            self.apply_suggested_palette()

            self.status_var.set(
                f"{self.image_path.name} — "
                f"{self.original_image.width} × "
                f"{self.original_image.height}"
            )

        except Exception as error:
            messagebox.showerror("Unable to open image", str(error))

    def display_original(self) -> None:
        if self.original_image is None:
            return

        preview = self.original_image.copy()
        preview.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)

        self.original_photo = ImageTk.PhotoImage(preview)
        self.original_label.configure(
            image=self.original_photo,
            text="",
        )

    def change_color_count(self) -> None:
        count = int(self.color_count_var.get())

        if self.original_image is None:
            self.create_default_layers(count)
        else:
            self.apply_suggested_palette()

    def apply_suggested_palette(self) -> None:
        if self.original_image is None:
            messagebox.showinfo("No image", "Open an image first.")
            return

        count = int(self.color_count_var.get())

        try:
            colors = suggest_palette(self.original_image, count)
            old_layers = self.layers
            new_layers: list[PaletteLayer] = []

            for index in range(count):
                color = (
                    colors[index]
                    if index < len(colors)
                    else DEFAULT_LAYER_COLORS[index]
                )
                name = (
                    old_layers[index].name
                    if index < len(old_layers)
                    else DEFAULT_LAYER_NAMES[index]
                )
                filament = (
                    old_layers[index].filament
                    if index < len(old_layers)
                    else ""
                )

                new_layers.append(
                    PaletteLayer(
                        name=name,
                        color=color,
                        filament=filament,
                    )
                )

            self.layers = new_layers
            self.rebuild_rows()
            self.schedule_preview()

        except Exception as error:
            messagebox.showerror(
                "Palette suggestion failed",
                str(error),
            )

    def rebuild_rows(self) -> None:
        for widget in self.rows_frame.winfo_children():
            widget.destroy()

        self.layer_rows.clear()

        for index, layer in enumerate(self.layers):
            row = ttk.Frame(self.rows_frame)
            row.pack(fill="x", pady=3)

            for column in range(6):
                row.columnconfigure(column, weight=1)

            ttk.Label(
                row,
                text=str(index + 1),
                anchor="center",
            ).grid(row=0, column=0, sticky="ew", padx=3)

            name_var = tk.StringVar(value=layer.name)
            name_entry = ttk.Entry(
                row,
                textvariable=name_var,
                justify="center",
            )
            name_entry.grid(row=0, column=1, sticky="ew", padx=3)

            color_button = tk.Button(
                row,
                text=rgb_to_hex(layer.color),
                background=rgb_to_hex(layer.color),
                foreground=readable_text_color(layer.color),
                activebackground=rgb_to_hex(layer.color),
                activeforeground=readable_text_color(layer.color),
                height=2,
                command=lambda layer_index=index: self.choose_color(
                    layer_index
                ),
            )
            color_button.grid(
                row=0,
                column=2,
                sticky="ew",
                padx=3,
            )

            hex_var = tk.StringVar(value=rgb_to_hex(layer.color))
            hex_entry = ttk.Entry(
                row,
                textvariable=hex_var,
                justify="center",
            )
            hex_entry.grid(row=0, column=3, sticky="ew", padx=3)

            filament_var = tk.StringVar(value=layer.filament)
            filament_entry = ttk.Entry(
                row,
                textvariable=filament_var,
                justify="center",
            )
            filament_entry.grid(
                row=0,
                column=4,
                sticky="ew",
                padx=3,
            )

            ttk.Button(
                row,
                text="Preview",
                command=lambda layer_index=index: self.preview_mask(
                    layer_index
                ),
            ).grid(row=0, column=5, sticky="ew", padx=3)

            name_entry.bind(
                "<FocusOut>",
                lambda event, layer_index=index: self.sync_row(
                    layer_index
                ),
            )
            name_entry.bind(
                "<Return>",
                lambda event, layer_index=index: self.sync_row(
                    layer_index
                ),
            )
            hex_entry.bind(
                "<FocusOut>",
                lambda event, layer_index=index: self.apply_hex(
                    layer_index,
                    False,
                ),
            )
            hex_entry.bind(
                "<Return>",
                lambda event, layer_index=index: self.apply_hex(
                    layer_index,
                    True,
                ),
            )
            filament_entry.bind(
                "<FocusOut>",
                lambda event, layer_index=index: self.sync_row(
                    layer_index
                ),
            )
            filament_entry.bind(
                "<Return>",
                lambda event, layer_index=index: self.sync_row(
                    layer_index
                ),
            )

            self.layer_rows.append(
                {
                    "name_var": name_var,
                    "hex_var": hex_var,
                    "filament_var": filament_var,
                    "color_button": color_button,
                }
            )

    def sync_row(self, index: int) -> None:
        controls = self.layer_rows[index]

        name_var = controls["name_var"]
        filament_var = controls["filament_var"]

        if isinstance(name_var, tk.StringVar):
            self.layers[index].name = (
                name_var.get().strip()
                or f"Layer {index + 1}"
            )

        if isinstance(filament_var, tk.StringVar):
            self.layers[index].filament = filament_var.get().strip()

    def apply_hex(
        self,
        index: int,
        show_error: bool,
    ) -> None:
        controls = self.layer_rows[index]
        hex_var = controls["hex_var"]

        if not isinstance(hex_var, tk.StringVar):
            return

        try:
            self.layers[index].color = hex_to_rgb(hex_var.get())
            self.refresh_row(index)
            self.schedule_preview()

        except ValueError as error:
            hex_var.set(rgb_to_hex(self.layers[index].color))

            if show_error:
                messagebox.showerror("Invalid color", str(error))

    def choose_color(self, index: int) -> None:
        selected_rgb, selected_hex = colorchooser.askcolor(
            color=rgb_to_hex(self.layers[index].color),
            title=f"Choose {self.layers[index].name}",
        )

        if selected_rgb is None or selected_hex is None:
            return

        self.layers[index].color = tuple(
            max(0, min(255, round(value)))
            for value in selected_rgb
        )

        self.refresh_row(index)
        self.schedule_preview()

    def refresh_row(self, index: int) -> None:
        controls = self.layer_rows[index]
        color = self.layers[index].color

        hex_var = controls["hex_var"]
        color_button = controls["color_button"]

        if isinstance(hex_var, tk.StringVar):
            hex_var.set(rgb_to_hex(color))

        if isinstance(color_button, tk.Button):
            color_button.configure(
                text=rgb_to_hex(color),
                background=rgb_to_hex(color),
                foreground=readable_text_color(color),
                activebackground=rgb_to_hex(color),
                activeforeground=readable_text_color(color),
            )

    def schedule_preview(self) -> None:
        if self.original_image is None:
            return

        if self.preview_job is not None:
            self.root.after_cancel(self.preview_job)

        self.preview_job = self.root.after(
            150,
            self.generate_preview,
        )

    def generate_preview(self) -> None:
        self.preview_job = None

        if self.original_image is None:
            return

        try:
            palette = [layer.color for layer in self.layers]

            self.reduced_image, self.assignment_map = reduce_to_palette(
                self.original_image,
                palette,
            )

            self.original_assignment_map = self.assignment_map.copy()
            self.analysis = []
            self.manufacturing_map = None
            self.cleanup_summary_var.set(
                "Cleanup has not been applied."
            )

            self.refresh_reduced_preview()

            self.status_var.set(
                f"{len(self.layers)}-color preview generated."
            )

        except Exception as error:
            messagebox.showerror("Preview failed", str(error))

    def refresh_reduced_preview(self) -> None:
        if self.reduced_image is None:
            return

        preview = self.reduced_image.copy()
        preview.thumbnail(PREVIEW_SIZE, Image.Resampling.NEAREST)

        self.output_photo = ImageTk.PhotoImage(preview)
        self.output_label.configure(
            image=self.output_photo,
            text="",
        )

        self.preview_mask(self.selected_mask_index)

    def preview_mask(self, index: int) -> None:
        if self.assignment_map is None or not self.layers:
            return

        if index >= len(self.layers):
            index = 0

        self.selected_mask_index = index

        mask = create_mask(self.assignment_map, index)
        mask.thumbnail(PREVIEW_SIZE, Image.Resampling.NEAREST)

        self.mask_photo = ImageTk.PhotoImage(mask)
        self.mask_label.configure(
            image=self.mask_photo,
            text="",
        )

        pixel_count = int(
            (self.assignment_map == index).sum()
        )
        percentage = (
            pixel_count / self.assignment_map.size * 100
        )

        self.layer_stats_var.set(
            f"{self.layers[index].name}: "
            f"{pixel_count:,} pixels "
            f"({percentage:.2f}% coverage)."
        )

    def analyze_artwork(self) -> None:
        if self.assignment_map is None:
            messagebox.showwarning(
                "Nothing to analyze",
                "Open an image and generate a preview first.",
            )
            return

        try:
            threshold = int(self.island_threshold_var.get())

            self.analysis = analyze_assignment(
                self.assignment_map,
                self.layers,
                threshold,
            )

            total_regions = sum(
                item.connected_regions for item in self.analysis
            )
            total_tiny = sum(
                item.tiny_regions for item in self.analysis
            )

            lines = [
                f"Image: {self.assignment_map.shape[1]} × "
                f"{self.assignment_map.shape[0]} px",
                f"Final palette: {len(self.layers)} colors",
                f"Connected regions: {total_regions:,}",
                f"Tiny regions (≤ {threshold} px): {total_tiny:,}",
                "",
            ]

            for item in self.analysis:
                lines.append(
                    f"{item.layer_number:02d}. "
                    f"{item.name:<18} "
                    f"{item.coverage_percentage:6.2f}%  "
                    f"regions {item.connected_regions:5,d}  "
                    f"tiny {item.tiny_regions:5,d}"
                )

            self.set_analysis_text("\n".join(lines))
            self.status_var.set("Artwork analysis complete.")

        except Exception as error:
            messagebox.showerror("Analysis failed", str(error))

    def open_region_explorer(self) -> None:
        """Open the interactive connected-region editor."""
        if (
            self.assignment_map is None
            or self.reduced_image is None
        ):
            messagebox.showwarning(
                "Nothing to explore",
                "Open an image and generate a preview first.",
            )
            return

        RegionExplorer(self)

    def open_object_explorer(self) -> None:
        """Open the manual semantic object editor."""
        if (
            self.assignment_map is None
            or self.reduced_image is None
        ):
            messagebox.showwarning(
                "Nothing to explore",
                "Open an image and generate a preview first.",
            )
            return

        ObjectExplorer(self)

    def open_outline_explorer(self) -> None:
        """Open enclosed-shape segmentation using an outline layer."""
        if (
            self.assignment_map is None
            or self.reduced_image is None
        ):
            messagebox.showwarning(
                "Nothing to explore",
                "Open an image and generate a preview first.",
            )
            return

        OutlineExplorer(self)

    def open_line_analyzer(self) -> None:
        """Open original-image line detection and repair preview."""
        if self.original_image is None:
            messagebox.showwarning(
                "Nothing to analyze",
                "Open an image first.",
            )
            return

        LineArtAnalyzer(self)

    def open_object_builder(self) -> None:
        """Open the click-based semantic object builder."""
        if (
            self.assignment_map is None
            or self.reduced_image is None
        ):
            messagebox.showwarning(
                "Nothing to build",
                "Open an image and generate a preview first.",
            )
            return

        ObjectBuilder(self)

    def open_hueforge_targeting(self) -> None:
        """Open filament assignment and grayscale target authoring."""
        if (
            self.original_image is None
            or self.assignment_map is None
        ):
            messagebox.showwarning(
                "Nothing to target",
                "Open an image and generate a preview first.",
            )
            return

        HueForgeTargeting(self)

    def open_manufacturing_map(self) -> None:
        if self.original_image is None or self.assignment_map is None:
            messagebox.showwarning("Nothing to map","Open an image and generate a preview first.")
            return
        ManufacturingMapViewer(self)

    def apply_cleanup(self) -> None:
        if self.original_assignment_map is None:
            messagebox.showwarning(
                "Nothing to clean",
                "Open an image and generate a preview first.",
            )
            return

        try:
            cleaned = self.original_assignment_map.copy()
            removed_islands = 0
            filled_holes = 0

            if self.remove_islands_var.get():
                cleaned, removed_islands = remove_tiny_islands(
                    cleaned,
                    len(self.layers),
                    int(self.island_threshold_var.get()),
                )

            if self.fill_holes_var.get():
                cleaned, filled_holes = fill_small_holes(
                    cleaned,
                    len(self.layers),
                    int(self.hole_threshold_var.get()),
                )

            self.assignment_map = cleaned
            self.reduced_image = image_from_assignment(
                cleaned,
                [layer.color for layer in self.layers],
            )

            self.analysis = []
            self.cleanup_summary_var.set(
                f"Cleanup complete: removed "
                f"{removed_islands:,} tiny islands and filled "
                f"{filled_holes:,} small holes."
            )

            self.refresh_reduced_preview()
            self.analyze_artwork()
            self.status_var.set("Clean preview generated.")

        except Exception as error:
            messagebox.showerror("Cleanup failed", str(error))

    def restore_uncleaned_preview(self) -> None:
        if self.original_assignment_map is None:
            return

        self.assignment_map = self.original_assignment_map.copy()
        self.reduced_image = image_from_assignment(
            self.assignment_map,
            [layer.color for layer in self.layers],
        )

        self.analysis = []
        self.cleanup_summary_var.set(
            "Restored the uncleaned palette preview."
        )

        self.refresh_reduced_preview()
        self.status_var.set("Uncleaned preview restored.")

    def sync_all_rows(self) -> None:
        for index in range(len(self.layers)):
            self.sync_row(index)
            self.apply_hex(index, False)

    def cleanup_settings(self) -> dict[str, object]:
        return {
            "remove_tiny_islands": self.remove_islands_var.get(),
            "island_threshold": int(
                self.island_threshold_var.get()
            ),
            "fill_small_holes": self.fill_holes_var.get(),
            "hole_threshold": int(
                self.hole_threshold_var.get()
            ),
        }

    def save_project(self) -> None:
        if self.image_path is None:
            messagebox.showwarning(
                "No project",
                "Open an image before saving a project.",
            )
            return

        self.sync_all_rows()

        selected = filedialog.asksaveasfilename(
            title="Save ForgePrep project",
            initialfile=f"{self.image_path.stem}_ForgePrep.json",
            defaultextension=".json",
            filetypes=[("ForgePrep project", "*.json")],
        )

        if not selected:
            return

        try:
            save_project_file(
                path=Path(selected),
                source_image=self.image_path,
                layers=self.layers,
                cleanup_settings=self.cleanup_settings(),
                version=APP_VERSION,
                artwork_objects=self.artwork_objects,
            )

            self.status_var.set(
                f"Project saved: {Path(selected).name}"
            )

        except Exception as error:
            messagebox.showerror(
                "Unable to save project",
                str(error),
            )

    def load_project(self) -> None:
        selected = filedialog.askopenfilename(
            title="Load ForgePrep project",
            filetypes=[("ForgePrep project", "*.json")],
        )

        if not selected:
            return

        try:
            source_path, layers, cleanup, artwork_objects = load_project_file(
                Path(selected)
            )

            if not source_path.exists():
                raise FileNotFoundError(
                    f"The source image no longer exists:\n"
                    f"{source_path}"
                )

            with Image.open(source_path) as opened:
                self.original_image = opened.convert("RGB").copy()

            self.image_path = source_path
            self.layers = layers
            self.artwork_objects = artwork_objects

            self.remove_islands_var.set(
                cleanup.get("remove_tiny_islands", True)
            )
            self.island_threshold_var.set(
                cleanup.get(
                    "island_threshold",
                    DEFAULT_TINY_THRESHOLD,
                )
            )
            self.fill_holes_var.set(
                cleanup.get("fill_small_holes", True)
            )
            self.hole_threshold_var.set(
                cleanup.get(
                    "hole_threshold",
                    DEFAULT_HOLE_THRESHOLD,
                )
            )

            self.color_count_var.set(len(self.layers))
            self.display_original()
            self.rebuild_rows()
            self.schedule_preview()

            self.status_var.set(
                f"Project loaded: {Path(selected).name}"
            )

        except Exception as error:
            messagebox.showerror(
                "Unable to load project",
                str(error),
            )

    def export_current_project(self) -> None:
        if (
            self.image_path is None
            or self.original_image is None
            or self.reduced_image is None
            or self.assignment_map is None
        ):
            messagebox.showwarning(
                "Nothing to export",
                "Open an image and generate a preview first.",
            )
            return

        self.sync_all_rows()

        destination = filedialog.askdirectory(
            title="Choose export location"
        )

        if not destination:
            return

        try:
            project_folder = export_project(
                destination=Path(destination),
                source_path=self.image_path,
                source_image=self.original_image,
                reduced_image=self.reduced_image,
                assignment_map=self.assignment_map,
                layers=self.layers,
                analysis=self.analysis,
                cleanup_settings=self.cleanup_settings(),
                cleanup_summary=self.cleanup_summary_var.get(),
                version=APP_VERSION,
                artwork_objects=self.artwork_objects,
            )

            messagebox.showinfo(
                "Export complete",
                f"Created:\n\n{project_folder}",
            )

            self.status_var.set(
                f"Exported: {project_folder.name}"
            )

        except Exception as error:
            messagebox.showerror("Export failed", str(error))


def run_app() -> None:
    root = tk.Tk()
    ForgePrepApp(root)
    root.mainloop()

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk

from core.palette import image_from_assignment
from core.regions import (
    Region,
    create_region_overlay,
    find_regions,
    merge_region,
)


class RegionExplorer:
    """Interactive connected-region viewer and editor."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — Region Explorer")
        self.window.geometry("980x720")
        self.window.minsize(820, 620)

        self.regions: list[Region] = []
        self.visible_regions: list[Region] = []
        self.overlay_photo: ImageTk.PhotoImage | None = None

        self.layer_var = tk.StringVar()
        self.tiny_only_var = tk.BooleanVar(value=True)
        self.threshold_var = tk.IntVar(value=25)
        self.target_var = tk.StringVar(value="Automatic neighbor")
        self.status_var = tk.StringVar(
            value="Choose a region to highlight it."
        )

        self.build_window()
        self.refresh_layer_choices()
        self.refresh_regions()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Region Explorer",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 10))

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Label(controls, text="Layer:").pack(
            side="left"
        )

        self.layer_box = ttk.Combobox(
            controls,
            textvariable=self.layer_var,
            state="readonly",
            width=24,
        )
        self.layer_box.pack(
            side="left",
            padx=(4, 14),
        )
        self.layer_box.bind(
            "<<ComboboxSelected>>",
            lambda event: self.refresh_regions(),
        )

        ttk.Checkbutton(
            controls,
            text="Show only regions at or below",
            variable=self.tiny_only_var,
            command=self.refresh_regions,
        ).pack(side="left")

        ttk.Spinbox(
            controls,
            from_=1,
            to=10000,
            width=7,
            textvariable=self.threshold_var,
            command=self.refresh_regions,
        ).pack(side="left", padx=(4, 4))

        ttk.Label(controls, text="pixels").pack(
            side="left"
        )

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            content,
            text="Regions",
            padding=8,
        )
        left.pack(
            side="left",
            fill="y",
            padx=(0, 6),
        )

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)

        self.region_list = tk.Listbox(
            list_frame,
            width=34,
            exportselection=False,
            font=("Consolas", 10),
        )
        self.region_list.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.region_list.bind(
            "<<ListboxSelect>>",
            self.show_selected_region,
        )

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.region_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.region_list.configure(
            yscrollcommand=scrollbar.set
        )

        right = ttk.LabelFrame(
            content,
            text="Selected Region",
            padding=8,
        )
        right.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(6, 0),
        )

        self.preview_label = ttk.Label(
            right,
            text="Select a region",
            anchor="center",
        )
        self.preview_label.pack(
            fill="both",
            expand=True,
        )

        action_frame = ttk.Frame(right)
        action_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(
            action_frame,
            text="Merge into:",
        ).pack(side="left")

        self.target_box = ttk.Combobox(
            action_frame,
            textvariable=self.target_var,
            state="readonly",
            width=24,
        )
        self.target_box.pack(
            side="left",
            padx=(5, 8),
        )

        ttk.Button(
            action_frame,
            text="Merge Selected Region",
            command=self.merge_selected,
        ).pack(side="left", padx=4)

        ttk.Button(
            action_frame,
            text="Merge All Shown",
            command=self.merge_all_shown,
        ).pack(side="left", padx=4)

        ttk.Label(
            main,
            textvariable=self.status_var,
            anchor="center",
        ).pack(fill="x", pady=(10, 0))

    def refresh_layer_choices(self) -> None:
        values = [
            f"{index + 1}: {layer.name}"
            for index, layer in enumerate(self.app.layers)
        ]

        self.layer_box["values"] = values

        target_values = [
            "Automatic neighbor",
            *values,
        ]
        self.target_box["values"] = target_values

        if values and not self.layer_var.get():
            self.layer_var.set(values[0])

        if self.target_var.get() not in target_values:
            self.target_var.set("Automatic neighbor")

    def selected_layer_index(self) -> int:
        value = self.layer_var.get()
        return max(0, int(value.split(":", 1)[0]) - 1)

    def refresh_regions(self) -> None:
        if self.app.assignment_map is None:
            return

        self.refresh_layer_choices()

        layer_index = self.selected_layer_index()
        self.regions = find_regions(
            self.app.assignment_map,
            layer_index,
        )

        threshold = max(
            1,
            int(self.threshold_var.get()),
        )

        if self.tiny_only_var.get():
            self.visible_regions = [
                region
                for region in self.regions
                if region.size <= threshold
            ]
        else:
            self.visible_regions = self.regions

        self.region_list.delete(0, "end")

        for region in self.visible_regions:
            self.region_list.insert(
                "end",
                f"Region {region.region_number:04d}  "
                f"{region.size:7,d} px",
            )

        self.preview_label.configure(
            image="",
            text="Select a region",
        )

        self.status_var.set(
            f"{len(self.visible_regions):,} shown of "
            f"{len(self.regions):,} regions in "
            f"{self.app.layers[layer_index].name}."
        )

    def selected_region(self) -> Region | None:
        selection = self.region_list.curselection()

        if not selection:
            return None

        index = int(selection[0])

        if index >= len(self.visible_regions):
            return None

        return self.visible_regions[index]

    def show_selected_region(
        self,
        _event: object | None = None,
    ) -> None:
        region = self.selected_region()

        if (
            region is None
            or self.app.reduced_image is None
        ):
            return

        overlay = create_region_overlay(
            self.app.reduced_image,
            region,
        )
        overlay.thumbnail(
            (560, 500),
        )

        self.overlay_photo = ImageTk.PhotoImage(
            overlay
        )

        self.preview_label.configure(
            image=self.overlay_photo,
            text="",
        )

        self.status_var.set(
            f"Layer: {self.app.layers[region.layer_index].name} • "
            f"Region {region.region_number} • "
            f"{region.size:,} pixels"
        )

    def selected_target_index(self) -> int | None:
        value = self.target_var.get()

        if value == "Automatic neighbor":
            return None

        return max(0, int(value.split(":", 1)[0]) - 1)

    def apply_updated_map(
        self,
        updated_map: object,
        summary: str,
    ) -> None:
        self.app.assignment_map = updated_map
        self.app.reduced_image = image_from_assignment(
            updated_map,
            [layer.color for layer in self.app.layers],
        )

        self.app.analysis = []
        self.app.cleanup_summary_var.set(summary)
        self.app.refresh_reduced_preview()
        self.app.analyze_artwork()
        self.refresh_regions()

    def merge_selected(self) -> None:
        region = self.selected_region()

        if region is None:
            messagebox.showinfo(
                "No region selected",
                "Select a region from the list first.",
                parent=self.window,
            )
            return

        updated, target = merge_region(
            self.app.assignment_map,
            region,
            self.selected_target_index(),
        )

        if target is None:
            messagebox.showwarning(
                "Unable to merge",
                "ForgePrep could not find a neighboring layer.",
                parent=self.window,
            )
            return

        self.apply_updated_map(
            updated,
            (
                f"Region Explorer merged a "
                f"{region.size:,}-pixel region from "
                f"{self.app.layers[region.layer_index].name} into "
                f"{self.app.layers[target].name}."
            ),
        )

    def merge_all_shown(self) -> None:
        if not self.visible_regions:
            messagebox.showinfo(
                "No regions shown",
                "There are no displayed regions to merge.",
                parent=self.window,
            )
            return

        confirmed = messagebox.askyesno(
            "Merge all shown regions?",
            (
                f"This will merge {len(self.visible_regions):,} regions "
                "using the selected target behavior.\n\n"
                "You can use Restore Uncleaned Preview in the main window "
                "to undo all region edits."
            ),
            parent=self.window,
        )

        if not confirmed:
            return

        updated = self.app.assignment_map.copy()
        merged_count = 0
        target_choice = self.selected_target_index()

        # Work from smallest to largest and recalculate automatic neighbors
        # against the progressively updated map.
        for region in sorted(
            self.visible_regions,
            key=lambda item: item.size,
        ):
            updated, target = merge_region(
                updated,
                region,
                target_choice,
            )

            if target is not None:
                merged_count += 1

        self.apply_updated_map(
            updated,
            (
                f"Region Explorer merged "
                f"{merged_count:,} displayed regions."
            ),
        )

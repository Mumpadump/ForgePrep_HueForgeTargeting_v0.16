from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk

from core.outline_cells import (
    OutlineCell,
    create_cell_overlay,
    find_outline_cells,
    reassign_cell,
)
from core.palette import image_from_assignment
from core.line_art import find_non_line_cells


class OutlineExplorer:
    """
    Segment artwork using one palette layer as the wall/outline layer.

    This is designed for comic-style artwork where black outlines separate
    visual objects even when those objects share similar fill colors.
    """

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — Outline Cell Explorer")
        self.window.geometry("1080x760")
        self.window.minsize(900, 640)

        self.cells: list[OutlineCell] = []
        self.visible_cells: list[OutlineCell] = []
        self.overlay_photo: ImageTk.PhotoImage | None = None

        self.outline_layer_var = tk.StringVar()
        self.target_layer_var = tk.StringVar()
        self.hide_edge_cells_var = tk.BooleanVar(value=True)
        self.use_repaired_mask_var = tk.BooleanVar(value=False)
        self.minimum_size_var = tk.IntVar(value=10)
        self.maximum_size_var = tk.IntVar(value=1000000)
        self.status_var = tk.StringVar(
            value="Choose an enclosed cell to inspect it."
        )

        self.build_window()
        self.refresh_layer_choices()
        self.rebuild_cells()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Outline Cell Explorer",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 8))

        ttk.Label(
            main,
            text=(
                "The selected outline layer acts as a wall. "
                "ForgePrep finds the enclosed areas between those walls."
            ),
        ).pack(fill="x", pady=(0, 10))

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Label(
            controls,
            text="Outline layer:",
        ).pack(side="left")

        self.outline_box = ttk.Combobox(
            controls,
            textvariable=self.outline_layer_var,
            state="readonly",
            width=25,
        )
        self.outline_box.pack(
            side="left",
            padx=(5, 12),
        )
        self.outline_box.bind(
            "<<ComboboxSelected>>",
            lambda event: self.rebuild_cells(),
        )

        ttk.Checkbutton(
            controls,
            text="Hide cells touching image edge",
            variable=self.hide_edge_cells_var,
            command=self.apply_filters,
        ).pack(side="left", padx=(0, 12))

        ttk.Checkbutton(
            controls,
            text="Use repaired line mask",
            variable=self.use_repaired_mask_var,
            command=self.rebuild_cells,
        ).pack(side="left", padx=(0, 12))

        ttk.Label(controls, text="Size:").pack(side="left")

        ttk.Spinbox(
            controls,
            from_=1,
            to=10000000,
            width=8,
            textvariable=self.minimum_size_var,
            command=self.apply_filters,
        ).pack(side="left", padx=(4, 3))

        ttk.Label(controls, text="to").pack(side="left")

        ttk.Spinbox(
            controls,
            from_=1,
            to=10000000,
            width=9,
            textvariable=self.maximum_size_var,
            command=self.apply_filters,
        ).pack(side="left", padx=(3, 4))

        ttk.Label(controls, text="pixels").pack(side="left")

        ttk.Button(
            controls,
            text="Rebuild Cells",
            command=self.rebuild_cells,
        ).pack(side="left", padx=(12, 0))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            content,
            text="Enclosed Cells",
            padding=8,
        )
        left.pack(
            side="left",
            fill="y",
            padx=(0, 6),
        )

        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True)

        self.cell_list = tk.Listbox(
            list_frame,
            width=42,
            exportselection=False,
            font=("Consolas", 10),
        )
        self.cell_list.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.cell_list.bind(
            "<<ListboxSelect>>",
            self.preview_selected_cell,
        )

        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.cell_list.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.cell_list.configure(
            yscrollcommand=scrollbar.set
        )

        right = ttk.LabelFrame(
            content,
            text="Selected Enclosed Cell",
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
            text="Select a cell",
            anchor="center",
        )
        self.preview_label.pack(
            fill="both",
            expand=True,
        )

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(10, 0))

        ttk.Label(
            actions,
            text="Assign cell to layer:",
        ).pack(side="left")

        self.target_box = ttk.Combobox(
            actions,
            textvariable=self.target_layer_var,
            state="readonly",
            width=25,
        )
        self.target_box.pack(
            side="left",
            padx=(5, 8),
        )

        ttk.Button(
            actions,
            text="Assign Selected Cell",
            command=self.assign_selected_cell,
        ).pack(side="left", padx=4)

        ttk.Button(
            actions,
            text="Create Object from Cell",
            command=self.create_object_from_cell,
        ).pack(side="left", padx=4)

        ttk.Label(
            main,
            textvariable=self.status_var,
            anchor="center",
        ).pack(fill="x", pady=(10, 0))

    def layer_values(self) -> list[str]:
        return [
            f"{index + 1}: {layer.name}"
            for index, layer in enumerate(self.app.layers)
        ]

    def refresh_layer_choices(self) -> None:
        values = self.layer_values()
        self.outline_box["values"] = values
        self.target_box["values"] = values

        if values and self.outline_layer_var.get() not in values:
            self.outline_layer_var.set(values[0])

        if values and self.target_layer_var.get() not in values:
            self.target_layer_var.set(values[0])

    def selected_outline_layer_index(self) -> int:
        return max(
            0,
            int(
                self.outline_layer_var.get().split(":", 1)[0]
            ) - 1,
        )

    def selected_target_layer_index(self) -> int:
        return max(
            0,
            int(
                self.target_layer_var.get().split(":", 1)[0]
            ) - 1,
        )

    def rebuild_cells(self) -> None:
        if self.app.assignment_map is None:
            return

        self.refresh_layer_choices()

        if (
            self.use_repaired_mask_var.get()
            and getattr(self.app, "repaired_line_mask", None) is not None
        ):
            raw_cells = find_non_line_cells(
                self.app.repaired_line_mask
            )
            self.cells = []

            for index, (coordinates, touches_edge) in enumerate(
                raw_cells,
                start=1,
            ):
                layer_counts: dict[int, int] = {}

                for y, x in coordinates:
                    layer_index = int(
                        self.app.assignment_map[y, x]
                    )
                    layer_counts[layer_index] = (
                        layer_counts.get(layer_index, 0) + 1
                    )

                dominant = max(
                    layer_counts,
                    key=layer_counts.get,
                )

                self.cells.append(
                    OutlineCell(
                        cell_number=index,
                        coordinates=coordinates,
                        dominant_layer_index=dominant,
                        touches_edge=touches_edge,
                    )
                )
        else:
            self.cells = find_outline_cells(
                self.app.assignment_map,
                self.selected_outline_layer_index(),
            )

        self.apply_filters()

    def apply_filters(self) -> None:
        if not self.cells:
            self.visible_cells = []
        else:
            minimum = max(
                1,
                int(self.minimum_size_var.get()),
            )
            maximum = max(
                minimum,
                int(self.maximum_size_var.get()),
            )

            self.visible_cells = [
                cell
                for cell in self.cells
                if minimum <= cell.size <= maximum
                and not (
                    self.hide_edge_cells_var.get()
                    and cell.touches_edge
                )
            ]

        self.cell_list.delete(0, "end")

        for cell in self.visible_cells:
            layer_name = (
                self.app.layers[
                    cell.dominant_layer_index
                ].name
            )

            edge_marker = "EDGE" if cell.touches_edge else "    "

            self.cell_list.insert(
                "end",
                f"Cell {cell.cell_number:04d}  "
                f"{cell.size:8,d} px  "
                f"{edge_marker}  "
                f"[{layer_name}]",
            )

        self.preview_label.configure(
            image="",
            text="Select a cell",
        )

        self.status_var.set(
            f"{len(self.visible_cells):,} shown of "
            f"{len(self.cells):,} cells."
        )

    def selected_cell(self) -> OutlineCell | None:
        selection = self.cell_list.curselection()

        if not selection:
            return None

        index = int(selection[0])

        if index >= len(self.visible_cells):
            return None

        return self.visible_cells[index]

    def preview_selected_cell(
        self,
        _event: object | None = None,
    ) -> None:
        cell = self.selected_cell()

        if cell is None or self.app.reduced_image is None:
            return

        overlay = create_cell_overlay(
            self.app.reduced_image,
            cell,
        )
        overlay.thumbnail((620, 520))

        self.overlay_photo = ImageTk.PhotoImage(overlay)

        self.preview_label.configure(
            image=self.overlay_photo,
            text="",
        )

        dominant_name = self.app.layers[
            cell.dominant_layer_index
        ].name

        self.status_var.set(
            f"Cell {cell.cell_number} • "
            f"{cell.size:,} pixels • "
            f"current dominant layer: {dominant_name}"
        )

    def assign_selected_cell(self) -> None:
        cell = self.selected_cell()

        if cell is None:
            messagebox.showinfo(
                "No cell selected",
                "Select an enclosed cell first.",
                parent=self.window,
            )
            return

        target = self.selected_target_layer_index()

        self.app.assignment_map = reassign_cell(
            self.app.assignment_map,
            cell,
            target,
        )

        self.app.reduced_image = image_from_assignment(
            self.app.assignment_map,
            [layer.color for layer in self.app.layers],
        )

        self.app.analysis = []
        self.app.cleanup_summary_var.set(
            f"Outline Explorer assigned cell "
            f"{cell.cell_number} to "
            f"{self.app.layers[target].name}."
        )

        self.app.refresh_reduced_preview()
        self.app.analyze_artwork()

        self.rebuild_cells()

        self.status_var.set(
            f"Assigned cell to "
            f"{self.app.layers[target].name}."
        )

    def create_object_from_cell(self) -> None:
        cell = self.selected_cell()

        if cell is None:
            messagebox.showinfo(
                "No cell selected",
                "Select an enclosed cell first.",
                parent=self.window,
            )
            return

        from core.objects import ArtworkObject
        from tkinter import simpledialog

        name = simpledialog.askstring(
            "Object name",
            "Name this enclosed object:",
            parent=self.window,
        )

        if not name:
            return

        self.app.artwork_objects.append(
            ArtworkObject(
                name=name,
                layer_index=cell.dominant_layer_index,
                coordinates=list(cell.coordinates),
            )
        )

        self.status_var.set(
            f"Created object '{name}' from "
            f"cell {cell.cell_number}."
        )

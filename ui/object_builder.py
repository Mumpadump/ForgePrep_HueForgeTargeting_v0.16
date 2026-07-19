from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import numpy as np
from PIL import Image, ImageTk

from core.line_art import find_non_line_cells
from core.objects import ArtworkObject, reassign_object
from core.outline_cells import find_outline_cells
from core.palette import image_from_assignment


class ObjectBuilder:
    """
    Build named manufacturing objects by clicking enclosed cells directly.

    The builder uses the repaired line mask when available. Otherwise, it uses
    a selected palette layer as the outline wall.
    """

    CANVAS_SIZE = 620

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — Object Builder")
        self.window.geometry("1280x850")
        self.window.minsize(1080, 720)

        self.cells: list[list[tuple[int, int]]] = []
        self.cell_lookup: np.ndarray | None = None
        self.current_object_index: int | None = None
        self.selected_cells: set[int] = set()

        self.display_photo: ImageTk.PhotoImage | None = None
        self.display_scale = 1.0
        self.display_offset_x = 0
        self.display_offset_y = 0

        self.source_var = tk.StringVar()
        self.target_layer_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Create or select an object, then click cells to add or remove them."
        )

        self.build_window()
        self.refresh_choices()
        self.rebuild_cells()
        self.refresh_objects()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Object Builder",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 6))

        ttk.Label(
            main,
            text=(
                "Click enclosed cells directly to teach ForgePrep what belongs "
                "to Face, Hat, Antlers, Clothing, Background, or any other object."
            ),
        ).pack(fill="x", pady=(0, 10))

        top_controls = ttk.Frame(main)
        top_controls.pack(fill="x", pady=(0, 10))

        ttk.Label(
            top_controls,
            text="Cell source:",
        ).pack(side="left")

        self.source_box = ttk.Combobox(
            top_controls,
            textvariable=self.source_var,
            state="readonly",
            width=32,
        )
        self.source_box.pack(side="left", padx=(5, 10))
        self.source_box.bind(
            "<<ComboboxSelected>>",
            lambda event: self.rebuild_cells(),
        )

        ttk.Button(
            top_controls,
            text="Rebuild Cells",
            command=self.rebuild_cells,
        ).pack(side="left", padx=5)

        ttk.Button(
            top_controls,
            text="New Object",
            command=self.new_object,
        ).pack(side="left", padx=5)

        ttk.Button(
            top_controls,
            text="Rename Object",
            command=self.rename_object,
        ).pack(side="left", padx=5)

        ttk.Button(
            top_controls,
            text="Delete Object",
            command=self.delete_object,
        ).pack(side="left", padx=5)

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        objects_panel = ttk.LabelFrame(
            content,
            text="Objects",
            padding=8,
        )
        objects_panel.pack(
            side="left",
            fill="y",
            padx=(0, 6),
        )

        self.object_list = tk.Listbox(
            objects_panel,
            width=33,
            exportselection=False,
            font=("Consolas", 10),
        )
        self.object_list.pack(fill="both", expand=True)
        self.object_list.bind(
            "<<ListboxSelect>>",
            self.select_object,
        )

        canvas_panel = ttk.LabelFrame(
            content,
            text="Click Cells to Add or Remove",
            padding=8,
        )
        canvas_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=6,
        )

        self.canvas = tk.Canvas(
            canvas_panel,
            width=self.CANVAS_SIZE,
            height=self.CANVAS_SIZE,
            background="#202020",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self.canvas_click)
        self.canvas.bind("<Configure>", lambda event: self.redraw())

        actions_panel = ttk.LabelFrame(
            content,
            text="Object Actions",
            padding=8,
        )
        actions_panel.pack(
            side="left",
            fill="y",
            padx=(6, 0),
        )

        ttk.Label(
            actions_panel,
            text=(
                "Selected object cells are yellow.\n"
                "Other saved objects are blue.\n"
                "Unassigned cells remain dim."
            ),
            justify="left",
        ).pack(fill="x", pady=(0, 12))

        self.object_info_label = ttk.Label(
            actions_panel,
            text="No object selected",
            justify="left",
        )
        self.object_info_label.pack(fill="x", pady=(0, 12))

        ttk.Button(
            actions_panel,
            text="Clear Object Cells",
            command=self.clear_current_object,
        ).pack(fill="x", pady=4)

        ttk.Button(
            actions_panel,
            text="Select All Unassigned Cells",
            command=self.select_all_unassigned,
        ).pack(fill="x", pady=4)

        ttk.Separator(
            actions_panel,
            orient="horizontal",
        ).pack(fill="x", pady=12)

        ttk.Label(
            actions_panel,
            text="Assign object to palette layer:",
        ).pack(fill="x")

        self.target_box = ttk.Combobox(
            actions_panel,
            textvariable=self.target_layer_var,
            state="readonly",
            width=26,
        )
        self.target_box.pack(fill="x", pady=(5, 8))

        ttk.Button(
            actions_panel,
            text="Reassign Entire Object",
            command=self.reassign_current_object,
        ).pack(fill="x", pady=4)

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

    def source_values(self) -> list[str]:
        values = []

        if getattr(self.app, "repaired_line_mask", None) is not None:
            values.append("Repaired line mask")

        values.extend(
            f"Outline layer {index + 1}: {layer.name}"
            for index, layer in enumerate(self.app.layers)
        )

        return values

    def refresh_choices(self) -> None:
        sources = self.source_values()
        layers = self.layer_values()

        self.source_box["values"] = sources
        self.target_box["values"] = layers

        if sources and self.source_var.get() not in sources:
            self.source_var.set(sources[0])

        if layers and self.target_layer_var.get() not in layers:
            self.target_layer_var.set(layers[0])

    def rebuild_cells(self) -> None:
        if self.app.assignment_map is None:
            return

        self.refresh_choices()
        source = self.source_var.get()

        if source == "Repaired line mask":
            raw_cells = find_non_line_cells(
                self.app.repaired_line_mask
            )
            self.cells = [
                coordinates
                for coordinates, _touches_edge in raw_cells
            ]
        else:
            layer_index = max(
                0,
                int(source.split(":", 1)[0].split()[-1]) - 1,
            )
            outline_cells = find_outline_cells(
                self.app.assignment_map,
                layer_index,
            )
            self.cells = [
                cell.coordinates
                for cell in outline_cells
            ]

        self.build_cell_lookup()
        self.load_current_object_cells()
        self.redraw()

        self.status_var.set(
            f"Built {len(self.cells):,} clickable cells."
        )

    def build_cell_lookup(self) -> None:
        if self.app.assignment_map is None:
            return

        lookup = np.full(
            self.app.assignment_map.shape,
            -1,
            dtype=np.int32,
        )

        for cell_index, coordinates in enumerate(self.cells):
            for y, x in coordinates:
                lookup[y, x] = cell_index

        self.cell_lookup = lookup

    def new_object(self) -> None:
        name = simpledialog.askstring(
            "New object",
            "Object name, such as Face, Hat, or Antlers:",
            parent=self.window,
        )

        if not name:
            return

        self.app.artwork_objects.append(
            ArtworkObject(
                name=name.strip(),
                layer_index=0,
                coordinates=[],
            )
        )

        self.refresh_objects()
        self.object_list.selection_clear(0, "end")
        self.object_list.selection_set(
            len(self.app.artwork_objects) - 1
        )
        self.select_object()

    def refresh_objects(self) -> None:
        self.object_list.delete(0, "end")

        for index, artwork_object in enumerate(
            self.app.artwork_objects
        ):
            layer_name = (
                self.app.layers[
                    artwork_object.layer_index
                ].name
                if 0 <= artwork_object.layer_index < len(self.app.layers)
                else "Unassigned"
            )

            self.object_list.insert(
                "end",
                f"{index + 1:02d}. "
                f"{artwork_object.name:<18} "
                f"{artwork_object.pixel_count:8,d} px "
                f"[{layer_name}]",
            )

    def select_object(
        self,
        _event: object | None = None,
    ) -> None:
        selection = self.object_list.curselection()

        if not selection:
            self.current_object_index = None
            self.selected_cells.clear()
            self.object_info_label.configure(
                text="No object selected"
            )
            self.redraw()
            return

        self.current_object_index = int(selection[0])
        self.load_current_object_cells()
        self.update_object_info()
        self.redraw()

    def current_object(self) -> ArtworkObject | None:
        if self.current_object_index is None:
            return None

        if not (
            0 <= self.current_object_index
            < len(self.app.artwork_objects)
        ):
            return None

        return self.app.artwork_objects[
            self.current_object_index
        ]

    def load_current_object_cells(self) -> None:
        self.selected_cells.clear()
        artwork_object = self.current_object()

        if artwork_object is None or self.cell_lookup is None:
            return

        counts: dict[int, int] = {}

        for y, x in artwork_object.coordinates:
            if (
                0 <= y < self.cell_lookup.shape[0]
                and 0 <= x < self.cell_lookup.shape[1]
            ):
                cell_index = int(
                    self.cell_lookup[y, x]
                )

                if cell_index >= 0:
                    counts[cell_index] = (
                        counts.get(cell_index, 0) + 1
                    )

        for cell_index, count in counts.items():
            if count >= max(
                1,
                len(self.cells[cell_index]) // 2,
            ):
                self.selected_cells.add(cell_index)

    def save_current_object_cells(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            return

        coordinates: set[tuple[int, int]] = set()

        for cell_index in self.selected_cells:
            if 0 <= cell_index < len(self.cells):
                coordinates.update(
                    self.cells[cell_index]
                )

        artwork_object.coordinates = sorted(coordinates)

        if artwork_object.coordinates:
            layer_counts: dict[int, int] = {}

            for y, x in artwork_object.coordinates:
                layer_index = int(
                    self.app.assignment_map[y, x]
                )
                layer_counts[layer_index] = (
                    layer_counts.get(layer_index, 0) + 1
                )

            artwork_object.layer_index = max(
                layer_counts,
                key=layer_counts.get,
            )

        self.refresh_objects()
        self.update_object_info()

    def update_object_info(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            self.object_info_label.configure(
                text="No object selected"
            )
            return

        self.object_info_label.configure(
            text=(
                f"Object: {artwork_object.name}\n"
                f"Cells: {len(self.selected_cells):,}\n"
                f"Pixels: {artwork_object.pixel_count:,}"
            )
        )

    def rename_object(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            return

        name = simpledialog.askstring(
            "Rename object",
            "New object name:",
            initialvalue=artwork_object.name,
            parent=self.window,
        )

        if not name:
            return

        artwork_object.name = name.strip()
        self.refresh_objects()

    def delete_object(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            return

        confirmed = messagebox.askyesno(
            "Delete object?",
            (
                f"Delete '{artwork_object.name}'?\n\n"
                "This removes the object definition only."
            ),
            parent=self.window,
        )

        if not confirmed:
            return

        del self.app.artwork_objects[
            self.current_object_index
        ]
        self.current_object_index = None
        self.selected_cells.clear()
        self.refresh_objects()
        self.update_object_info()
        self.redraw()

    def canvas_click(self, event: tk.Event) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            messagebox.showinfo(
                "Select an object",
                "Create or select an object before clicking cells.",
                parent=self.window,
            )
            return

        if self.cell_lookup is None:
            return

        image_x = int(
            (event.x - self.display_offset_x)
            / self.display_scale
        )
        image_y = int(
            (event.y - self.display_offset_y)
            / self.display_scale
        )

        if not (
            0 <= image_y < self.cell_lookup.shape[0]
            and 0 <= image_x < self.cell_lookup.shape[1]
        ):
            return

        cell_index = int(
            self.cell_lookup[image_y, image_x]
        )

        if cell_index < 0:
            self.status_var.set(
                "That pixel belongs to the outline, not an enclosed cell."
            )
            return

        if cell_index in self.selected_cells:
            self.selected_cells.remove(cell_index)
            action = "Removed"
        else:
            self.selected_cells.add(cell_index)
            action = "Added"

        self.save_current_object_cells()
        self.redraw()

        self.status_var.set(
            f"{action} cell {cell_index + 1:,} "
            f"({len(self.cells[cell_index]):,} pixels) "
            f"{'from' if action == 'Removed' else 'to'} "
            f"{artwork_object.name}."
        )

    def object_coordinate_sets(
        self,
    ) -> list[set[tuple[int, int]]]:
        return [
            set(artwork_object.coordinates)
            for artwork_object in self.app.artwork_objects
        ]

    def redraw(self) -> None:
        if self.app.reduced_image is None:
            return

        source = np.asarray(
            self.app.reduced_image.convert("RGB"),
            dtype=np.uint8,
        )
        display = (
            source.astype(np.float32) * 0.38
        ).astype(np.uint8)

        current = self.current_object()
        current_points = (
            set(current.coordinates)
            if current is not None
            else set()
        )

        other_points: set[tuple[int, int]] = set()

        for artwork_object in self.app.artwork_objects:
            if artwork_object is current:
                continue
            other_points.update(
                artwork_object.coordinates
            )

        for y, x in other_points:
            if (
                0 <= y < display.shape[0]
                and 0 <= x < display.shape[1]
            ):
                display[y, x] = (60, 150, 255)

        for y, x in current_points:
            if (
                0 <= y < display.shape[0]
                and 0 <= x < display.shape[1]
            ):
                display[y, x] = (255, 225, 0)

        image = Image.fromarray(display, mode="RGB")

        canvas_width = max(
            1,
            self.canvas.winfo_width(),
        )
        canvas_height = max(
            1,
            self.canvas.winfo_height(),
        )

        scale = min(
            canvas_width / image.width,
            canvas_height / image.height,
        )

        draw_width = max(
            1,
            int(image.width * scale),
        )
        draw_height = max(
            1,
            int(image.height * scale),
        )

        resized = image.resize(
            (draw_width, draw_height),
            Image.Resampling.NEAREST,
        )

        self.display_scale = scale
        self.display_offset_x = (
            canvas_width - draw_width
        ) // 2
        self.display_offset_y = (
            canvas_height - draw_height
        ) // 2

        self.display_photo = ImageTk.PhotoImage(
            resized
        )

        self.canvas.delete("all")
        self.canvas.create_image(
            self.display_offset_x,
            self.display_offset_y,
            anchor="nw",
            image=self.display_photo,
        )

    def clear_current_object(self) -> None:
        if self.current_object() is None:
            return

        self.selected_cells.clear()
        self.save_current_object_cells()
        self.redraw()

    def select_all_unassigned(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            return

        occupied: set[tuple[int, int]] = set()

        for other in self.app.artwork_objects:
            if other is artwork_object:
                continue
            occupied.update(other.coordinates)

        self.selected_cells = {
            cell_index
            for cell_index, coordinates in enumerate(self.cells)
            if not any(
                point in occupied
                for point in coordinates
            )
        }

        self.save_current_object_cells()
        self.redraw()

    def selected_target_layer_index(self) -> int:
        return max(
            0,
            int(
                self.target_layer_var.get().split(":", 1)[0]
            ) - 1,
        )

    def reassign_current_object(self) -> None:
        artwork_object = self.current_object()

        if artwork_object is None:
            return

        if not artwork_object.coordinates:
            messagebox.showinfo(
                "Empty object",
                "Add at least one cell to this object first.",
                parent=self.window,
            )
            return

        target = self.selected_target_layer_index()

        self.app.assignment_map = reassign_object(
            self.app.assignment_map,
            artwork_object,
            target,
        )

        self.app.reduced_image = image_from_assignment(
            self.app.assignment_map,
            [layer.color for layer in self.app.layers],
        )

        self.app.analysis = []
        self.app.cleanup_summary_var.set(
            f"Object Builder moved '{artwork_object.name}' to "
            f"{self.app.layers[target].name}."
        )

        self.app.refresh_reduced_preview()
        self.app.analyze_artwork()

        self.refresh_objects()
        self.redraw()

        self.status_var.set(
            f"Moved {artwork_object.name} to "
            f"{self.app.layers[target].name}."
        )

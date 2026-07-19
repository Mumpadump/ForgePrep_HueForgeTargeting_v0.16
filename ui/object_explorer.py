from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import ImageTk

from core.objects import (
    ArtworkObject,
    create_object_from_regions,
    reassign_object,
)
from core.palette import image_from_assignment
from core.regions import Region, create_region_overlay, find_regions


class ObjectExplorer:
    """
    Manual object builder.

    The user selects one or more regions that belong together, gives the
    collection a name such as Hat or Face, and can later move that whole object
    to another palette layer.
    """

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — Object Explorer")
        self.window.geometry("1120x760")
        self.window.minsize(920, 640)

        self.regions: list[Region] = []
        self.overlay_photo: ImageTk.PhotoImage | None = None

        self.layer_var = tk.StringVar()
        self.object_target_var = tk.StringVar()
        self.status_var = tk.StringVar(
            value="Select regions that belong to one object."
        )

        self.build_window()
        self.refresh_layer_choices()
        self.refresh_regions()
        self.refresh_objects()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Object Explorer",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 8))

        ttk.Label(
            main,
            text=(
                "Build semantic objects manually by grouping connected regions. "
                "This keeps same-colored parts such as a hat and face separate."
            ),
        ).pack(fill="x", pady=(0, 10))

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Label(controls, text="Source layer:").pack(side="left")

        self.layer_box = ttk.Combobox(
            controls,
            textvariable=self.layer_var,
            state="readonly",
            width=26,
        )
        self.layer_box.pack(side="left", padx=(5, 10))
        self.layer_box.bind(
            "<<ComboboxSelected>>",
            lambda event: self.refresh_regions(),
        )

        ttk.Button(
            controls,
            text="Create Object from Selected Regions",
            command=self.create_object,
        ).pack(side="left", padx=5)

        ttk.Button(
            controls,
            text="Select All Regions",
            command=self.select_all_regions,
        ).pack(side="left", padx=5)

        ttk.Button(
            controls,
            text="Clear Selection",
            command=lambda: self.region_list.selection_clear(0, "end"),
        ).pack(side="left", padx=5)

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        regions_panel = ttk.LabelFrame(
            content,
            text="Connected Regions",
            padding=8,
        )
        regions_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 5),
        )

        region_list_frame = ttk.Frame(regions_panel)
        region_list_frame.pack(fill="both", expand=True)

        self.region_list = tk.Listbox(
            region_list_frame,
            selectmode="extended",
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
            self.preview_selected_regions,
        )

        region_scroll = ttk.Scrollbar(
            region_list_frame,
            orient="vertical",
            command=self.region_list.yview,
        )
        region_scroll.pack(side="right", fill="y")
        self.region_list.configure(yscrollcommand=region_scroll.set)

        preview_panel = ttk.LabelFrame(
            content,
            text="Selection Preview",
            padding=8,
        )
        preview_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=5,
        )

        self.preview_label = ttk.Label(
            preview_panel,
            text="Select one or more regions",
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)

        objects_panel = ttk.LabelFrame(
            content,
            text="Saved Objects",
            padding=8,
        )
        objects_panel.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0),
        )

        object_list_frame = ttk.Frame(objects_panel)
        object_list_frame.pack(fill="both", expand=True)

        self.object_list = tk.Listbox(
            object_list_frame,
            exportselection=False,
            font=("Consolas", 10),
        )
        self.object_list.pack(
            side="left",
            fill="both",
            expand=True,
        )
        self.object_list.bind(
            "<<ListboxSelect>>",
            self.preview_selected_object,
        )

        object_scroll = ttk.Scrollbar(
            object_list_frame,
            orient="vertical",
            command=self.object_list.yview,
        )
        object_scroll.pack(side="right", fill="y")
        self.object_list.configure(yscrollcommand=object_scroll.set)

        object_actions = ttk.Frame(objects_panel)
        object_actions.pack(fill="x", pady=(8, 0))

        ttk.Label(
            object_actions,
            text="Move object to layer:",
        ).pack(side="left")

        self.target_box = ttk.Combobox(
            object_actions,
            textvariable=self.object_target_var,
            state="readonly",
            width=24,
        )
        self.target_box.pack(side="left", padx=(5, 8))

        ttk.Button(
            object_actions,
            text="Reassign Object",
            command=self.reassign_selected_object,
        ).pack(side="left", padx=4)

        ttk.Button(
            object_actions,
            text="Delete Object Definition",
            command=self.delete_selected_object,
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
        self.layer_box["values"] = values
        self.target_box["values"] = values

        if values and self.layer_var.get() not in values:
            self.layer_var.set(values[0])

        if values and self.object_target_var.get() not in values:
            self.object_target_var.set(values[0])

    def selected_layer_index(self) -> int:
        return max(
            0,
            int(self.layer_var.get().split(":", 1)[0]) - 1,
        )

    def selected_target_index(self) -> int:
        return max(
            0,
            int(self.object_target_var.get().split(":", 1)[0]) - 1,
        )

    def refresh_regions(self) -> None:
        if self.app.assignment_map is None:
            return

        self.refresh_layer_choices()
        layer_index = self.selected_layer_index()

        self.regions = find_regions(
            self.app.assignment_map,
            layer_index,
        )

        self.region_list.delete(0, "end")

        for region in self.regions:
            self.region_list.insert(
                "end",
                f"Region {region.region_number:04d}  "
                f"{region.size:8,d} px",
            )

        self.preview_label.configure(
            image="",
            text="Select one or more regions",
        )

        self.status_var.set(
            f"{len(self.regions):,} regions in "
            f"{self.app.layers[layer_index].name}."
        )

    def selected_regions(self) -> list[Region]:
        return [
            self.regions[int(index)]
            for index in self.region_list.curselection()
            if int(index) < len(self.regions)
        ]

    def preview_selected_regions(
        self,
        _event: object | None = None,
    ) -> None:
        selected = self.selected_regions()

        if not selected or self.app.reduced_image is None:
            return

        combined = create_object_from_regions(
            name="Selection",
            layer_index=selected[0].layer_index,
            regions=selected,
        )

        synthetic_region = Region(
            layer_index=combined.layer_index,
            region_number=0,
            coordinates=combined.coordinates,
        )

        overlay = create_region_overlay(
            self.app.reduced_image,
            synthetic_region,
        )
        overlay.thumbnail((430, 500))

        self.overlay_photo = ImageTk.PhotoImage(overlay)
        self.preview_label.configure(
            image=self.overlay_photo,
            text="",
        )

        self.status_var.set(
            f"{len(selected):,} selected regions • "
            f"{combined.pixel_count:,} total pixels"
        )

    def select_all_regions(self) -> None:
        if self.regions:
            self.region_list.selection_set(0, "end")
            self.preview_selected_regions()

    def create_object(self) -> None:
        selected = self.selected_regions()

        if not selected:
            messagebox.showinfo(
                "No regions selected",
                "Select one or more regions first.",
                parent=self.window,
            )
            return

        name = simpledialog.askstring(
            "Object name",
            "Name this object, for example Hat, Face, or Antlers:",
            parent=self.window,
        )

        if not name:
            return

        artwork_object = create_object_from_regions(
            name=name,
            layer_index=self.selected_layer_index(),
            regions=selected,
        )

        self.app.artwork_objects.append(artwork_object)
        self.refresh_objects()

        self.status_var.set(
            f"Created object '{artwork_object.name}' from "
            f"{len(selected):,} regions "
            f"({artwork_object.pixel_count:,} pixels)."
        )

    def refresh_objects(self) -> None:
        self.object_list.delete(0, "end")

        for index, artwork_object in enumerate(
            self.app.artwork_objects
        ):
            layer_name = (
                self.app.layers[artwork_object.layer_index].name
                if artwork_object.layer_index < len(self.app.layers)
                else "Unknown"
            )

            self.object_list.insert(
                "end",
                f"{index + 1:02d}. "
                f"{artwork_object.name:<18} "
                f"{artwork_object.pixel_count:8,d} px  "
                f"[{layer_name}]",
            )

    def selected_object_index(self) -> int | None:
        selection = self.object_list.curselection()

        if not selection:
            return None

        return int(selection[0])

    def preview_selected_object(
        self,
        _event: object | None = None,
    ) -> None:
        index = self.selected_object_index()

        if index is None or self.app.reduced_image is None:
            return

        artwork_object = self.app.artwork_objects[index]

        synthetic_region = Region(
            layer_index=artwork_object.layer_index,
            region_number=0,
            coordinates=artwork_object.coordinates,
        )

        overlay = create_region_overlay(
            self.app.reduced_image,
            synthetic_region,
        )
        overlay.thumbnail((430, 500))

        self.overlay_photo = ImageTk.PhotoImage(overlay)
        self.preview_label.configure(
            image=self.overlay_photo,
            text="",
        )

        self.status_var.set(
            f"Object: {artwork_object.name} • "
            f"{artwork_object.pixel_count:,} pixels"
        )

    def reassign_selected_object(self) -> None:
        index = self.selected_object_index()

        if index is None:
            messagebox.showinfo(
                "No object selected",
                "Select a saved object first.",
                parent=self.window,
            )
            return

        target = self.selected_target_index()
        artwork_object = self.app.artwork_objects[index]

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
            f"Object Explorer moved '{artwork_object.name}' to "
            f"{self.app.layers[target].name}."
        )

        self.app.refresh_reduced_preview()
        self.app.analyze_artwork()

        self.refresh_regions()
        self.refresh_objects()

        self.status_var.set(
            f"Moved '{artwork_object.name}' to "
            f"{self.app.layers[target].name}."
        )

    def delete_selected_object(self) -> None:
        index = self.selected_object_index()

        if index is None:
            return

        artwork_object = self.app.artwork_objects[index]

        confirmed = messagebox.askyesno(
            "Delete object definition?",
            (
                f"Delete the object definition '{artwork_object.name}'?\n\n"
                "This does not undo color changes already made."
            ),
            parent=self.window,
        )

        if not confirmed:
            return

        del self.app.artwork_objects[index]
        self.refresh_objects()
        self.preview_label.configure(
            image="",
            text="Select an object or regions",
        )

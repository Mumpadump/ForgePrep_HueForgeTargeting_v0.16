from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from core.hueforge_targeting import (
    build_false_color_preview,
    build_hueforge_input,
    normalize_target_luminances,
    write_hueforge_profile,
)
from core.objects import reassign_object


class HueForgeTargeting:
    """
    Assign artwork areas to physical filament targets and author the
    grayscale brightness bands HueForge will receive.
    """

    PREVIEW_SIZE = (470, 470)

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — HueForge Color Targeting")
        self.window.geometry("1320x900")
        self.window.minsize(1080, 760)

        self.color_photo: ImageTk.PhotoImage | None = None
        self.gray_photo: ImageTk.PhotoImage | None = None

        self.selected_object_index: int | None = None

        self.layer_var = tk.StringVar()
        self.luminance_var = tk.IntVar(value=128)
        self.status_var = tk.StringVar(
            value=(
                "Choose a manufacturing group, assign its target filament, "
                "then tune the grayscale band HueForge will receive."
            )
        )

        self.ensure_targets()
        self.build_window()
        self.refresh_layer_controls()
        self.refresh_objects()
        self.refresh_previews()

    def ensure_targets(self) -> None:
        self.app.hueforge_target_luminances = (
            normalize_target_luminances(
                getattr(
                    self.app,
                    "hueforge_target_luminances",
                    None,
                ),
                len(self.app.layers),
            )
        )

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="HueForge Color Targeting",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 6))

        ttk.Label(
            main,
            text=(
                "Tell ForgePrep which physical filament each area must become. "
                "ForgePrep then converts those assignments into controlled "
                "grayscale brightness bands for HueForge."
            ),
        ).pack(fill="x", pady=(0, 10))

        content = ttk.Frame(main)
        content.pack(fill="both", expand=True)

        left = ttk.LabelFrame(
            content,
            text="Manufacturing Groups",
            padding=8,
        )
        left.pack(side="left", fill="y", padx=(0, 6))

        self.object_list = tk.Listbox(
            left,
            width=34,
            exportselection=False,
            font=("Consolas", 10),
        )
        self.object_list.pack(fill="both", expand=True)
        self.object_list.bind(
            "<<ListboxSelect>>",
            self.select_object,
        )

        ttk.Label(
            left,
            text="Target filament:",
        ).pack(fill="x", pady=(10, 2))

        self.target_box = ttk.Combobox(
            left,
            textvariable=self.layer_var,
            state="readonly",
            width=30,
        )
        self.target_box.pack(fill="x", pady=(0, 6))

        ttk.Button(
            left,
            text="Assign Group to Filament",
            command=self.assign_group,
        ).pack(fill="x", pady=4)

        ttk.Label(
            left,
            text=(
                "Groups are optional masks. They help ForgePrep separate "
                "areas that must use different physical filaments."
            ),
            wraplength=260,
            justify="left",
        ).pack(fill="x", pady=(12, 0))

        middle = ttk.Frame(content)
        middle.pack(side="left", fill="both", expand=True, padx=6)

        preview_frame = ttk.Frame(middle)
        preview_frame.pack(fill="both", expand=True)

        self.color_label = self.make_preview(
            preview_frame,
            "Target Filament Preview",
            0,
        )
        self.gray_label = self.make_preview(
            preview_frame,
            "Actual HueForge Input",
            1,
        )

        ttk.Label(
            middle,
            text=(
                "Left: the intended physical colors. "
                "Right: the grayscale image that will be exported to HueForge."
            ),
            anchor="center",
        ).pack(fill="x", pady=(8, 0))

        right = ttk.LabelFrame(
            content,
            text="Filament Brightness Bands",
            padding=8,
        )
        right.pack(side="left", fill="y", padx=(6, 0))

        self.layers_frame = ttk.Frame(right)
        self.layers_frame.pack(fill="both", expand=True)

        ttk.Separator(right).pack(fill="x", pady=10)

        ttk.Button(
            right,
            text="Reset Evenly Spaced Bands",
            command=self.reset_targets,
        ).pack(fill="x", pady=4)

        ttk.Button(
            right,
            text="Export HueForge PNG + Profile",
            command=self.export_hueforge,
        ).pack(fill="x", pady=4)

        ttk.Label(
            right,
            text=(
                "Starter values organize the image into clear bands. "
                "They are not a substitute for filament TD calibration."
            ),
            wraplength=290,
            justify="left",
        ).pack(fill="x", pady=(12, 0))

        ttk.Label(
            main,
            textvariable=self.status_var,
            anchor="center",
        ).pack(fill="x", pady=(10, 0))

    def make_preview(
        self,
        parent: ttk.Frame,
        title: str,
        column: int,
    ) -> ttk.Label:
        parent.columnconfigure(column, weight=1)

        panel = ttk.LabelFrame(
            parent,
            text=title,
            padding=8,
        )
        panel.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=4,
        )

        label = ttk.Label(
            panel,
            text="No preview",
            anchor="center",
        )
        label.pack(fill="both", expand=True)

        return label

    def layer_values(self) -> list[str]:
        return [
            f"{index + 1}: {layer.name}"
            for index, layer in enumerate(self.app.layers)
        ]

    def refresh_objects(self) -> None:
        self.object_list.delete(0, "end")

        for artwork_object in self.app.artwork_objects:
            layer_name = (
                self.app.layers[artwork_object.layer_index].name
                if 0 <= artwork_object.layer_index < len(self.app.layers)
                else "Unassigned"
            )
            self.object_list.insert(
                "end",
                (
                    f"{artwork_object.name:<18} "
                    f"→ {layer_name:<12} "
                    f"{artwork_object.pixel_count:>7,d}px"
                ),
            )

        if not self.app.artwork_objects:
            self.object_list.insert(
                "end",
                "No saved groups — use Object Builder first.",
            )

    def select_object(self, _event: object = None) -> None:
        selection = self.object_list.curselection()

        if (
            not selection
            or not self.app.artwork_objects
        ):
            self.selected_object_index = None
            return

        self.selected_object_index = int(selection[0])
        artwork_object = self.app.artwork_objects[
            self.selected_object_index
        ]

        values = self.layer_values()
        if 0 <= artwork_object.layer_index < len(values):
            self.layer_var.set(
                values[artwork_object.layer_index]
            )

    def assign_group(self) -> None:
        if self.selected_object_index is None:
            messagebox.showwarning(
                "No group selected",
                "Select a saved manufacturing group first.",
                parent=self.window,
            )
            return

        value = self.layer_var.get()

        if not value:
            return

        target_index = max(
            0,
            int(value.split(":", 1)[0]) - 1,
        )

        artwork_object = self.app.artwork_objects[
            self.selected_object_index
        ]

        self.app.assignment_map = reassign_object(
            self.app.assignment_map,
            artwork_object,
            target_index,
        )

        from core.palette import image_from_assignment

        self.app.reduced_image = image_from_assignment(
            self.app.assignment_map,
            [
                layer.color
                for layer in self.app.layers
            ],
        )
        self.app.original_assignment_map = (
            self.app.assignment_map.copy()
        )
        self.app.manufacturing_map = None
        self.app.refresh_reduced_preview()

        self.refresh_objects()
        self.refresh_previews()

        self.status_var.set(
            f"{artwork_object.name} assigned to "
            f"{self.app.layers[target_index].name}."
        )

    def refresh_layer_controls(self) -> None:
        for child in self.layers_frame.winfo_children():
            child.destroy()

        values = self.layer_values()
        self.target_box["values"] = values

        if values and self.layer_var.get() not in values:
            self.layer_var.set(values[0])

        for index, layer in enumerate(self.app.layers):
            frame = ttk.LabelFrame(
                self.layers_frame,
                text=f"{index + 1}. {layer.name}",
                padding=6,
            )
            frame.pack(fill="x", pady=4)

            filament = layer.filament or "(filament not named)"
            ttk.Label(
                frame,
                text=filament,
            ).pack(fill="x")

            value_var = tk.IntVar(
                value=self.app.hueforge_target_luminances[index]
            )

            row = ttk.Frame(frame)
            row.pack(fill="x", pady=(4, 0))

            ttk.Scale(
                row,
                from_=0,
                to=255,
                orient="horizontal",
                variable=value_var,
                command=lambda _value, i=index, v=value_var: (
                    self.set_target(i, v.get())
                ),
            ).pack(side="left", fill="x", expand=True)

            value_label = ttk.Label(
                row,
                textvariable=value_var,
                width=4,
                anchor="e",
            )
            value_label.pack(side="left", padx=(6, 0))

    def set_target(
        self,
        index: int,
        value: int,
    ) -> None:
        self.app.hueforge_target_luminances[index] = max(
            0,
            min(255, int(round(value))),
        )
        self.refresh_previews()

    def reset_targets(self) -> None:
        self.app.hueforge_target_luminances = (
            normalize_target_luminances(
                None,
                len(self.app.layers),
            )
        )
        self.refresh_layer_controls()
        self.refresh_previews()
        self.status_var.set(
            "Brightness bands reset to evenly spaced starter values."
        )

    def refresh_previews(self) -> None:
        if self.app.assignment_map is None:
            return

        color = build_false_color_preview(
            self.app.assignment_map,
            self.app.layers,
        )
        gray = build_hueforge_input(
            self.app.assignment_map,
            self.app.hueforge_target_luminances,
        )

        color.thumbnail(
            self.PREVIEW_SIZE
        )
        gray.thumbnail(
            self.PREVIEW_SIZE
        )

        self.color_photo = ImageTk.PhotoImage(color)
        self.gray_photo = ImageTk.PhotoImage(gray)

        self.color_label.configure(
            image=self.color_photo,
            text="",
        )
        self.gray_label.configure(
            image=self.gray_photo,
            text="",
        )

    def export_hueforge(self) -> None:
        if (
            self.app.assignment_map is None
            or self.app.image_path is None
        ):
            return

        destination = filedialog.askdirectory(
            title="Choose HueForge export location",
            parent=self.window,
        )

        if not destination:
            return

        folder = Path(destination)
        stem = self.app.image_path.stem

        png_path = folder / f"{stem}_HueForge_Input.png"
        profile_path = folder / f"{stem}_HueForge_Profile.json"

        image = build_hueforge_input(
            self.app.assignment_map,
            self.app.hueforge_target_luminances,
        )
        image.save(png_path)

        write_hueforge_profile(
            path=profile_path,
            source_name=self.app.image_path.name,
            layers=self.app.layers,
            target_luminances=self.app.hueforge_target_luminances,
            object_assignments=self.app.artwork_objects,
        )

        messagebox.showinfo(
            "HueForge export complete",
            (
                f"Created:\n\n{png_path.name}\n"
                f"{profile_path.name}\n\n"
                "Load the PNG into HueForge and use the same filament "
                "stack recorded in the profile."
            ),
            parent=self.window,
        )

        self.status_var.set(
            f"Exported {png_path.name} and profile."
        )

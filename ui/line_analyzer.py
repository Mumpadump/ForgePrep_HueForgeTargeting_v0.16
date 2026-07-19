from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import ImageTk

from core.line_art import (
    LineArtStats,
    analyze_line_mask,
    comparison_overlay,
    detect_dark_lines,
    line_mask_image,
    repair_line_mask,
)


class LineArtAnalyzer:
    """Analyze and preview line-art repair settings."""

    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("ForgePrep — Line Art Analyzer")
        self.window.geometry("1180x820")
        self.window.minsize(980, 680)

        self.original_mask = None
        self.repaired_mask = None

        self.original_photo: ImageTk.PhotoImage | None = None
        self.repaired_photo: ImageTk.PhotoImage | None = None
        self.overlay_photo: ImageTk.PhotoImage | None = None

        self.threshold_var = tk.IntVar(value=55)
        self.close_var = tk.IntVar(value=1)
        self.thicken_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(
            value="Adjust the settings and click Analyze Line Art."
        )

        self.build_window()
        self.analyze()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(
            main,
            text="Line Art Analyzer",
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(0, 8))

        ttk.Label(
            main,
            text=(
                "ForgePrep detects dark line art from the original image, "
                "then previews conservative gap closing and line thickening."
            ),
        ).pack(fill="x", pady=(0, 10))

        controls = ttk.LabelFrame(
            main,
            text="Detection and Repair Settings",
            padding=10,
        )
        controls.pack(fill="x")

        ttk.Label(
            controls,
            text="Dark-line threshold:",
        ).pack(side="left")

        ttk.Spinbox(
            controls,
            from_=0,
            to=255,
            width=7,
            textvariable=self.threshold_var,
        ).pack(side="left", padx=(5, 16))

        ttk.Label(
            controls,
            text="Close gaps:",
        ).pack(side="left")

        ttk.Spinbox(
            controls,
            from_=0,
            to=5,
            width=6,
            textvariable=self.close_var,
        ).pack(side="left", padx=(5, 16))

        ttk.Label(
            controls,
            text="Thicken lines:",
        ).pack(side="left")

        ttk.Spinbox(
            controls,
            from_=0,
            to=5,
            width=6,
            textvariable=self.thicken_var,
        ).pack(side="left", padx=(5, 16))

        ttk.Button(
            controls,
            text="Analyze Line Art",
            command=self.analyze,
        ).pack(side="left", padx=5)

        ttk.Button(
            controls,
            text="Use Repaired Mask in Outline Explorer",
            command=self.apply_repaired_mask,
        ).pack(side="left", padx=5)

        previews = ttk.Frame(main)
        previews.pack(fill="both", expand=True, pady=(10, 0))

        self.original_label = self.make_panel(
            previews,
            "Detected Line Art",
            0,
        )
        self.repaired_label = self.make_panel(
            previews,
            "Repaired Line Art",
            1,
        )
        self.overlay_label = self.make_panel(
            previews,
            "Repair Overlay",
            2,
        )

        report_frame = ttk.LabelFrame(
            main,
            text="Line Art Report",
            padding=8,
        )
        report_frame.pack(fill="x", pady=(10, 0))

        self.report_text = tk.Text(
            report_frame,
            height=8,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
        )
        self.report_text.pack(fill="x")

        ttk.Label(
            main,
            textvariable=self.status_var,
            anchor="center",
        ).pack(fill="x", pady=(8, 0))

    def make_panel(
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

    def set_report(
        self,
        original: LineArtStats,
        repaired: LineArtStats,
    ) -> None:
        text = "\n".join(
            [
                "ORIGINAL LINE ART",
                f"Outline coverage : {original.outline_percentage:6.2f}%",
                f"Enclosed cells   : {original.enclosed_cells:,}",
                f"Edge leaks       : {original.edge_leaks:,}",
                f"Largest cell     : {original.largest_cell:,} px",
                "",
                "REPAIRED LINE ART",
                f"Outline coverage : {repaired.outline_percentage:6.2f}%",
                f"Enclosed cells   : {repaired.enclosed_cells:,}",
                f"Edge leaks       : {repaired.edge_leaks:,}",
                f"Largest cell     : {repaired.largest_cell:,} px",
                "",
                (
                    "Interpretation: more enclosed cells can mean successful "
                    "gap repair, but excessive thickening may split artwork "
                    "into false shapes."
                ),
            ]
        )

        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", text)
        self.report_text.configure(state="disabled")

    def analyze(self) -> None:
        if self.app.original_image is None:
            messagebox.showwarning(
                "No artwork",
                "Open an image first.",
                parent=self.window,
            )
            return

        try:
            self.original_mask = detect_dark_lines(
                self.app.original_image,
                int(self.threshold_var.get()),
            )

            self.repaired_mask = repair_line_mask(
                self.original_mask,
                close_iterations=int(self.close_var.get()),
                thicken_iterations=int(self.thicken_var.get()),
            )

            original_preview = line_mask_image(
                self.original_mask
            )
            original_preview.thumbnail((380, 470))

            repaired_preview = line_mask_image(
                self.repaired_mask
            )
            repaired_preview.thumbnail((380, 470))

            overlay = comparison_overlay(
                self.app.original_image,
                self.original_mask,
                self.repaired_mask,
            )
            overlay.thumbnail((380, 470))

            self.original_photo = ImageTk.PhotoImage(
                original_preview
            )
            self.repaired_photo = ImageTk.PhotoImage(
                repaired_preview
            )
            self.overlay_photo = ImageTk.PhotoImage(
                overlay
            )

            self.original_label.configure(
                image=self.original_photo,
                text="",
            )
            self.repaired_label.configure(
                image=self.repaired_photo,
                text="",
            )
            self.overlay_label.configure(
                image=self.overlay_photo,
                text="",
            )

            original_stats = analyze_line_mask(
                self.original_mask
            )
            repaired_stats = analyze_line_mask(
                self.repaired_mask
            )

            self.set_report(
                original_stats,
                repaired_stats,
            )

            added = int(
                (
                    self.repaired_mask
                    & ~self.original_mask
                ).sum()
            )

            self.status_var.set(
                f"Repair preview adds {added:,} outline pixels. "
                "Green = existing line art; red = repair pixels."
            )

        except Exception as error:
            messagebox.showerror(
                "Line analysis failed",
                str(error),
                parent=self.window,
            )

    def apply_repaired_mask(self) -> None:
        if self.repaired_mask is None:
            return

        self.app.repaired_line_mask = (
            self.repaired_mask.copy()
        )
        self.app.line_repair_settings = {
            "threshold": int(self.threshold_var.get()),
            "close_iterations": int(self.close_var.get()),
            "thicken_iterations": int(self.thicken_var.get()),
        }

        self.app.cleanup_summary_var.set(
            "Line Art Analyzer supplied a repaired outline mask "
            "for Outline Explorer."
        )

        messagebox.showinfo(
            "Repaired outline saved",
            (
                "The repaired line mask is now available to "
                "Outline Explorer.\n\n"
                "Open Outline Explorer and choose "
                "'Use repaired line mask'."
            ),
            parent=self.window,
        )

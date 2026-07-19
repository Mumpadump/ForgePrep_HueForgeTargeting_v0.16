from __future__ import annotations
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageTk
from core.manufacturing_map import build_manufacturing_map, confidence_preview, edge_preview, object_preview

class ManufacturingMapViewer:
    PREVIEW_SIZE = (420, 420)
    def __init__(self, app: object) -> None:
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title('ForgePrep — Manufacturing Map')
        self.window.geometry('1260x820')
        self.window.minsize(1040, 680)
        self.edge_photo = self.confidence_photo = self.object_photo = None
        self.status_var = tk.StringVar(value='Building manufacturing map...')
        self.build_window()
        self.rebuild()

    def build_window(self) -> None:
        main = ttk.Frame(self.window, padding=12); main.pack(fill='both', expand=True)
        ttk.Label(main, text='Manufacturing Map', font=('Segoe UI',18,'bold')).pack(pady=(0,8))
        ttk.Label(main, text='Shared per-pixel data for Smart Brush, confidence, validation, SVG, and 3MF tools.').pack(fill='x', pady=(0,10))
        toolbar = ttk.Frame(main); toolbar.pack(fill='x', pady=(0,10))
        ttk.Button(toolbar, text='Rebuild Manufacturing Map', command=self.rebuild).pack(side='left')
        ttk.Button(toolbar, text='Save Map to Current Project', command=self.save_to_app).pack(side='left', padx=8)
        previews = ttk.Frame(main); previews.pack(fill='both', expand=True)
        self.edge_label = self.make_panel(previews,'Edge Strength',0)
        self.confidence_label = self.make_panel(previews,'Confidence Map',1)
        self.object_label = self.make_panel(previews,'Saved Manufacturing Groups',2)
        report = ttk.LabelFrame(main,text='Map Summary',padding=8); report.pack(fill='x', pady=(10,0))
        self.report_text = tk.Text(report,height=8,state='disabled',font=('Consolas',10)); self.report_text.pack(fill='x')
        ttk.Label(main,textvariable=self.status_var,anchor='center').pack(fill='x', pady=(8,0))

    def make_panel(self,parent,title,column):
        parent.columnconfigure(column, weight=1)
        panel = ttk.LabelFrame(parent,text=title,padding=8); panel.grid(row=0,column=column,sticky='nsew',padx=4)
        label = ttk.Label(panel,text='No preview',anchor='center'); label.pack(fill='both',expand=True); return label

    def set_report(self) -> None:
        m = self.app.manufacturing_map
        assigned = int((m.object_id >= 0).sum()); total = int(m.object_id.size)
        pct = assigned / total * 100 if total else 0.0
        lines = [
            f'Image size            : {m.shape[1]} × {m.shape[0]} px',
            f'Palette layers        : {len(self.app.layers)}',
            f'Manufacturing groups  : {len(self.app.artwork_objects)}',
            f'Assigned object pixels: {assigned:,} ({pct:.2f}%)',
            f'Outline pixels        : {int(m.outline_mask.sum()):,}',
            f'Average edge strength : {float(m.edge_strength.mean()):.2f} / 255',
            f'Average confidence    : {float(m.confidence.mean()):.2f} / 100',
            '',
            'Confidence colors: red = uncertain, yellow = moderate, green = high.',
        ]
        self.report_text.configure(state='normal'); self.report_text.delete('1.0','end'); self.report_text.insert('1.0','\n'.join(lines)); self.report_text.configure(state='disabled')

    def rebuild(self) -> None:
        if self.app.original_image is None or self.app.assignment_map is None:
            messagebox.showwarning('Nothing to map','Open an image and generate a preview first.',parent=self.window); return
        try:
            self.app.manufacturing_map = build_manufacturing_map(
                self.app.original_image,
                self.app.assignment_map,
                self.app.artwork_objects,
                getattr(self.app,'repaired_line_mask',None),
                int(getattr(self.app,'line_repair_settings',{}).get('threshold',55)),
            )
            edge = edge_preview(self.app.manufacturing_map); conf = confidence_preview(self.app.manufacturing_map); obj = object_preview(self.app.manufacturing_map)
            edge.thumbnail(self.PREVIEW_SIZE); conf.thumbnail(self.PREVIEW_SIZE); obj.thumbnail(self.PREVIEW_SIZE)
            self.edge_photo = ImageTk.PhotoImage(edge); self.confidence_photo = ImageTk.PhotoImage(conf); self.object_photo = ImageTk.PhotoImage(obj)
            self.edge_label.configure(image=self.edge_photo,text=''); self.confidence_label.configure(image=self.confidence_photo,text=''); self.object_label.configure(image=self.object_photo,text='')
            self.set_report(); self.status_var.set('Manufacturing map rebuilt successfully.')
        except Exception as error:
            messagebox.showerror('Manufacturing map failed',str(error),parent=self.window)

    def save_to_app(self) -> None:
        if getattr(self.app,'manufacturing_map',None) is None: self.rebuild()
        self.app.cleanup_summary_var.set('Manufacturing Map v0.15 is active for this project.')
        messagebox.showinfo('Manufacturing map saved','The project now has shared edge, outline, palette, object, and confidence metadata.',parent=self.window)

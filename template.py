import json
from dataclasses import dataclass, field
from enum import Enum
from tkinter import ttk, filedialog, messagebox
import tkinter as tk

from pydantic import BaseModel, Field
from PIL import Image, ImageTk

# A4 at 300 DPI (portrait)
TARGET_W, TARGET_H = 2480, 3508

# ── Shared primitives ────────────────────────────────────────────
class BubbleShape(str, Enum):
    rectangle = "rectangle"
    ellipse = "ellipse"

class BubbleDimensions(BaseModel):
    shape: BubbleShape
    width: int = Field(gt=0)
    height: int = Field(gt=0)

class Bubble(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    value: str

class ImageDimensions(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)

class Entry(BaseModel):
    question: int = Field(gt=0)  # 1-indexed question number
    bubbles: list[Bubble] = Field(min_length=1)

class BubbleField(BaseModel):
    name: str
    bubble: BubbleDimensions
    entries: list[Entry] = Field(min_length=1)

# ── Root template ────────────────────────────────────────────────
class OMRTemplate(BaseModel):
    name: str
    image: ImageDimensions
    fields: list[BubbleField] = Field(min_length=1)

# ── Blueprint template ────────────────────────────────────────────────
class BubbleOverride(BaseModel):
    question_index: int = Field(ge=0)   # 0-based within the entry
    option_index: int = Field(ge=0)     # 0-based
    dx: int = 0
    dy: int = 0

class EntryBlueprint(BaseModel):
    name: str
    start_x: int
    start_y: int
    num_questions: int
    options: list[str]
    row_spacing: int
    col_spacing: int
    vertical_options: bool = Field(default=False)
    start_question_num: int
    overrides: list[BubbleOverride] = Field(default_factory=list)

class BubbleFieldBlueprint(BaseModel):
    name: str
    shape: BubbleShape
    bubble_w: int
    bubble_h: int
    entries: list[EntryBlueprint] = Field(min_length=1)

class OMRTemplateBlueprint(BaseModel):
    name: str
    img_w: int = Field(gt=0)
    img_h: int = Field(gt=0)
    fields: list[BubbleFieldBlueprint] = Field(min_length=1)

# ── Mutable GUI state (mirrors the blueprint) ────────────────────
@dataclass
class EntryState:
    name: str = "Entry"
    start_x: int = 50
    start_y: int = 50
    num_questions: int = 5
    options: list = field(default_factory=lambda: ["A", "B", "C", "D"])
    row_spacing: int = 40
    col_spacing: int = 40
    vertical_options: bool = False
    start_question_num: int = 1
    overrides: dict = field(default_factory=dict)   # (q, o) -> (dx, dy)


def base_pos(e: EntryState, q: int, o: int):
    """Grid position BEFORE applying any override."""
    if e.vertical_options:
        return e.start_x + q * e.row_spacing, e.start_y + o * e.col_spacing
    return e.start_x + o * e.col_spacing, e.start_y + q * e.row_spacing


def expand_entry(e: EntryState):
    """Yield (x, y, value, qnum, q_index, o_index) with overrides applied."""
    for q in range(max(0, e.num_questions)):
        qnum = e.start_question_num + q
        for o, opt in enumerate(e.options):
            bx, by = base_pos(e, q, o)
            dx, dy = e.overrides.get((q, o), (0, 0))
            yield bx + dx, by + dy, opt, qnum, q, o

@dataclass
class FieldState:
    name: str = "Field"
    shape: str = "rectangle"
    bubble_w: int = 24
    bubble_h: int = 24
    entries: list = field(default_factory=list)


# ── Cloning helpers (preserve grid config + bubble overrides) ────
def clone_entry(e: EntryState, offset: int = 0, suffix: str = "") -> EntryState:
    """Deep copy of an entry: grid settings, options, and overrides."""
    return EntryState(
        name=e.name + suffix,
        start_x=e.start_x + offset,
        start_y=e.start_y + offset,
        num_questions=e.num_questions,
        options=list(e.options),                 # copy list
        row_spacing=e.row_spacing,
        col_spacing=e.col_spacing,
        vertical_options=e.vertical_options,
        start_question_num=e.start_question_num,
        overrides=dict(e.overrides),              # keys/values are tuples
    )


def clone_field(f: FieldState, offset: int = 20, suffix: str = " copy") -> FieldState:
    """Deep copy of a field, including every entry's overrides."""
    return FieldState(
        name=f.name + suffix,
        shape=f.shape,
        bubble_w=f.bubble_w,
        bubble_h=f.bubble_h,
        entries=[clone_entry(e, offset=offset) for e in f.entries],
    )


PALETTE = ["#ff5555", "#55aaff", "#55cc77", "#ffaa33",
           "#cc66ff", "#22cccc", "#ff77aa", "#aacc44"]

# ── Builders for the Pydantic outputs ────────────────────────────
def build_blueprint(name, iw, ih, fields):
    bp_fields = []
    for f in fields:
        entries = [EntryBlueprint(
            name=e.name, start_x=e.start_x, start_y=e.start_y,
            num_questions=e.num_questions, options=e.options,
            row_spacing=e.row_spacing, col_spacing=e.col_spacing,
            vertical_options=e.vertical_options,
            start_question_num=e.start_question_num,
            overrides=[BubbleOverride(question_index=qq, option_index=oo,
                                    dx=d[0], dy=d[1])
                    for (qq, oo), d in e.overrides.items()],
        ) for e in f.entries]
        bp_fields.append(BubbleFieldBlueprint(
            name=f.name, shape=BubbleShape(f.shape),
            bubble_w=f.bubble_w, bubble_h=f.bubble_h, entries=entries))
    return OMRTemplateBlueprint(name=name, img_w=iw, img_h=ih, fields=bp_fields)


def build_template(name, iw, ih, fields):
    out_fields = []
    for f in fields:
        out_entries = []
        for e in f.entries:
            by_q = {}
            for x, y, opt, qnum, q, o in expand_entry(e):
                by_q.setdefault(qnum, []).append(
                    Bubble(x=max(0, x), y=max(0, y), value=opt))
            for qnum, bubbles in by_q.items():
                out_entries.append(Entry(question=qnum, bubbles=bubbles))
        out_fields.append(BubbleField(
            name=f.name,
            bubble=BubbleDimensions(shape=BubbleShape(f.shape),
                                    width=f.bubble_w, height=f.bubble_h),
            entries=out_entries))
    return OMRTemplate(name=name,
                       image=ImageDimensions(width=iw, height=ih),
                       fields=out_fields)


def blueprint_to_fields(bp: OMRTemplateBlueprint):
    """Convert a loaded blueprint back into mutable GUI state."""
    fields = []
    for bf in bp.fields:
        entries = []
        for be in bf.entries:
            overrides = {(o.question_index, o.option_index): (o.dx, o.dy)
                         for o in be.overrides}
            entries.append(EntryState(
                name=be.name, start_x=be.start_x, start_y=be.start_y,
                num_questions=be.num_questions, options=list(be.options),
                row_spacing=be.row_spacing, col_spacing=be.col_spacing,
                vertical_options=be.vertical_options,
                start_question_num=be.start_question_num,
                overrides=overrides))
        fields.append(FieldState(
            name=bf.name, shape=bf.shape.value,
            bubble_w=bf.bubble_w, bubble_h=bf.bubble_h, entries=entries))
    return fields


# ── Application ──────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OMR Template Builder")
        self.geometry("1200x760")

        self.image = None
        self.tk_image = None
        self.fields: list[FieldState] = []
        self.sel_field: FieldState | None = None
        self.sel_entry: EntryState | None = None
        self._drag = None
        self._field_drag = None       # (origin_ix, origin_iy, [(entry, sx, sy), ...])

        self.zoom = 1.0
        self.min_zoom, self.max_zoom = 0.05, 8.0
        self.node_map = {}      # tree id -> ("field"/"entry", obj)
        self.id_to_node = {}    # id(obj) -> tree id

        # vars updated during canvas drag
        self.var_sx = None
        self.var_sy = None

        self._bubble_drag = None      # (entry, q, o, grab_dx, grab_dy)
        self._sel_bubble = None       # (entry, q, o) for highlight
        self.tune_var = tk.BooleanVar(value=False)
        self.autoresize_var = tk.BooleanVar(value=True)

        self._build_layout()

        # ---------- Arrow key bindings (new) ----------
        # Bind globally, but we'll check focus to avoid interfering with text entry.
        self.bind_all("<Up>", self.on_arrow_key)
        self.bind_all("<Down>", self.on_arrow_key)
        self.bind_all("<Left>", self.on_arrow_key)
        self.bind_all("<Right>", self.on_arrow_key)

    # ---------- layout ----------
    def _build_layout(self):
        # Scrollable sidebar: outer frame holds a canvas + scrollbar,
        # the actual widgets live in `side` (an inner frame on the canvas).
        sidebar_outer = ttk.Frame(self, width=320)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        self.sb_canvas = tk.Canvas(sidebar_outer, highlightthickness=0)
        sb_scroll = ttk.Scrollbar(sidebar_outer, orient="vertical",
                                  command=self.sb_canvas.yview)
        self.sb_canvas.configure(yscrollcommand=sb_scroll.set)
        sb_scroll.pack(side="right", fill="y")
        self.sb_canvas.pack(side="left", fill="both", expand=True)

        side = ttk.Frame(self.sb_canvas, padding=8)
        self._side_window = self.sb_canvas.create_window(
            (0, 0), window=side, anchor="nw")

        # keep scrollregion in sync with content, and width in sync with canvas
        side.bind("<Configure>",
                  lambda _e: self.sb_canvas.configure(
                      scrollregion=self.sb_canvas.bbox("all")))
        self.sb_canvas.bind("<Configure>",
                            lambda e: self.sb_canvas.itemconfigure(
                                self._side_window, width=e.width))

        # mousewheel scrolls the sidebar only while the pointer is over it
        def _sb_wheel(e):
            self.sb_canvas.yview_scroll(int(-e.delta / 120), "units")
        self.sb_canvas.bind("<Enter>", lambda _e: (
            self.sb_canvas.bind_all("<MouseWheel>", _sb_wheel),
            self.sb_canvas.bind_all("<Button-4>", lambda ev: self.sb_canvas.yview_scroll(-1, "units")),
            self.sb_canvas.bind_all("<Button-5>", lambda ev: self.sb_canvas.yview_scroll(1, "units")),
        ))
        self.sb_canvas.bind("<Leave>", lambda _e: (
            self.sb_canvas.unbind_all("<MouseWheel>"),
            self.sb_canvas.unbind_all("<Button-4>"),
            self.sb_canvas.unbind_all("<Button-5>"),
        ))

        ttk.Label(side, text="Template name").pack(anchor="w")
        self.tname = tk.StringVar(value="OMR Template")
        ttk.Entry(side, textvariable=self.tname).pack(fill="x", pady=(0, 6))

        row = ttk.Frame(side); row.pack(fill="x")
        ttk.Button(row, text="Load Image…", command=self.load_image).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(row, text="Load Blueprint…", command=self.import_blueprint).pack(
            side="left", expand=True, fill="x", padx=1)

        row2 = ttk.Frame(side); row2.pack(fill="x", pady=2)
        ttk.Button(row2, text="Export Blueprint", command=self.export_blueprint).pack(
            side="left", expand=True, fill="x", padx=1)
        ttk.Button(row2, text="Export Compiled", command=self.export_template).pack(
            side="left", expand=True, fill="x", padx=1)

        # auto-resize controls
        arf = ttk.LabelFrame(side, text="Image size", padding=6)
        arf.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(
            arf, text=f"Auto-resize to A4 300 DPI ({TARGET_W}×{TARGET_H})",
            variable=self.autoresize_var).pack(anchor="w")
        ttk.Button(arf, text="Resize current image",
                   command=self.resize_current).pack(fill="x", pady=(4, 0))
        self.size_label = ttk.Label(arf, text="No image loaded",
                                    foreground="#666", font=("Segoe UI", 8))
        self.size_label.pack(anchor="w", pady=(2, 0))

        # zoom
        zr = ttk.Frame(side); zr.pack(fill="x", pady=(6, 0))
        ttk.Button(zr, text="−", width=3, command=lambda: self.zoom_by(0.8)).pack(side="left")
        self.zlabel = ttk.Label(zr, text="100%", width=8, anchor="center")
        self.zlabel.pack(side="left", expand=True)
        ttk.Button(zr, text="+", width=3, command=lambda: self.zoom_by(1.25)).pack(side="left")
        ttk.Button(side, text="Fit to Window", command=self.fit_to_window).pack(fill="x", pady=2)

        ttk.Separator(side).pack(fill="x", pady=8)

        # tree of fields/entries
        ttk.Label(side, text="Structure", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.tree = ttk.Treeview(side, height=8, show="tree")
        self.tree.pack(fill="x")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        tr = ttk.Frame(side); tr.pack(fill="x", pady=2)
        ttk.Button(tr, text="+ Field", command=self.add_field).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(tr, text="+ Entry", command=self.add_entry).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(tr, text="Delete", command=self.delete_selected).pack(side="left", expand=True, fill="x", padx=1)

        tr2 = ttk.Frame(side); tr2.pack(fill="x", pady=2)
        ttk.Button(tr2, text="Duplicate Selected", command=self.duplicate_selected).pack(
            side="left", expand=True, fill="x", padx=1)

        ttk.Checkbutton(side, text="Tune individual bubbles",
                variable=self.tune_var).pack(anchor="w", pady=(4, 0))

        ttk.Label(side, text="Tip: select a field to drag the whole section;\n"
                             "select an entry to drag just that entry.",
                  foreground="#666", font=("Segoe UI", 8),
                  justify="left").pack(anchor="w", pady=(2, 0))

        ttk.Separator(side).pack(fill="x", pady=8)

        self.config_frame = ttk.LabelFrame(side, text="Configuration", padding=8)
        self.config_frame.pack(fill="both", expand=True)

        # canvas
        container = ttk.Frame(self)
        container.pack(side="right", fill="both", expand=True)
        self.canvas = tk.Canvas(container, bg="#2b2b2b", highlightthickness=0)
        hbar = ttk.Scrollbar(container, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Control-MouseWheel>", lambda e: self.zoom_by(1.25 if e.delta > 0 else 0.8))
        self.canvas.bind("<Control-Button-4>", lambda e: self.zoom_by(1.25))
        self.canvas.bind("<Control-Button-5>", lambda e: self.zoom_by(0.8))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.canvas.bind("<Shift-MouseWheel>", lambda e: self.canvas.xview_scroll(int(-e.delta / 120), "units"))

    # ---------- Arrow key support (new) ----------
    def on_arrow_key(self, event):
        """Handle arrow key presses to move selected element."""
        # Ignore if a text entry has focus
        focus = self.focus_get()
        if focus and focus.winfo_class() in ('Entry', 'TEntry', 'Combobox', 'TCombobox'):
            return

        # Determine step size
        shift = (event.state & 0x0001) != 0
        ctrl = (event.state & 0x0004) != 0
        if shift:
            step = 10
        elif ctrl:
            step = 5
        else:
            step = 1

        # Map key to (dx, dy)
        key = event.keysym
        if key == "Up":
            dx, dy = 0, -step
        elif key == "Down":
            dx, dy = 0, step
        elif key == "Left":
            dx, dy = -step, 0
        elif key == "Right":
            dx, dy = step, 0
        else:
            return

        self.move_selected(dx, dy)

    def move_selected(self, dx, dy):
        """Move the currently selected element(s) by (dx, dy) pixels."""
        # Tune mode: move individual bubble override
        if self.tune_var.get() and self._sel_bubble is not None:
            e, q, o = self._sel_bubble
            bx, by = base_pos(e, q, o)
            old_dx, old_dy = e.overrides.get((q, o), (0, 0))
            new_dx = old_dx + dx
            new_dy = old_dy + dy
            e.overrides[(q, o)] = (new_dx, new_dy)
            self.redraw()
            return

        # Entry selected: move that entry
        if self.sel_entry is not None:
            e = self.sel_entry
            nx = e.start_x + dx
            ny = e.start_y + dy
            # Update the config entry variables if they exist
            if self.var_sx is not None and self.var_sy is not None:
                self.var_sx.set(str(nx))
                self.var_sy.set(str(ny))
            else:
                e.start_x = nx
                e.start_y = ny
                self.redraw()
            return

        # Field selected: move all entries in that field
        if self.sel_field is not None:
            for e in self.sel_field.entries:
                e.start_x += dx
                e.start_y += dy
            self.redraw()
            return

        # Nothing selected – do nothing (could beep or show message)

    # ---------- coordinate helpers ----------
    def img_to_canvas(self, x, y):
        return x * self.zoom, y * self.zoom

    def canvas_to_img(self, cx, cy):
        return self.canvas.canvasx(cx) / self.zoom, self.canvas.canvasy(cy) / self.zoom

    # ---------- image / zoom ----------
    def _update_size_label(self):
        if self.image:
            iw, ih = self.image.size
            tag = "  ✓ A4" if (iw, ih) == (TARGET_W, TARGET_H) else ""
            self.size_label.config(text=f"Current: {iw}×{ih}{tag}")
        else:
            self.size_label.config(text="No image loaded")

    def load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if not path:
            return
        self.image = Image.open(path).convert("RGB")
        if self.autoresize_var.get():
            self.image = self.image.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
        self._update_size_label()
        self.fit_to_window()

    def resize_current(self):
        """Force the already-loaded image to the A4 target size."""
        if not self.image:
            messagebox.showinfo("Resize", "Load an image first.")
            return
        if self.image.size == (TARGET_W, TARGET_H):
            messagebox.showinfo("Resize", "Image is already at the target size.")
            return
        self.image = self.image.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
        self._update_size_label()
        self.fit_to_window()

    def set_zoom(self, v):
        self.zoom = max(self.min_zoom, min(self.max_zoom, v))
        self.zlabel.config(text=f"{int(self.zoom * 100)}%")
        self.redraw()

    def zoom_by(self, f):
        self.set_zoom(self.zoom * f)

    def fit_to_window(self):
        if not self.image:
            return
        self.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            self.after(50, self.fit_to_window)
            return
        iw, ih = self.image.size
        self.set_zoom(min(cw / iw, ch / ih))

    # ---------- structure editing ----------
    def add_field(self):
        f = FieldState(name=f"Field {len(self.fields) + 1}",
                       entries=[EntryState(name="Entry 1")])
        self.fields.append(f)
        self.refresh_tree(select=f.entries[0])

    def add_entry(self):
        if not self.sel_field:
            messagebox.showinfo("Add Entry", "Select a field first.")
            return
        e = EntryState(name=f"Entry {len(self.sel_field.entries) + 1}",
                       start_x=self.sel_field.entries[-1].start_x if self.sel_field.entries else 50,
                       start_y=(self.sel_field.entries[-1].start_y + 200) if self.sel_field.entries else 50)
        self.sel_field.entries.append(e)
        self.refresh_tree(select=e)

    def duplicate_selected(self):
        # Duplicating an entry takes priority over its parent field.
        if self.sel_entry and self.sel_field:
            new_e = clone_entry(self.sel_entry, offset=20, suffix=" copy")
            idx = self.sel_field.entries.index(self.sel_entry)
            self.sel_field.entries.insert(idx + 1, new_e)
            self.refresh_tree(select=new_e)
        elif self.sel_field:
            new_f = clone_field(self.sel_field)
            idx = self.fields.index(self.sel_field)
            self.fields.insert(idx + 1, new_f)
            target = new_f.entries[0] if new_f.entries else new_f
            self.refresh_tree(select=target)
        else:
            messagebox.showinfo("Duplicate", "Select a field or entry first.")

    def delete_selected(self):
        if self.sel_entry and self.sel_field:
            self.sel_field.entries.remove(self.sel_entry)
            if not self.sel_field.entries:
                self.fields.remove(self.sel_field)
            self.sel_entry = self.sel_field = None
        elif self.sel_field:
            self.fields.remove(self.sel_field)
            self.sel_field = None
        self._sel_bubble = None
        self.refresh_tree()

    # ---------- tree ----------
    def refresh_tree(self, select=None):
        self.tree.delete(*self.tree.get_children())
        self.node_map.clear()
        self.id_to_node.clear()
        for f in self.fields:
            fid = self.tree.insert("", "end", text=f"📋 {f.name}", open=True)
            self.node_map[fid] = ("field", f)
            self.id_to_node[id(f)] = fid
            for e in f.entries:
                eid = self.tree.insert(fid, "end", text=f"   • {e.name}")
                self.node_map[eid] = ("entry", e)
                self.id_to_node[id(e)] = eid
        if select is not None and id(select) in self.id_to_node:
            self.tree.selection_set(self.id_to_node[id(select)])
        self.redraw()

    def on_tree_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        kind, obj = self.node_map[sel[0]]
        if kind == "field":
            self.sel_field, self.sel_entry = obj, None
            self.build_field_config(obj)
        else:
            self.sel_entry = obj
            # find parent field
            for f in self.fields:
                if obj in f.entries:
                    self.sel_field = f
                    break
            self.build_entry_config(obj)
        self.redraw()

    # ---------- config panels ----------
    def _clear_config(self):
        for w in self.config_frame.winfo_children():
            w.destroy()

    def _str_row(self, parent, label, obj, attr, on_extra=None):
        ttk.Label(parent, text=label).pack(anchor="w")
        var = tk.StringVar(value=str(getattr(obj, attr)))
        ttk.Entry(parent, textvariable=var).pack(fill="x", pady=(0, 6))
        def cb(*_):
            setattr(obj, attr, var.get())
            if on_extra:
                on_extra()
            self.redraw()
        var.trace_add("write", cb)
        return var

    def _int_row(self, parent, label, obj, attr):
        ttk.Label(parent, text=label).pack(anchor="w")
        var = tk.StringVar(value=str(getattr(obj, attr)))
        ttk.Entry(parent, textvariable=var).pack(fill="x", pady=(0, 6))
        def cb(*_):
            try:
                setattr(obj, attr, int(var.get()))
            except ValueError:
                return
            self.redraw()
        var.trace_add("write", cb)
        return var

    def build_field_config(self, f: FieldState):
        self._clear_config()
        self.config_frame.config(text="Field (drag whole section on canvas)")
        self._str_row(self.config_frame, "Name", f, "name",
                      on_extra=lambda: self._rename_node(f, f"📋 {f.name}"))
        ttk.Label(self.config_frame, text="Bubble shape").pack(anchor="w")
        svar = tk.StringVar(value=f.shape)
        cb = ttk.Combobox(self.config_frame, textvariable=svar, state="readonly",
                          values=["rectangle", "ellipse"])
        cb.pack(fill="x", pady=(0, 6))
        svar.trace_add("write", lambda *_: (setattr(f, "shape", svar.get()), self.redraw()))
        self._int_row(self.config_frame, "Bubble width", f, "bubble_w")
        self._int_row(self.config_frame, "Bubble height", f, "bubble_h")

        ttk.Separator(self.config_frame).pack(fill="x", pady=8)
        ttk.Button(self.config_frame, text="Nudge section…",
                   command=lambda: self._nudge_field(f)).pack(fill="x")

    def _nudge_field(self, f: FieldState):
        """Small dialog to move a whole field by an exact pixel offset."""
        if not f.entries:
            return
        dlg = tk.Toplevel(self)
        dlg.title(f"Move {f.name}")
        dlg.transient(self)
        dlg.resizable(False, False)
        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="Offset X").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Offset Y").grid(row=1, column=0, sticky="w")
        vx = tk.StringVar(value="0")
        vy = tk.StringVar(value="0")
        ttk.Entry(frm, textvariable=vx, width=8).grid(row=0, column=1, padx=6, pady=2)
        ttk.Entry(frm, textvariable=vy, width=8).grid(row=1, column=1, padx=6, pady=2)

        def apply_and_close():
            try:
                dx, dy = int(vx.get()), int(vy.get())
            except ValueError:
                return
            for e in f.entries:
                e.start_x += dx
                e.start_y += dy
            self.redraw()
            dlg.destroy()

        ttk.Button(frm, text="Apply", command=apply_and_close).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    def build_entry_config(self, e: EntryState):
        self._clear_config()
        self.config_frame.config(text="Entry")
        self._str_row(self.config_frame, "Name", e, "name",
                      on_extra=lambda: self._rename_node(e, f"   • {e.name}"))
        self.var_sx = self._int_row(self.config_frame, "Start X", e, "start_x")
        self.var_sy = self._int_row(self.config_frame, "Start Y", e, "start_y")
        self._int_row(self.config_frame, "Num questions", e, "num_questions")
        self._int_row(self.config_frame, "Start question #", e, "start_question_num")
        self._int_row(self.config_frame, "Row spacing (between questions)", e, "row_spacing")
        self._int_row(self.config_frame, "Col spacing (between options)", e, "col_spacing")

        ttk.Label(self.config_frame, text="Options (comma separated)").pack(anchor="w")
        ovar = tk.StringVar(value=",".join(e.options))
        ttk.Entry(self.config_frame, textvariable=ovar).pack(fill="x", pady=(0, 6))
        def opt_cb(*_):
            e.options = [o.strip() for o in ovar.get().split(",") if o.strip()]
            self.redraw()
        ovar.trace_add("write", opt_cb)

        bvar = tk.BooleanVar(value=e.vertical_options)
        ttk.Checkbutton(self.config_frame, text="Vertical options",
                        variable=bvar,
                        command=lambda: (setattr(e, "vertical_options", bvar.get()),
                                         self.redraw())).pack(anchor="w", pady=4)

        ttk.Button(self.config_frame, text="Clear bubble overrides",
           command=lambda: (e.overrides.clear(),
                            setattr(self, "_sel_bubble", None),
                            self.redraw())).pack(fill="x", pady=(6, 0))

    def _rename_node(self, obj, text):
        nid = self.id_to_node.get(id(obj))
        if nid:
            self.tree.item(nid, text=text)

    # ---------- drawing ----------
    def field_color(self, f):
        return PALETTE[self.fields.index(f) % len(PALETTE)]

    def redraw(self):
        self.canvas.delete("all")
        if self.image:
            iw, ih = self.image.size
            dw, dh = max(1, int(iw * self.zoom)), max(1, int(ih * self.zoom))
            self.tk_image = ImageTk.PhotoImage(self.image.resize((dw, dh), Image.Resampling.LANCZOS))
            self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
            self.canvas.configure(scrollregion=(0, 0, dw, dh))

        for f in self.fields:
            color = self.field_color(f)
            bw, bh = f.bubble_w, f.bubble_h
            for e in f.entries:
                selected = (e is self.sel_entry)
                for x, y, val, qnum, q, o in expand_entry(e):
                    x0, y0 = self.img_to_canvas(x, y)
                    x1, y1 = self.img_to_canvas(x + bw, y + bh)

                    is_override = (q, o) in e.overrides
                    is_sel_bubble = self._sel_bubble == (e, q, o)
                    if is_sel_bubble:
                        outline, width = "yellow", 3
                    elif is_override:
                        outline, width = "#ffcc00", 2
                    elif selected:
                        outline, width = "white", 2
                    else:
                        outline, width = color, 1

                    if f.shape == "ellipse":
                        self.canvas.create_oval(x0, y0, x1, y1, outline=outline,
                                                width=width, fill=color, stipple="gray25")
                    else:
                        self.canvas.create_rectangle(x0, y0, x1, y1, outline=outline,
                                                     width=width, fill=color, stipple="gray25")
                    if bw * self.zoom >= 16:
                        self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                                                text=val, fill="white",
                                                font=("Segoe UI", 7))

        # selected-section bounding box (drawn on top so it's always visible)
        if self.sel_field and self.sel_entry is None and self.sel_field.entries:
            x0, y0, x1, y1 = self._field_bbox(self.sel_field)
            cx0, cy0 = self.img_to_canvas(x0 - 6, y0 - 6)
            cx1, cy1 = self.img_to_canvas(x1 + 6, y1 + 6)
            self.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=self.field_color(self.sel_field),
                dash=(6, 4), width=2)
            self.canvas.create_text(
                cx0 + 4, cy0 - 8, anchor="w",
                text=f"⤧ {self.sel_field.name}",
                fill=self.field_color(self.sel_field),
                font=("Segoe UI", 8, "bold"))

    # ---------- canvas interaction ----------
    def _entry_bbox(self, e, f):
        pts = list(expand_entry(e))
        if not pts:
            return (e.start_x, e.start_y, e.start_x + f.bubble_w, e.start_y + f.bubble_h)
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs) + f.bubble_w, max(ys) + f.bubble_h)

    def _field_bbox(self, f):
        """Union of every entry's bounding box in the field (image coords)."""
        boxes = [self._entry_bbox(e, f) for e in f.entries]
        if not boxes:
            return (0, 0, 0, 0)
        return (min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes))

    def _hit_bubble(self, ix, iy):
        for f in reversed(self.fields):
            bw, bh = f.bubble_w, f.bubble_h
            for e in reversed(f.entries):
                for x, y, val, qnum, q, o in expand_entry(e):
                    if x <= ix <= x + bw and y <= iy <= y + bh:
                        return e, q, o, x, y
        return None

    def _on_press(self, evt):
        ix, iy = self.canvas_to_img(evt.x, evt.y)

        if self.tune_var.get():
            hit = self._hit_bubble(ix, iy)
            if hit:
                e, q, o, bx, by = hit
                self._bubble_drag = (e, q, o, ix - bx, iy - by)
                self._sel_bubble = (e, q, o)
                nid = self.id_to_node.get(id(e))
                if nid:
                    self.tree.selection_set(nid)
                self.redraw()
            return

        # If a whole field/section is selected, drag every entry together
        # when the press lands inside the section's bounding box.
        if self.sel_field and self.sel_entry is None and self.sel_field.entries:
            x0, y0, x1, y1 = self._field_bbox(self.sel_field)
            if x0 - 6 <= ix <= x1 + 6 and y0 - 6 <= iy <= y1 + 6:
                self._field_drag = (ix, iy,
                                     [(e, e.start_x, e.start_y)
                                      for e in self.sel_field.entries])
                return

        # whole-entry drag
        for f in reversed(self.fields):
            for e in reversed(f.entries):
                x0, y0, x1, y1 = self._entry_bbox(e, f)
                if x0 <= ix <= x1 and y0 <= iy <= y1:
                    self._drag = (ix - e.start_x, iy - e.start_y)
                    nid = self.id_to_node.get(id(e))
                    if nid:
                        self.tree.selection_set(nid)  # triggers config build
                    return
        self._drag = None

    def _on_drag(self, evt):
        ix, iy = self.canvas_to_img(evt.x, evt.y)

        if self._field_drag:
            ox, oy, snapshot = self._field_drag
            dx, dy = ix - ox, iy - oy
            for e, sx, sy in snapshot:
                e.start_x = int(round(sx + dx))
                e.start_y = int(round(sy + dy))
            self.redraw()
            return

        if self._bubble_drag:
            e, q, o, gx, gy = self._bubble_drag
            desired_x, desired_y = ix - gx, iy - gy
            bx, by = base_pos(e, q, o)
            e.overrides[(q, o)] = (int(round(desired_x - bx)),
                                   int(round(desired_y - by)))
            self.redraw()
            return

        if self.sel_entry and self._drag:
            dx, dy = self._drag
            nx, ny = int(ix - dx), int(iy - dy)
            if self.var_sx and self.var_sy:
                self.var_sx.set(str(nx))   # updates model + redraw via trace
                self.var_sy.set(str(ny))
            else:
                self.sel_entry.start_x, self.sel_entry.start_y = nx, ny
                self.redraw()

    def _on_release(self, _evt):
        self._drag = None
        self._bubble_drag = None
        self._field_drag = None

    # ---------- import ----------
    def import_blueprint(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path) as fh:
                data = json.load(fh)
            bp = OMRTemplateBlueprint.model_validate(data)
        except Exception as ex:
            messagebox.showerror("Import error", str(ex))
            return
        self.tname.set(bp.name)
        self.fields = blueprint_to_fields(bp)
        self.sel_field = self.sel_entry = None
        self._sel_bubble = None
        self._clear_config()
        self.refresh_tree()
        if self.image is None:
            # no image loaded; show at 100% so the layout is visible
            self.set_zoom(1.0)

    # ---------- export ----------
    def _dims(self):
        if not self.image:
            messagebox.showwarning("No image", "Load an image first (needed for dimensions).")
            return None
        return self.image.size

    def export_blueprint(self):
        dims = self._dims()
        if not dims:
            return
        try:
            bp = build_blueprint(self.tname.get(), dims[0], dims[1], self.fields)
        except Exception as ex:
            messagebox.showerror("Validation error", str(ex))
            return
        self._save(bp.model_dump_json(indent=2), "blueprint")

    def export_template(self):
        dims = self._dims()
        if not dims:
            return
        try:
            tpl = build_template(self.tname.get(), dims[0], dims[1], self.fields)
        except Exception as ex:
            messagebox.showerror("Validation error", str(ex))
            return
        self._save(tpl.model_dump_json(indent=2), "template")

    def _save(self, text, kind):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=f"{self.tname.get()}_{kind}.json",
            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w") as fh:
            fh.write(text)
        messagebox.showinfo("Saved", f"Wrote {kind} to:\n{path}")


if __name__ == "__main__":
    App().mainloop()
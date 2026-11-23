"""Tkinter entry point for the Beam Designer."""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from beam_calculations import (
    BeamAnalysis,
    BeamModel,
    PointLoad,
    Section,
    UniformLoad,
    analyze_beam,
    available_sections,
    find_lightest_passing_section,
)
from beam_canvas import BeamCanvasView
from beam_export import write_analysis_csv
from beam_io import BeamFileError, load_beam, save_beam
from beam_report import save_calculation_sheet


@dataclass
class CheckCard:
    value: tk.StringVar
    allowable: tk.StringVar
    status: tk.StringVar
    status_label: ttk.Label
    bar: ttk.Progressbar


class LoadEditor:
    def __init__(
        self,
        kind: str,
        frame: ttk.LabelFrame,
        magnitude: tk.StringVar,
        position: Optional[tk.StringVar] = None,
        start: Optional[tk.StringVar] = None,
        end: Optional[tk.StringVar] = None,
    ) -> None:
        self.kind = kind
        self.frame = frame
        self.magnitude = magnitude
        self.position = position
        self.start = start
        self.end = end
        self.position_scale: Optional[ttk.Scale] = None
        self.start_scale: Optional[ttk.Scale] = None
        self.end_scale: Optional[ttk.Scale] = None


class BeamDesignerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Beam Designer")
        self.root.geometry("1380x940")
        self.root.minsize(1000, 760)
        self._configure_styles()
        self.current_file: Optional[str] = None

        self._ready = False
        self._refresh_scheduled = False
        self.point_editors: List[LoadEditor] = []
        self.uniform_editors: List[LoadEditor] = []
        self.support_var = tk.StringVar(value="simple")
        self.span_var = tk.StringVar(value="20")
        self.material_var = tk.StringVar(value="steel")
        self.section_var = tk.StringVar(value="W12x26")
        self.limit_var = tk.StringVar(value="360")
        self.status_var = tk.StringVar(value="")
        self.reactions_var = tk.StringVar(value="")
        self.recommendation_var = tk.StringVar(value="Calculating recommendation…")
        self.check_widgets: Dict[str, CheckCard] = {}
        self.recommended_section: Optional[Section] = None
        self.current_model: Optional[BeamModel] = None
        self.current_analysis: Optional[BeamAnalysis] = None

        self._build_header()
        self._build_body()
        self._build_menu()
        self._add_load_editor("point", magnitude="0", position="10")
        self._add_load_editor("uniform", magnitude="1", start="0", end="20")
        self._ready = True
        self._refresh()

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Open…", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save_file, accelerator="Ctrl+S")
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menu_bar)
        self.root.bind_all("<Control-o>", lambda _event: self._open_file())
        self.root.bind_all("<Control-s>", lambda _event: self._save_file())
        self.root.bind_all("<Command-o>", lambda _event: self._open_file())
        self.root.bind_all("<Command-s>", lambda _event: self._save_file())

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("TkDefaultFont", 10))
        style.configure("App.TFrame", background="#f3f6f9")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Heading.TLabel", font=("TkDefaultFont", 15, "bold"))
        style.configure("Subheading.TLabel", font=("TkDefaultFont", 10, "bold"))
        style.configure("Muted.TLabel", foreground="#65738a")
        style.configure("Error.TLabel", foreground="#b42318")
        style.configure("Pass.TLabel", foreground="#067647", font=("TkDefaultFont", 10, "bold"))
        style.configure("Fail.TLabel", foreground="#b42318", font=("TkDefaultFont", 10, "bold"))
        style.configure("Good.Horizontal.TProgressbar", troughcolor="#e8eef3", background="#16865b")
        style.configure("Warn.Horizontal.TProgressbar", troughcolor="#e8eef3", background="#c88616")
        style.configure("Bad.Horizontal.TProgressbar", troughcolor="#e8eef3", background="#c43d3d")

    def _build_header(self) -> None:
        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Beam Designer", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Analyze reactions, shear, moment, deflection, and preliminary section checks.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 0))

    def _build_body(self) -> None:
        self.panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.panes.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.left_outer = ttk.Frame(self.panes, width=350)
        self.right = ttk.Frame(self.panes, padding=(12, 4))
        self.panes.add(self.left_outer, weight=0)
        self.panes.add(self.right, weight=1)

        self._build_scrollable_controls()
        self._build_results()

    def _build_scrollable_controls(self) -> None:
        scroll_canvas = tk.Canvas(
            self.left_outer, width=340, background="#f3f6f9", highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            self.left_outer, orient="vertical", command=scroll_canvas.yview
        )
        self.control_frame = ttk.Frame(scroll_canvas, padding=(2, 0, 10, 4))
        self.control_window = scroll_canvas.create_window(
            (0, 0), window=self.control_frame, anchor="nw"
        )
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self.control_frame.bind(
            "<Configure>",
            lambda _event: scroll_canvas.configure(
                scrollregion=scroll_canvas.bbox("all")
            ),
        )
        scroll_canvas.bind(
            "<Configure>",
            lambda event: scroll_canvas.itemconfigure(
                self.control_window, width=event.width
            ),
        )
        scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.bind_all("<MouseWheel>", lambda event: self._scroll_controls(event, scroll_canvas))

        beam_box = ttk.LabelFrame(self.control_frame, text="Beam", padding=10)
        beam_box.pack(fill="x", pady=(0, 8))
        support_row = ttk.Frame(beam_box)
        support_row.pack(fill="x", pady=(0, 8))
        ttk.Label(support_row, text="Support type").pack(anchor="w")
        radio_row = ttk.Frame(support_row)
        radio_row.pack(fill="x", pady=(3, 0))
        ttk.Radiobutton(
            radio_row, text="Simply supported", variable=self.support_var,
            value="simple", command=self._schedule_refresh,
        ).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(
            radio_row, text="Cantilever", variable=self.support_var,
            value="cantilever", command=self._schedule_refresh,
        ).pack(side="left")
        self._add_slider(
            beam_box, "Span (ft)", self.span_var, 4, 40,
            value_width=7, step=1,
        )
        self.span_var.trace_add("write", lambda *_args: self._update_load_bounds())

        self.loads_box = ttk.LabelFrame(self.control_frame, text="Loads", padding=10)
        self.loads_box.pack(fill="x", pady=(0, 8))
        self.load_cards = ttk.Frame(self.loads_box)
        self.load_cards.pack(fill="x")
        add_buttons = ttk.Frame(self.loads_box)
        add_buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(
            add_buttons, text="+ Point load",
            command=lambda: self._add_load_editor("point"),
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(
            add_buttons, text="+ Uniform load",
            command=lambda: self._add_load_editor("uniform"),
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        selection_box = ttk.LabelFrame(
            self.control_frame, text="Material & section", padding=10
        )
        selection_box.pack(fill="x", pady=(0, 8))
        ttk.Label(selection_box, text="Material").pack(anchor="w")
        material_row = ttk.Frame(selection_box)
        material_row.pack(fill="x", pady=(3, 8))
        ttk.Radiobutton(
            material_row, text="Steel", value="steel",
            variable=self.material_var, command=self._material_changed,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            material_row, text="Douglas Fir-Larch No. 2", value="lumber",
            variable=self.material_var, command=self._material_changed,
        ).pack(side="left")
        self.sections_frame = ttk.Frame(selection_box)
        self.sections_frame.pack(fill="x")
        self._render_section_choices()

        limit_box = ttk.LabelFrame(
            self.control_frame, text="Deflection limit", padding=10
        )
        limit_box.pack(fill="x", pady=(0, 8))
        ttk.Radiobutton(
            limit_box, text="L/240", value="240",
            variable=self.limit_var, command=self._schedule_refresh,
        ).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(
            limit_box, text="L/360", value="360",
            variable=self.limit_var, command=self._schedule_refresh,
        ).pack(side="left")

        self.status_label = ttk.Label(
            self.control_frame, textvariable=self.status_var, style="Error.TLabel",
            wraplength=310, justify="left",
        )
        self.status_label.pack(fill="x", pady=(2, 8))
        ttk.Label(
            self.control_frame,
            text="Simplified preliminary checks only; see scope limitations in the project spec.",
            style="Muted.TLabel", wraplength=310, justify="left",
        ).pack(fill="x", pady=(0, 6))

    @staticmethod
    def _scroll_controls(event: tk.Event, canvas: tk.Canvas) -> None:
        direction = -1 if event.delta > 0 else 1
        canvas.yview_scroll(direction, "units")

    def _add_slider(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
        minimum: float,
        maximum: float,
        value_width: int = 8,
        step: float = 1,
    ) -> ttk.Scale:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(5, 0))
        ttk.Label(row, text=label).grid(row=0, column=0, columnspan=2, sticky="w")
        scale = ttk.Scale(
            row, from_=minimum, to=maximum, orient="horizontal",
            command=lambda value: self._slider_changed(variable, value, step),
        )
        scale.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        entry = ttk.Entry(row, textvariable=variable, width=value_width)
        entry.grid(row=1, column=1, sticky="e")
        row.columnconfigure(0, weight=1)
        variable.trace_add(
            "write",
            lambda *_args: self._sync_scale(scale, variable, minimum),
        )
        variable.trace_add("write", lambda *_args: self._schedule_refresh())
        self._sync_scale(scale, variable, minimum)
        return scale

    @staticmethod
    def _slider_changed(variable: tk.StringVar, value: str, step: float) -> None:
        number = float(value)
        if step:
            number = round(number / step) * step
        variable.set(_format_number(number))

    @staticmethod
    def _sync_scale(
        scale: ttk.Scale,
        variable: tk.StringVar,
        minimum: float,
    ) -> None:
        try:
            number = float(variable.get())
            if math.isfinite(number):
                maximum = float(scale.cget("to"))
                scale.set(min(maximum, max(minimum, number)))
        except ValueError:
            return

    def _update_load_bounds(self) -> None:
        try:
            span = self._read_float(self.span_var, "Span")
        except ValueError:
            return
        if not 4 <= span <= 40:
            return

        for editor in self.point_editors + self.uniform_editors:
            controls = (
                ((editor.position, editor.position_scale),)
                if editor.kind == "point"
                else (
                    (editor.start, editor.start_scale),
                    (editor.end, editor.end_scale),
                )
            )
            for variable, scale in controls:
                if variable is None or scale is None:
                    continue
                scale.configure(to=span)
                try:
                    position = float(variable.get())
                except ValueError:
                    continue
                if math.isfinite(position) and position > span:
                    variable.set(_format_number(span))

    def _add_load_editor(
        self,
        kind: str,
        magnitude: str = "0",
        position: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> None:
        editors = self.point_editors if kind == "point" else self.uniform_editors
        try:
            span = self._read_float(self.span_var, "Span")
            if not 4 <= span <= 40:
                raise ValueError("Span must be a finite value between 4 and 40 ft.")
        except ValueError as error:
            self.status_var.set(str(error))
            return

        if position is None and kind == "point":
            position = str(span if self.support_var.get() == "cantilever" else span / 2)
        if kind == "uniform":
            if start is None:
                start = "0"
            if end is None:
                end = _format_number(span)

        index = len(editors) + 1
        frame = ttk.LabelFrame(
            self.load_cards,
            text=f"{'Point' if kind == 'point' else 'Uniform'} load {index}",
            padding=8,
        )
        frame.pack(fill="x", pady=(0, 6))
        variable = tk.StringVar(value=magnitude)
        magnitude_row = ttk.Frame(frame)
        magnitude_row.pack(fill="x")
        magnitude_units = "kip" if kind == "point" else "kip/ft"
        ttk.Label(magnitude_row, text=f"Magnitude ({magnitude_units})").pack(side="left")
        ttk.Entry(magnitude_row, textvariable=variable, width=10).pack(side="right")
        variable.trace_add("write", lambda *_args: self._schedule_refresh())

        editor = LoadEditor(kind, frame, variable)
        if kind == "point":
            editor.position = tk.StringVar(value=position or "10")
            editor.position_scale = self._add_slider(
                frame, "Position (ft)", editor.position, 0, span, value_width=7, step=1
            )
        else:
            editor.start = tk.StringVar(value=start or "0")
            editor.end = tk.StringVar(value=end or _format_number(span))
            editor.start_scale = self._add_slider(
                frame, "Start (ft)", editor.start, 0, span, value_width=7, step=1
            )
            editor.end_scale = self._add_slider(
                frame, "End (ft)", editor.end, 0, span, value_width=7, step=1
            )

        remove_button = ttk.Button(
            frame, text="Remove load", command=lambda current=editor: self._remove_load(current)
        )
        remove_button.pack(anchor="e", pady=(5, 0))
        editors.append(editor)
        self._schedule_refresh()

    def _remove_load(self, editor: LoadEditor) -> None:
        editors = self.point_editors if editor.kind == "point" else self.uniform_editors
        editors.remove(editor)
        editor.frame.destroy()
        self._renumber_loads()
        self._schedule_refresh()

    def _renumber_loads(self) -> None:
        for kind, editors in (
            ("Point", self.point_editors),
            ("Uniform", self.uniform_editors),
        ):
            for index, editor in enumerate(editors, start=1):
                editor.frame.configure(text=f"{kind} load {index}")

    def _render_section_choices(self) -> None:
        for widget in self.sections_frame.winfo_children():
            widget.destroy()
        for section in available_sections(self.material_var.get()):
            details = f"Ix {section.ix:g} in⁴ · Sx {section.sx:g} in³"
            if section.weight is not None:
                details += f" · {section.weight:g} lb/ft"
            ttk.Radiobutton(
                self.sections_frame,
                text=f"{section.name}  ({details})",
                value=section.name,
                variable=self.section_var,
                command=self._schedule_refresh,
            ).pack(anchor="w", pady=1)

    def _material_changed(self) -> None:
        sections = available_sections(self.material_var.get())
        if self.section_var.get() not in {section.name for section in sections}:
            self.section_var.set(sections[0].name)
        self._render_section_choices()
        self._schedule_refresh()

    def _build_results(self) -> None:
        top = ttk.Frame(self.right)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Analysis results", style="Heading.TLabel").pack(side="left")
        self.reactions_label = ttk.Label(
            top, textvariable=self.reactions_var, style="Muted.TLabel"
        )
        self.reactions_label.pack(side="right")
        self.export_button = ttk.Button(
            top, text="Export CSV", command=self._export_csv, state="disabled"
        )
        self.export_button.pack(side="right", padx=(0, 10))
        self.report_button = ttk.Button(
            top, text="Calculation Sheet PDF", command=self._export_pdf, state="disabled"
        )
        self.report_button.pack(side="right", padx=(0, 10))

        self.canvas_view = BeamCanvasView(self.right)
        self.canvas_view.frame.pack(fill="both", expand=True)

        cards = ttk.Frame(self.right)
        cards.pack(fill="x", pady=(6, 8))
        self.check_widgets["bending"] = self._make_check_card(
            cards, "Bending", "fb = |Mmax| × 12 / Sx"
        )
        self.check_widgets["deflection"] = self._make_check_card(
            cards, "Deflection", "|ymax| ≤ L / limit"
        )

        recommendation = ttk.Frame(self.right, padding=(10, 8))
        recommendation.pack(fill="x")
        self.recommendation_label = ttk.Label(
            recommendation, textvariable=self.recommendation_var,
            style="Subheading.TLabel",
        )
        self.recommendation_label.pack(side="left", fill="x", expand=True)
        self.use_section_button = ttk.Button(
            recommendation, text="Use section", command=self._use_recommendation,
            state="disabled",
        )
        self.use_section_button.pack(side="right")

    def _make_check_card(
        self, parent: ttk.Frame, title: str, tooltip: str
    ) -> CheckCard:
        card = ttk.LabelFrame(parent, text=title, padding=8)
        card.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._attach_tooltip(card, tooltip)
        value_var = tk.StringVar(value="—")
        allowable_var = tk.StringVar(value="—")
        status_var = tk.StringVar(value="—")
        ttk.Label(card, textvariable=value_var, style="Subheading.TLabel").pack(anchor="w")
        values_row = ttk.Frame(card)
        values_row.pack(fill="x", pady=(2, 5))
        ttk.Label(values_row, text="Allowable:", style="Muted.TLabel").pack(side="left")
        ttk.Label(values_row, textvariable=allowable_var, style="Muted.TLabel").pack(
            side="left", padx=(4, 0)
        )
        status_label = ttk.Label(card, textvariable=status_var, style="Muted.TLabel")
        status_label.pack(anchor="e")
        bar = ttk.Progressbar(card, maximum=100, mode="determinate")
        bar.pack(fill="x", pady=(5, 0))
        for widget in card.winfo_children():
            self._attach_tooltip(widget, tooltip)
        return CheckCard(value_var, allowable_var, status_var, status_label, bar)

    def _attach_tooltip(self, widget: tk.Widget, text: str) -> None:
        tooltip_window: List[Optional[tk.Toplevel]] = [None]

        def show(_event: tk.Event) -> None:
            if tooltip_window[0] is not None:
                return
            window = tk.Toplevel(self.root)
            window.wm_overrideredirect(True)
            window.wm_geometry(f"+{widget.winfo_rootx() + 12}+{widget.winfo_rooty() + 18}")
            ttk.Label(
                window, text=text, padding=6, background="#fff6d8",
                relief="solid",
            ).pack()
            tooltip_window[0] = window

        def hide(_event: tk.Event) -> None:
            if tooltip_window[0] is not None:
                tooltip_window[0].destroy()
                tooltip_window[0] = None

        widget.bind("<Enter>", show, add="+")
        widget.bind("<Leave>", hide, add="+")

    def _schedule_refresh(self) -> None:
        if not self._ready or self._refresh_scheduled:
            return
        self._refresh_scheduled = True
        self.root.after_idle(self._refresh)

    def _refresh(self) -> None:
        self._refresh_scheduled = False
        if not self._ready:
            return
        try:
            model = self._build_model()
            result = analyze_beam(model)
            recommendation = find_lightest_passing_section(model)
        except ValueError as error:
            self.status_var.set(str(error))
            self._clear_results()
            return

        self.status_var.set("")
        self.current_model = model
        self.current_analysis = result
        self.export_button.configure(state="normal")
        self.report_button.configure(state="normal")
        self.canvas_view.show(model, result)
        self.reactions_var.set(self._format_reactions(model, result))
        self._update_check_card(
            self.check_widgets["bending"],
            result.bending_stress,
            result.allowable_stress,
            "ksi",
            result.bending_pass,
        )
        self._update_check_card(
            self.check_widgets["deflection"],
            abs(result.max_deflection.value),
            result.deflection_limit,
            "in",
            result.deflection_pass,
        )
        self._set_recommendation(recommendation)

    def _build_model(self) -> BeamModel:
        point_loads = tuple(
            PointLoad(
                self._read_float(editor.magnitude, "Point-load magnitude"),
                self._read_float(editor.position, "Point-load position"),
            )
            for editor in self.point_editors
        )
        uniform_loads = tuple(
            UniformLoad(
                self._read_float(editor.magnitude, "Uniform-load magnitude"),
                self._read_float(editor.start, "Uniform-load start"),
                self._read_float(editor.end, "Uniform-load end"),
            )
            for editor in self.uniform_editors
        )
        return BeamModel(
            support=self.support_var.get(),
            span=self._read_float(self.span_var, "Span"),
            point_loads=point_loads,
            uniform_loads=uniform_loads,
            material=self.material_var.get(),
            section_name=self.section_var.get(),
            deflection_limit=int(self.limit_var.get()),
        )

    @staticmethod
    def _read_float(variable: Optional[tk.StringVar], label: str) -> float:
        if variable is None:
            raise ValueError(f"Enter a value for {label.lower()}.")
        value = variable.get().strip()
        try:
            number = float(value)
        except ValueError as error:
            raise ValueError(f"Enter a numeric value for {label.lower()}.") from error
        if not math.isfinite(number):
            raise ValueError(f"{label} must be finite.")
        return number

    def _update_check_card(
        self,
        card: CheckCard,
        actual: float,
        allowable: float,
        units: str,
        passed: bool,
    ) -> None:
        ratio = actual / allowable if allowable else 0.0
        card.value.set(f"Actual: {actual:.3f} {units}  ({ratio:.0%})")
        card.allowable.set(f"{allowable:.3f} {units}")
        card.status.set("PASS" if passed else "FAIL")
        card.status_label.configure(
            style="Pass.TLabel" if passed else "Fail.TLabel"
        )
        card.bar.configure(
            value=min(100.0, ratio * 100),
            style=(
                "Good.Horizontal.TProgressbar" if ratio < 0.7
                else "Warn.Horizontal.TProgressbar" if ratio <= 1
                else "Bad.Horizontal.TProgressbar"
            ),
        )

    def _clear_results(self) -> None:
        self.current_model = None
        self.current_analysis = None
        self.export_button.configure(state="disabled")
        self.report_button.configure(state="disabled")
        self.canvas_view.clear()
        self.reactions_var.set("")
        self.recommendation_var.set("Results unavailable until the inputs are valid.")
        self.use_section_button.configure(state="disabled", text="Use section")
        for card in self.check_widgets.values():
            card.value.set("—")
            card.allowable.set("—")
            card.status.set("—")
            card.status_label.configure(style="Muted.TLabel")
            card.bar.configure(value=0)

    def _format_reactions(self, model: BeamModel, result: BeamAnalysis) -> str:
        if model.support == "cantilever":
            return (
                f"Left reaction {result.reactions.left:.3f} k"
                f"   ·   Fixed moment {result.reactions.fixed_moment:.3f} kip-ft"
            )
        return (
            f"Reactions: {result.reactions.left:.3f} k left"
            f"   ·   {result.reactions.right:.3f} k right"
        )

    def _set_recommendation(self, section: Optional[Section]) -> None:
        self.recommended_section = section
        if section is None:
            self.recommendation_var.set(
                f"No {self.material_var.get()} section passes both checks."
            )
            self.use_section_button.configure(state="disabled", text="Use section")
        else:
            self.recommendation_var.set(
                f"Lightest passing section: {section.name}"
            )
            self.use_section_button.configure(
                state="normal", text=f"Use {section.name}"
            )

    def _use_recommendation(self) -> None:
        if self.recommended_section is not None:
            self.section_var.set(self.recommended_section.name)
            self._schedule_refresh()

    def _save_file(self) -> None:
        try:
            model = self._build_model()
        except ValueError as error:
            self.status_var.set(str(error))
            return

        path = self.current_file
        if path is None:
            path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Save Beam",
                defaultextension=".json",
                filetypes=(("Beam design JSON", "*.json"), ("All files", "*")),
            )
        if not path:
            return
        try:
            save_beam(model, path)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not save beam", str(error), parent=self.root)
            return
        self._set_current_file(path)

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Open Beam",
            filetypes=(("Beam design JSON", "*.json"), ("All files", "*")),
        )
        if not path:
            return
        try:
            model = load_beam(path)
        except BeamFileError as error:
            messagebox.showerror("Could not open beam", str(error), parent=self.root)
            return
        self._apply_model(model)
        self._set_current_file(path)

    def _apply_model(self, model: BeamModel) -> None:
        self._ready = False
        for editor in self.point_editors + self.uniform_editors:
            editor.frame.destroy()
        self.point_editors.clear()
        self.uniform_editors.clear()

        self.support_var.set(model.support)
        self.span_var.set(_format_number(model.span))
        self.material_var.set(model.material)
        self.section_var.set(model.section_name)
        self.limit_var.set(str(model.deflection_limit))
        self._render_section_choices()
        for load in model.point_loads:
            self._add_load_editor(
                "point",
                magnitude=_format_number(load.magnitude),
                position=_format_number(load.position),
            )
        for load in model.uniform_loads:
            self._add_load_editor(
                "uniform",
                magnitude=_format_number(load.magnitude),
                start=_format_number(load.start),
                end=_format_number(load.end),
            )
        self._ready = True
        self._refresh_scheduled = False
        self._refresh()

    def _set_current_file(self, path: str) -> None:
        self.current_file = path
        self.root.title(f"Beam Designer - {Path(path).name}")

    def _export_csv(self) -> None:
        if self.current_model is None or self.current_analysis is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export Beam Results",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*")),
        )
        if not path:
            return
        try:
            write_analysis_csv(self.current_model, self.current_analysis, path)
        except OSError as error:
            messagebox.showerror("Could not export results", str(error), parent=self.root)
            return
        messagebox.showinfo("Results exported", f"Saved results to {path}", parent=self.root)

    def _export_pdf(self) -> None:
        if self.current_model is None or self.current_analysis is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Calculation Sheet",
            defaultextension=".pdf",
            filetypes=(("PDF files", "*.pdf"), ("All files", "*")),
        )
        if not path:
            return
        try:
            save_calculation_sheet(self.current_model, self.current_analysis, path)
        except OSError as error:
            messagebox.showerror("Could not save calculation sheet", str(error), parent=self.root)
            return
        messagebox.showinfo("Calculation sheet saved", f"Saved PDF to {path}", parent=self.root)


def _format_number(number: float) -> str:
    return str(int(number)) if number.is_integer() else f"{number:g}"


def main() -> None:
    root = tk.Tk()
    BeamDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

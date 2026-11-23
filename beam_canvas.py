"""Canvas-based beam and diagram views for the Tkinter application."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Tuple

from beam_calculations import (
    BeamAnalysis,
    BeamModel,
    CurvePoint,
    moment_at,
    shear_at,
)


INK = "#263247"
MUTED = "#65738a"
ACCENT = "#087f83"
FILL = "#b9e5e3"
GRID = "#dce3eb"


class BeamCanvasView:
    def __init__(self, parent: ttk.Frame) -> None:
        self.frame = ttk.Frame(parent)
        self.model: Optional[BeamModel] = None
        self.analysis: Optional[BeamAnalysis] = None
        self.hover_x: Optional[float] = None
        self._chart_canvases: Dict[str, tk.Canvas] = {}
        self._chart_layouts: Dict[str, Tuple[float, float, float, float]] = {}

        ttk.Label(self.frame, text="Beam & loading", style="Heading.TLabel").pack(
            anchor="w", padx=12, pady=(10, 0)
        )
        self.beam_canvas = tk.Canvas(
            self.frame, height=142, background="white", highlightthickness=0
        )
        self.beam_canvas.pack(fill="x", expand=False, padx=8)

        for key, title, units in (
            ("shear", "Shear", "kips"),
            ("moment", "Moment", "kip-ft"),
            ("deflection", "Deflected shape", "in"),
        ):
            row = ttk.Frame(self.frame)
            row.pack(fill="x", padx=12, pady=(5, 0))
            ttk.Label(row, text=title, style="Subheading.TLabel").pack(
                side="left", anchor="w"
            )
            ttk.Label(row, text=units, style="Muted.TLabel").pack(
                side="right", anchor="e"
            )
            canvas = tk.Canvas(
                self.frame,
                height=112,
                background="white",
                highlightthickness=0,
            )
            canvas.pack(fill="x", expand=True, padx=8)
            canvas.bind("<Configure>", lambda _event, name=key: self._draw_chart(name))
            canvas.bind("<Motion>", self._on_hover)
            canvas.bind("<Leave>", self._on_leave)
            self._chart_canvases[key] = canvas
            self._chart_layouts[key] = (44, 8, 14, 18)

        self.hover_var = tk.StringVar(value="Move over a diagram to inspect values.")
        ttk.Label(
            self.frame, textvariable=self.hover_var, style="Muted.TLabel"
        ).pack(anchor="w", padx=12, pady=(5, 10))
        self.beam_canvas.bind("<Configure>", lambda _event: self._draw_beam())

    def show(self, model: BeamModel, analysis: BeamAnalysis) -> None:
        self.model = model
        self.analysis = analysis
        self._draw_beam()
        for name in self._chart_canvases:
            self._draw_chart(name)
        self._update_hover_text()

    def clear(self) -> None:
        self.model = None
        self.analysis = None
        self.hover_x = None
        self.beam_canvas.delete("all")
        for canvas in self._chart_canvases.values():
            canvas.delete("all")
        self.hover_var.set("Move over a diagram to inspect values.")

    def _draw_beam(self) -> None:
        canvas = self.beam_canvas
        canvas.delete("all")
        if self.model is None or self.analysis is None:
            return

        width = max(canvas.winfo_width(), 360)
        left, right = 54.0, width - 34.0
        y = 62.0
        span = self.model.span

        def x_at(position: float) -> float:
            return left + (right - left) * position / span

        canvas.create_line(left, y, right, y, fill=INK, width=7, capstyle="round")
        if self.model.support == "simple":
            self._draw_triangle(canvas, left, y + 3)
            self._draw_triangle(canvas, right, y + 3)
            canvas.create_oval(
                right - 12, y + 28, right - 4, y + 36, fill="#ffffff", outline=INK
            )
            canvas.create_oval(
                right + 4, y + 28, right + 12, y + 36, fill="#ffffff", outline=INK
            )
        else:
            canvas.create_line(left - 8, y - 25, left - 8, y + 35, fill=INK, width=4)
            for offset in range(-20, 33, 10):
                canvas.create_line(
                    left - 17, y + offset + 8, left - 8, y + offset, fill=MUTED
                )
            self._draw_triangle(canvas, right, y + 3)

        for load in self.model.uniform_loads:
            start, end = sorted((load.start, load.end))
            start = min(span, max(0.0, start))
            end = min(span, max(0.0, end))
            if load.magnitude <= 0 or end <= start:
                continue
            x0, x1 = x_at(start), x_at(end)
            canvas.create_line(x0, y - 34, x1, y - 34, fill=ACCENT, width=2)
            arrow_count = max(2, min(32, int((x1 - x0) / 22) + 1))
            for index in range(arrow_count):
                position = x0 + (x1 - x0) * index / max(1, arrow_count - 1)
                canvas.create_line(
                    position, y - 30, position, y - 5,
                    fill=ACCENT, width=2, arrow=tk.LAST,
                )
            canvas.create_text(
                (x0 + x1) / 2, y - 48, text=f"{load.magnitude:g} kip/ft",
                fill=ACCENT, font=("TkDefaultFont", 9, "bold"),
            )

        for load in self.model.point_loads:
            if load.magnitude <= 0 or not 0 <= load.position <= span:
                continue
            x = x_at(load.position)
            canvas.create_line(
                x, y - 42, x, y - 5, fill="#356ac3", width=2, arrow=tk.LAST
            )
            canvas.create_text(
                x, y - 54, text=f"{load.magnitude:g} k",
                fill="#356ac3", font=("TkDefaultFont", 9, "bold"),
            )

        reaction_y = y + 42
        for x, value in (
            (left, self.analysis.reactions.left),
            (right, self.analysis.reactions.right),
        ):
            if value > 0:
                canvas.create_line(
                    x, reaction_y, x, y + 7, fill="#16865b", width=2, arrow=tk.LAST
                )
                canvas.create_text(
                    x, reaction_y + 10, text=f"{value:.2f} k",
                    fill="#16865b", font=("TkDefaultFont", 9, "bold"),
                )
        if self.model.support == "cantilever":
            canvas.create_text(
                left + 6, y + 41,
                text=f"M = {self.analysis.reactions.fixed_moment:.2f} kip-ft",
                anchor="w", fill="#16865b", font=("TkDefaultFont", 9, "bold"),
            )

        dimension_y = 126
        canvas.create_line(left, dimension_y, right, dimension_y, fill=MUTED)
        canvas.create_line(left, dimension_y - 4, left, dimension_y + 4, fill=MUTED)
        canvas.create_line(right, dimension_y - 4, right, dimension_y + 4, fill=MUTED)
        canvas.create_text(
            (left + right) / 2, dimension_y - 7,
            text=f"{span:g} ft", fill=MUTED, font=("TkDefaultFont", 9),
        )

    @staticmethod
    def _draw_triangle(canvas: tk.Canvas, x: float, y: float) -> None:
        canvas.create_polygon(
            x, y, x - 13, y + 22, x + 13, y + 22,
            fill="#d9e2ec", outline=INK, width=1.5,
        )

    def _draw_chart(self, name: str) -> None:
        canvas = self._chart_canvases[name]
        canvas.delete("all")
        if self.model is None or self.analysis is None:
            return

        width = max(canvas.winfo_width(), 360)
        height = max(canvas.winfo_height(), 84)
        margin_left, margin_top, margin_right, margin_bottom = self._chart_layouts[name]
        x0, x1 = margin_left, width - margin_right
        y0, y1 = margin_top, height - margin_bottom

        if name == "deflection":
            values = [(point.x, point.value) for point in self.analysis.deflection]
            maximum = self.analysis.max_deflection
            color = "#8b78cb"
            positive_down = True
        else:
            values = [
                (point.x, point.shear if name == "shear" else point.moment)
                for point in self.analysis.curve
            ]
            maximum = self.analysis.max_shear if name == "shear" else self.analysis.max_moment
            color = "#3e83cc" if name == "shear" else "#e08a46"
            positive_down = False

        raw = [value for _, value in values] + [0.0]
        low, high = min(raw), max(raw)
        if abs(high - low) < 1e-12:
            low, high = -1.0, 1.0
        else:
            padding = (high - low) * 0.08
            low -= padding
            high += padding

        def x_coord(x: float) -> float:
            return x0 + (x1 - x0) * x / self.model.span

        def y_coord(value: float) -> float:
            ratio = (value - low) / (high - low)
            return y0 + ratio * (y1 - y0) if positive_down else y1 - ratio * (y1 - y0)

        baseline = y_coord(0.0)
        canvas.create_line(x0, baseline, x1, baseline, fill=GRID, width=1)
        canvas.create_line(x0, y0, x0, y1, fill=GRID, width=1)
        if values:
            coordinates = []
            for x, value in values:
                coordinates.extend((x_coord(x), y_coord(value)))
            polygon = coordinates + [x_coord(values[-1][0]), baseline, x_coord(values[0][0]), baseline]
            canvas.create_polygon(
                *polygon, fill=color, stipple="gray25", outline="", smooth=False
            )
            canvas.create_line(*coordinates, fill=color, width=2, smooth=False)

        canvas.create_text(
            x0, height - 4, text="0 ft", anchor="sw",
            fill=MUTED, font=("TkDefaultFont", 8),
        )
        canvas.create_text(
            x1, height - 4, text=f"{self.model.span:g} ft", anchor="se",
            fill=MUTED, font=("TkDefaultFont", 8),
        )
        max_x, max_y = x_coord(maximum.x), y_coord(maximum.value)
        canvas.create_oval(
            max_x - 3, max_y - 3, max_x + 3, max_y + 3,
            fill=color, outline="white",
        )
        canvas.create_text(
            min(max_x + 7, x1 - 4), max(y0 + 8, max_y - 9),
            text=f"{maximum.value:.3f} at {maximum.x:.2f} ft",
            anchor="nw", fill=INK, font=("TkDefaultFont", 8, "bold"),
        )

        if self.hover_x is not None:
            hover = x_coord(self.hover_x)
            canvas.create_line(hover, y0, hover, y1, fill=INK, dash=(3, 3))

    def _on_hover(self, event: tk.Event) -> None:
        if self.model is None:
            return
        canvas = event.widget
        width = max(canvas.winfo_width(), 360)
        x0 = self._chart_layouts["shear"][0]
        x1 = width - self._chart_layouts["shear"][2]
        fraction = min(1.0, max(0.0, (event.x - x0) / max(1.0, x1 - x0)))
        self.hover_x = fraction * self.model.span
        for name in self._chart_canvases:
            self._draw_chart(name)
        self._update_hover_text()

    def _on_leave(self, _event: tk.Event) -> None:
        self.hover_x = None
        for name in self._chart_canvases:
            self._draw_chart(name)
        self.hover_var.set("Move over a diagram to inspect values.")

    def _update_hover_text(self) -> None:
        if self.model is None or self.analysis is None or self.hover_x is None:
            return
        x = self.hover_x
        shear = shear_at(self.model, x, "right")
        moment = moment_at(self.model, x)
        deflection = _interpolate(self.analysis.deflection, x)
        self.hover_var.set(
            f"x = {x:.2f} ft     V = {shear:.3f} k     "
            f"M = {moment:.3f} kip-ft     y = {deflection:.4f} in"
        )


def _interpolate(points: Tuple[CurvePoint, ...], x: float) -> float:
    if not points:
        return 0.0
    if x <= points[0].x:
        return points[0].value
    for left, right in zip(points, points[1:]):
        if left.x <= x <= right.x:
            if right.x == left.x:
                return right.value
            fraction = (x - left.x) / (right.x - left.x)
            return left.value + fraction * (right.value - left.value)
    return points[-1].value

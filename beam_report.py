"""PDF calculation-sheet generation."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from beam_calculations import BeamAnalysis, BeamModel


INK = colors.HexColor("#263247")
ACCENT = colors.HexColor("#087f83")
MUTED = colors.HexColor("#65738a")
GRID = colors.HexColor("#dce3eb")


class BeamDiagram(Flowable):
    def __init__(self, model: BeamModel, analysis: BeamAnalysis, kind: str) -> None:
        super().__init__()
        self.model = model
        self.analysis = analysis
        self.kind = kind
        self.height = 78

    def wrap(self, avail_width: float, avail_height: float) -> Tuple[float, float]:
        self.width = avail_width
        return avail_width, self.height

    def draw(self) -> None:
        if self.kind == "beam":
            self._draw_beam()
        else:
            self._draw_plot()

    def _draw_beam(self) -> None:
        canvas = self.canv
        left, right = 42.0, self.width - 42.0
        beam_y = 40.0
        span = self.model.span

        def x_at(x: float) -> float:
            return left + (right - left) * x / span

        canvas.setStrokeColor(INK)
        canvas.setLineWidth(4)
        canvas.line(left, beam_y, right, beam_y)
        canvas.setLineWidth(1)
        if self.model.support == "simple":
            self._triangle(left, beam_y - 2)
            self._triangle(right, beam_y - 2)
            canvas.circle(right - 5, beam_y - 18, 2.5, stroke=1, fill=0)
            canvas.circle(right + 5, beam_y - 18, 2.5, stroke=1, fill=0)
        else:
            canvas.setLineWidth(3)
            canvas.line(left - 8, beam_y - 22, left - 8, beam_y + 22)
            canvas.setLineWidth(1)
            for offset in range(-18, 23, 8):
                canvas.line(left - 15, beam_y + offset - 3, left - 8, beam_y + offset + 3)
            self._triangle(right, beam_y - 2)

        for load in self.model.uniform_loads:
            start, end = sorted((load.start, load.end))
            if load.magnitude <= 0 or end <= start:
                continue
            x0, x1 = x_at(start), x_at(end)
            canvas.setStrokeColor(ACCENT)
            canvas.setFillColor(ACCENT)
            canvas.line(x0, beam_y + 23, x1, beam_y + 23)
            arrow_count = max(2, min(30, int((x1 - x0) / 18) + 1))
            for index in range(arrow_count):
                x = x0 + (x1 - x0) * index / (arrow_count - 1)
                self._arrow(x, beam_y + 20, x, beam_y + 3)
            canvas.setFont("Helvetica", 7)
            canvas.drawCentredString(
                (x0 + x1) / 2, beam_y + 27, f"{load.magnitude:g} kip/ft"
            )

        for load in self.model.point_loads:
            if load.magnitude <= 0:
                continue
            x = x_at(load.position)
            canvas.setStrokeColor(ACCENT)
            canvas.setFillColor(ACCENT)
            self._arrow(x, beam_y + 26, x, beam_y + 3)
            canvas.setFont("Helvetica", 7)
            canvas.drawCentredString(x, beam_y + 30, f"{load.magnitude:g} k")

        canvas.setStrokeColor(colors.HexColor("#16865b"))
        canvas.setFillColor(colors.HexColor("#16865b"))
        reactions = self.analysis.reactions
        self._arrow(left, beam_y - 25, left, beam_y - 4)
        canvas.setFont("Helvetica", 7)
        canvas.drawCentredString(left, beam_y - 34, f"{reactions.left:.2f} k")
        if self.model.support == "simple":
            self._arrow(right, beam_y - 25, right, beam_y - 4)
            canvas.drawCentredString(right, beam_y - 34, f"{reactions.right:.2f} k")
        else:
            canvas.drawString(
                left + 10, beam_y - 33,
                f"Fixed moment {reactions.fixed_moment:.2f} kip-ft",
            )
        canvas.setStrokeColor(MUTED)
        canvas.line(left, 9, right, 9)
        canvas.line(left, 6, left, 12)
        canvas.line(right, 6, right, 12)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString((left + right) / 2, 12, f"{span:g} ft")

    def _draw_plot(self) -> None:
        canvas = self.canv
        left, right = 44.0, self.width - 14.0
        bottom, top = 14.0, self.height - 17.0
        if self.kind == "shear":
            data = [(point.x, point.shear) for point in self.analysis.curve]
            maximum = self.analysis.max_shear
            title, units = "Shear V", "kip"
            fill = colors.HexColor("#3e83cc")
            positive_down = False
        elif self.kind == "moment":
            data = [(point.x, point.moment) for point in self.analysis.curve]
            maximum = self.analysis.max_moment
            title, units = "Moment M", "kip-ft"
            fill = colors.HexColor("#e08a46")
            positive_down = False
        else:
            data = [(point.x, point.value) for point in self.analysis.deflection]
            maximum = self.analysis.max_deflection
            title, units = "Deflection y", "in"
            fill = colors.HexColor("#8b78cb")
            positive_down = True

        values = [value for _, value in data] + [0.0]
        low, high = min(values), max(values)
        if high - low < 1e-12:
            low, high = -1.0, 1.0
        else:
            padding = (high - low) * 0.08
            low -= padding
            high += padding

        def x_at(x: float) -> float:
            return left + (right - left) * x / self.model.span

        def y_at(value: float) -> float:
            ratio = (value - low) / (high - low)
            return bottom + ratio * (top - bottom) if positive_down else top - ratio * (top - bottom)

        base = y_at(0.0)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(2, self.height - 9, f"{title} ({units})")
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.6)
        canvas.line(left, base, right, base)
        canvas.line(left, bottom, left, top)

        if data:
            path = canvas.beginPath()
            path.moveTo(x_at(data[0][0]), y_at(data[0][1]))
            for x, value in data[1:]:
                path.lineTo(x_at(x), y_at(value))
            path.lineTo(x_at(data[-1][0]), base)
            path.lineTo(x_at(data[0][0]), base)
            path.close()
            canvas.setFillColor(colors.Color(fill.red, fill.green, fill.blue, alpha=0.25))
            canvas.setStrokeColor(fill)
            canvas.setLineWidth(1)
            canvas.drawPath(path, stroke=1, fill=1)

        marker_x = x_at(maximum.x)
        marker_y = y_at(maximum.value)
        canvas.setFillColor(fill)
        canvas.circle(marker_x, marker_y, 2.5, stroke=0, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica", 7)
        label = f"{maximum.value:.3f} {units} at {maximum.x:.2f} ft"
        label_x = min(max(marker_x + 5, left + 2), right - 120)
        canvas.drawString(label_x, max(bottom + 2, marker_y + 3), label)
        canvas.setFillColor(MUTED)
        canvas.drawString(left, 2, "0 ft")
        canvas.drawRightString(right, 2, f"{self.model.span:g} ft")

    def _triangle(self, x: float, y: float) -> None:
        path = self.canv.beginPath()
        path.moveTo(x, y)
        path.lineTo(x - 9, y - 14)
        path.lineTo(x + 9, y - 14)
        path.close()
        self.canv.setFillColor(colors.HexColor("#d9e2ec"))
        self.canv.setStrokeColor(INK)
        self.canv.drawPath(path, stroke=1, fill=1)

    def _arrow(self, x0: float, y0: float, x1: float, y1: float) -> None:
        canvas = self.canv
        canvas.line(x0, y0, x1, y1)
        direction = 1 if y1 > y0 else -1
        path = canvas.beginPath()
        path.moveTo(x1, y1)
        path.lineTo(x1 - 2.5, y1 - direction * 4)
        path.lineTo(x1 + 2.5, y1 - direction * 4)
        path.close()
        canvas.drawPath(path, stroke=0, fill=1)


def save_calculation_sheet(
    model: BeamModel, analysis: BeamAnalysis, path: str
) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=19,
        textColor=INK,
        alignment=TA_CENTER,
        spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "ReportSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=ACCENT,
        spaceBefore=4,
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=INK,
    )

    document = SimpleDocTemplate(
        str(Path(path)),
        pagesize=landscape(letter),
        rightMargin=30,
        leftMargin=30,
        topMargin=24,
        bottomMargin=24,
        title="Beam calculation sheet",
    )
    story: List[Flowable] = [
        Paragraph("Beam Calculation Sheet", title_style),
        Paragraph("Inputs", section_style),
    ]
    input_rows = [
        ["Support", "Span", "Material", "Section", "Deflection limit"],
        [
            "Simply supported" if model.support == "simple" else "Cantilever",
            f"{model.span:g} ft",
            "Steel" if model.material == "steel" else "Douglas Fir-Larch No. 2",
            model.section_name,
            f"L/{model.deflection_limit}",
        ],
    ]
    story.append(_styled_table(input_rows, (120, 100, 220, 100, 130)))

    load_rows = [["Load", "Magnitude", "Position / start", "End"]]
    for index, load in enumerate(model.point_loads, start=1):
        load_rows.append(
            [f"Point {index}", f"{load.magnitude:g} kip", f"{load.position:g} ft", "-"]
        )
    for index, load in enumerate(model.uniform_loads, start=1):
        load_rows.append(
            [
                f"Uniform {index}",
                f"{load.magnitude:g} kip/ft",
                f"{load.start:g} ft",
                f"{load.end:g} ft",
            ]
        )
    if len(load_rows) == 1:
        load_rows.append(["No applied loads", "-", "-", "-"])
    story.extend(
        (
            Paragraph("Loads", section_style),
            _styled_table(load_rows, (140, 180, 190, 160), repeat_rows=1),
            Spacer(1, 5),
            Paragraph("Reactions and checks", section_style),
        )
    )
    reactions = analysis.reactions
    reaction_text = (
        f"Left reaction: {reactions.left:.3f} k; "
        f"Fixed-end moment: {reactions.fixed_moment:.3f} kip-ft"
        if model.support == "cantilever"
        else f"Left reaction: {reactions.left:.3f} k; Right reaction: {reactions.right:.3f} k"
    )
    check_rows = [
        ["Reactions", reaction_text, "Section", model.section_name],
        [
            "Bending",
            f"{analysis.bending_stress:.3f} / {analysis.allowable_stress:.3f} ksi",
            "Result",
            "PASS" if analysis.bending_pass else "FAIL",
        ],
        [
            "Deflection",
            f"{abs(analysis.max_deflection.value):.4f} / {analysis.deflection_limit:.4f} in",
            "Result",
            "PASS" if analysis.deflection_pass else "FAIL",
        ],
    ]
    story.extend(
        (
            _styled_table(check_rows, (100, 360, 80, 130)),
            Spacer(1, 5),
            BeamDiagram(model, analysis, "beam"),
            BeamDiagram(model, analysis, "shear"),
            BeamDiagram(model, analysis, "moment"),
            BeamDiagram(model, analysis, "deflection"),
            Spacer(1, 4),
            Paragraph(
                "Preliminary checks only. This sheet does not include self-weight, "
                "shear capacity, lateral-torsional buckling, or load combinations.",
                normal_style,
            ),
        )
    )
    document.build(story)


def _styled_table(
    rows: Sequence[Sequence[str]],
    widths: Sequence[float],
    repeat_rows: int = 0,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9f2f4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table

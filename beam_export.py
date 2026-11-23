"""CSV export for beam analysis results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple

from beam_calculations import BeamAnalysis, BeamModel, BeamPoint, CurvePoint, moment_at, shear_at


CSV_COLUMNS = ("x_ft", "V_kip", "M_kip_ft", "deflection_in")


def write_analysis_csv(model: BeamModel, analysis: BeamAnalysis, path: str) -> None:
    """Write sampled results, preserving both shear values at point-load jumps."""
    beam_points = list(analysis.curve)
    existing_x = {round(point.x, 10) for point in beam_points}
    for point in analysis.deflection:
        if round(point.x, 10) not in existing_x:
            beam_points.append(
                BeamPoint(
                    point.x,
                    shear_at(model, point.x, "right"),
                    moment_at(model, point.x),
                )
            )
            existing_x.add(round(point.x, 10))
    beam_points.sort(key=lambda point: point.x)

    with Path(path).open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_COLUMNS)
        writer.writerows(
            (
                f"{point.x:.6f}",
                f"{point.shear:.6f}",
                f"{point.moment:.6f}",
                f"{_deflection_at(analysis.deflection, point.x):.6f}",
            )
            for point in beam_points
        )


def _deflection_at(points: Tuple[CurvePoint, ...], x: float) -> float:
    if not points:
        return 0.0
    for point in points:
        if abs(point.x - x) <= 1e-10:
            return point.value
    if x <= points[0].x:
        return points[0].value
    for left, right in zip(points, points[1:]):
        if left.x < x < right.x:
            if right.x == left.x:
                return right.value
            fraction = (x - left.x) / (right.x - left.x)
            return left.value + fraction * (right.value - left.value)
    return points[-1].value

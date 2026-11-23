"""Pure beam-analysis calculations for the Beam Designer."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class PointLoad:
    magnitude: float
    position: float


@dataclass(frozen=True)
class UniformLoad:
    magnitude: float
    start: float
    end: float


@dataclass(frozen=True)
class Section:
    name: str
    material: str
    ix: float
    sx: float
    weight: Optional[float] = None


@dataclass(frozen=True)
class BeamModel:
    support: str
    span: float
    point_loads: Tuple[PointLoad, ...] = ()
    uniform_loads: Tuple[UniformLoad, ...] = ()
    material: str = "steel"
    section_name: str = "W12x26"
    deflection_limit: int = 360


@dataclass(frozen=True)
class Reactions:
    left: float
    right: float
    fixed_moment: float


@dataclass(frozen=True)
class BeamPoint:
    x: float
    shear: float
    moment: float


@dataclass(frozen=True)
class CurvePoint:
    x: float
    value: float


@dataclass(frozen=True)
class StationValue:
    value: float
    x: float


@dataclass(frozen=True)
class BeamAnalysis:
    section: Section
    reactions: Reactions
    curve: Tuple[BeamPoint, ...]
    deflection: Tuple[CurvePoint, ...]
    max_shear: StationValue
    max_moment: StationValue
    max_deflection: StationValue
    bending_stress: float
    allowable_stress: float
    deflection_limit: float
    bending_pass: bool
    deflection_pass: bool


STEEL_SECTIONS = (
    Section("W8x10", "steel", 30.8, 7.81, 10),
    Section("W10x12", "steel", 53.8, 10.9, 12),
    Section("W12x26", "steel", 204, 33.4, 26),
    Section("W14x22", "steel", 199, 29.0, 22),
    Section("W16x26", "steel", 301, 38.4, 26),
    Section("W18x35", "steel", 510, 57.6, 35),
    Section("W21x44", "steel", 843, 81.6, 44),
    Section("W24x55", "steel", 1350, 114, 55),
)

LUMBER_SECTIONS = (
    Section("2x8", "lumber", 47.63, 13.14),
    Section("2x10", "lumber", 98.93, 21.39),
    Section("2x12", "lumber", 177.98, 31.64),
)

SECTIONS = {section.name: section for section in STEEL_SECTIONS + LUMBER_SECTIONS}
STEEL_E = 29000.0
LUMBER_E = 1600.0
STEEL_ALLOWABLE_STRESS = 30.0
LUMBER_ALLOWABLE_STRESS = 0.900
MAX_LOAD_MAGNITUDE = 10000.0
CURVE_STEP_FT = 0.05


def available_sections(material: str) -> Tuple[Section, ...]:
    if material == "steel":
        return STEEL_SECTIONS
    if material == "lumber":
        return LUMBER_SECTIONS
    raise ValueError("Material must be steel or lumber.")


def validate_model(model: BeamModel) -> None:
    if model.support not in ("simple", "cantilever"):
        raise ValueError("Support type must be simply supported or cantilever.")
    if not _is_finite(model.span) or not 4 <= model.span <= 40:
        raise ValueError("Span must be a finite value between 4 and 40 ft.")
    if model.material not in ("steel", "lumber"):
        raise ValueError("Material must be steel or lumber.")
    if model.deflection_limit not in (240, 360):
        raise ValueError("Deflection limit must be L/240 or L/360.")

    section = SECTIONS.get(model.section_name)
    if section is None or section.material != model.material:
        raise ValueError("Choose a section from the selected material.")

    for load in model.point_loads:
        if not _is_finite(load.magnitude) or not 0 <= load.magnitude <= MAX_LOAD_MAGNITUDE:
            raise ValueError("Point-load magnitude must be between 0 and 10,000 kip.")
        if not _is_finite(load.position) or not 0 <= load.position <= model.span:
            raise ValueError(
                f"Point-load position must be within the beam span (0 to {model.span:g} ft)."
            )

    for load in model.uniform_loads:
        if not _is_finite(load.magnitude) or not 0 <= load.magnitude <= MAX_LOAD_MAGNITUDE:
            raise ValueError("Uniform-load magnitude must be between 0 and 10,000 kip/ft.")
        if not _is_finite(load.start) or not 0 <= load.start <= model.span:
            raise ValueError(
                f"Uniform-load start must be within the beam span (0 to {model.span:g} ft)."
            )
        if not _is_finite(load.end) or not 0 <= load.end <= model.span:
            raise ValueError(
                f"Uniform-load end must be within the beam span (0 to {model.span:g} ft)."
            )


def calculate_reactions(model: BeamModel) -> Reactions:
    validate_model(model)
    return _calculate_reactions(model, _active_uniform_loads(model))


def _calculate_reactions(
    model: BeamModel, active_uniforms: Tuple[Tuple[float, float, float], ...]
) -> Reactions:
    total_load, moment_about_left = _load_resultants(model, active_uniforms)
    if model.support == "cantilever":
        return Reactions(total_load, 0.0, moment_about_left)
    right = moment_about_left / model.span
    return Reactions(total_load - right, right, 0.0)


def shear_at(model: BeamModel, x: float, side: str = "right") -> float:
    """Return internal shear at x; side selects the value around point-load jumps."""
    validate_model(model)
    _validate_station(model, x, side)
    active_uniforms = _active_uniform_loads(model)
    reactions = _calculate_reactions(model, active_uniforms)
    return _shear_at(model, x, side, reactions, active_uniforms)


def _shear_at(
    model: BeamModel,
    x: float,
    side: str,
    reactions: Reactions,
    active_uniforms: Tuple[Tuple[float, float, float], ...],
) -> float:
    if model.support == "cantilever":
        shear = 0.0
        for load in model.point_loads:
            if _point_is_to_right(load.position, x, side) and load.position <= model.span:
                shear += load.magnitude
        for a, b, magnitude in active_uniforms:
            if b > x:
                shear += magnitude * (b - max(a, x))
        return shear

    value = reactions.left
    for load in model.point_loads:
        if load.position <= model.span and _point_is_at_or_left(load.position, x, side):
            value -= load.magnitude
    for a, b, magnitude in active_uniforms:
        value -= magnitude * max(0.0, min(x, b) - a)
    return value


def moment_at(model: BeamModel, x: float) -> float:
    """Return internal moment in kip-ft at x."""
    validate_model(model)
    _validate_station(model, x, "right")
    active_uniforms = _active_uniform_loads(model)
    reactions = (
        _calculate_reactions(model, active_uniforms)
        if model.support == "simple"
        else Reactions(0.0, 0.0, 0.0)
    )
    return _moment_at(model, x, reactions, active_uniforms)


def _moment_at(
    model: BeamModel,
    x: float,
    reactions: Reactions,
    active_uniforms: Tuple[Tuple[float, float, float], ...],
) -> float:
    if model.support == "cantilever":
        moment = 0.0
        for load in model.point_loads:
            if x < load.position <= model.span:
                moment -= load.magnitude * (load.position - x)
        for a, b, magnitude in active_uniforms:
            if b > x:
                start = max(a, x)
                length = b - start
                moment -= magnitude * length * ((start + b) / 2 - x)
        return moment

    moment = reactions.left * x
    for load in model.point_loads:
        if load.position <= x and load.position <= model.span:
            moment -= load.magnitude * (x - load.position)
    for a, b, magnitude in active_uniforms:
        end = min(x, b)
        if end > a:
            length = end - a
            moment -= magnitude * length * (x - (a + end) / 2)
    return moment


def analyze_beam(model: BeamModel, section: Optional[Section] = None) -> BeamAnalysis:
    validate_model(model)
    if section is None:
        section = SECTIONS[model.section_name]
    if section.material != model.material:
        raise ValueError("Selected section does not match the material.")

    active_uniforms = _active_uniform_loads(model)
    reactions = _calculate_reactions(model, active_uniforms)
    stations = _event_stations(model, active_uniforms)
    x_grid = _sample_grid(stations)
    shear_values = _diagram_shear(model, x_grid, reactions, active_uniforms)
    moment_candidates = _moment_candidates(model, stations, reactions, active_uniforms)
    max_shear = max(shear_values, key=lambda value: abs(value.value))
    max_moment = max(moment_candidates, key=lambda value: abs(value.value))

    deflection = _calculate_deflection(
        model, section, x_grid, reactions, active_uniforms
    )
    max_deflection = max(deflection, key=lambda value: abs(value.value))
    allowable_stress = (
        STEEL_ALLOWABLE_STRESS if model.material == "steel"
        else LUMBER_ALLOWABLE_STRESS
    )
    bending_stress = abs(max_moment.value) * 12 / section.sx
    deflection_limit = model.span * 12 / model.deflection_limit
    curve = tuple(
        BeamPoint(
            x,
            _shear_at(model, x, side, reactions, active_uniforms),
            _moment_at(model, x, reactions, active_uniforms),
        )
        for x, side in _curve_stations(model, x_grid)
    )

    return BeamAnalysis(
        section=section,
        reactions=reactions,
        curve=curve,
        deflection=deflection,
        max_shear=max_shear,
        max_moment=max_moment,
        max_deflection=max_deflection,
        bending_stress=bending_stress,
        allowable_stress=allowable_stress,
        deflection_limit=deflection_limit,
        bending_pass=bending_stress <= allowable_stress,
        deflection_pass=abs(max_deflection.value) <= deflection_limit,
    )


def find_lightest_passing_section(model: BeamModel) -> Optional[Section]:
    validate_model(model)
    passing = []
    for section in available_sections(model.material):
        result = analyze_beam(model, section)
        if result.bending_pass and result.deflection_pass:
            passing.append(section)

    if model.material == "lumber":
        return passing[0] if passing else None
    return min(
        passing,
        key=lambda section: (section.weight, -section.ix),
        default=None,
    )


def _is_finite(value: float) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _validate_station(model: BeamModel, x: float, side: str) -> None:
    if not _is_finite(x) or not 0 <= x <= model.span:
        raise ValueError("Analysis station must be within the beam span.")
    if side not in ("left", "right"):
        raise ValueError("Station side must be left or right.")


def _load_resultants(
    model: BeamModel, active_uniforms: Tuple[Tuple[float, float, float], ...]
) -> Tuple[float, float]:
    total = 0.0
    moment = 0.0
    for load in model.point_loads:
        if 0 <= load.position <= model.span:
            total += load.magnitude
            moment += load.magnitude * load.position
    for start, end, magnitude in active_uniforms:
        force = magnitude * (end - start)
        total += force
        moment += force * (start + end) / 2
    return total, moment


def _active_uniform_loads(model: BeamModel) -> Tuple[Tuple[float, float, float], ...]:
    active = []
    for load in model.uniform_loads:
        start, end = sorted((load.start, load.end))
        if end > start and load.magnitude > 0:
            active.append((start, end, load.magnitude))
    return tuple(active)


def _point_is_at_or_left(position: float, x: float, side: str) -> bool:
    return position < x or (side == "right" and position == x)


def _point_is_to_right(position: float, x: float, side: str) -> bool:
    return position > x or (side == "left" and position == x)


def _event_stations(
    model: BeamModel,
    active_uniforms: Optional[Tuple[Tuple[float, float, float], ...]] = None,
) -> Tuple[float, ...]:
    stations = {0.0, float(model.span)}
    for load in model.point_loads:
        if 0 <= load.position <= model.span:
            stations.add(float(load.position))
    if active_uniforms is None:
        active_uniforms = _active_uniform_loads(model)
    for start, end, _ in active_uniforms:
        stations.update((start, end))
    return tuple(sorted(stations))


def _sample_grid(stations: Tuple[float, ...]) -> Tuple[float, ...]:
    grid = [stations[0]]
    for start, end in zip(stations, stations[1:]):
        count = max(1, int(math.ceil((end - start) / CURVE_STEP_FT)))
        grid.extend(start + (end - start) * index / count for index in range(1, count + 1))
    return tuple(grid)


def _diagram_shear(
    model: BeamModel,
    x_grid: Tuple[float, ...],
    reactions: Reactions,
    active_uniforms: Tuple[Tuple[float, float, float], ...],
) -> Tuple[StationValue, ...]:
    values = []
    point_positions = {
        load.position for load in model.point_loads
        if 0 < load.position < model.span
    }
    for x in x_grid:
        if x == 0:
            values.append(StationValue(_shear_at(model, x, "right", reactions, active_uniforms), x))
        elif x == model.span:
            values.append(StationValue(_shear_at(model, x, "left", reactions, active_uniforms), x))
        elif x in point_positions:
            values.append(StationValue(_shear_at(model, x, "left", reactions, active_uniforms), x))
            values.append(StationValue(_shear_at(model, x, "right", reactions, active_uniforms), x))
        else:
            values.append(StationValue(_shear_at(model, x, "right", reactions, active_uniforms), x))

    for x in _event_stations(model, active_uniforms):
        if x == 0:
            values.append(StationValue(_shear_at(model, x, "right", reactions, active_uniforms), x))
        elif x == model.span:
            values.append(StationValue(_shear_at(model, x, "left", reactions, active_uniforms), x))
        elif x not in point_positions:
            values.append(StationValue(_shear_at(model, x, "left", reactions, active_uniforms), x))
            values.append(StationValue(_shear_at(model, x, "right", reactions, active_uniforms), x))
    return tuple(values)


def _curve_stations(
    model: BeamModel, x_grid: Tuple[float, ...]
) -> Tuple[Tuple[float, str], ...]:
    point_positions = {
        load.position for load in model.point_loads
        if 0 < load.position < model.span
    }
    result = []
    for x in x_grid:
        if x == 0:
            result.append((x, "right"))
        elif x == model.span:
            result.append((x, "left"))
        elif x in point_positions:
            result.extend(((x, "left"), (x, "right")))
        else:
            result.append((x, "right"))
    return tuple(result)


def _moment_candidates(
    model: BeamModel,
    stations: Tuple[float, ...],
    reactions: Reactions,
    active_uniforms: Tuple[Tuple[float, float, float], ...],
) -> Tuple[StationValue, ...]:
    candidates = [
        StationValue(_moment_at(model, x, reactions, active_uniforms), x)
        for x in stations
    ]
    for start, end in zip(stations, stations[1:]):
        shear_start = _shear_at(model, start, "right", reactions, active_uniforms)
        shear_end = _shear_at(model, end, "left", reactions, active_uniforms)
        if shear_start == 0:
            candidates.append(
                StationValue(_moment_at(model, start, reactions, active_uniforms), start)
            )
        elif shear_end == 0:
            candidates.append(
                StationValue(_moment_at(model, end, reactions, active_uniforms), end)
            )
        elif shear_start * shear_end < 0:
            fraction = -shear_start / (shear_end - shear_start)
            x = start + (end - start) * fraction
            candidates.append(
                StationValue(_moment_at(model, x, reactions, active_uniforms), x)
            )
    return tuple(candidates)


def _calculate_deflection(
    model: BeamModel,
    section: Section,
    x_grid: Tuple[float, ...],
    reactions: Reactions,
    active_uniforms: Tuple[Tuple[float, float, float], ...],
) -> Tuple[CurvePoint, ...]:
    elastic_modulus = STEEL_E if model.material == "steel" else LUMBER_E
    ei = elastic_modulus * section.ix
    y = 0.0
    theta = 0.0
    segments = []
    raw_nodes = [(x_grid[0], y)]

    for x0, x1 in zip(x_grid, x_grid[1:]):
        h = (x1 - x0) * 12
        x0_in = x0 * 12
        m0 = _moment_at(model, x0, reactions, active_uniforms) * 12
        mm = _moment_at(model, (x0 + x1) / 2, reactions, active_uniforms) * 12
        m1 = _moment_at(model, x1, reactions, active_uniforms) * 12
        k0, km, k1 = (-m0 / ei, -mm / ei, -m1 / ei)
        linear = (4 * km - 3 * k0 - k1) / h
        quadratic = 2 * (k0 + k1 - 2 * km) / (h * h)
        y0 = y
        theta0 = theta
        y += theta0 * h + h * h * (k0 / 6 + km / 3)
        theta += h * (k0 + 4 * km + k1) / 6
        segments.append((x0_in, h, y0, theta0, k0, linear, quadratic))
        raw_nodes.append((x1, y))

    correction = -y / (model.span * 12) if model.support == "simple" else 0.0
    points = [
        CurvePoint(x, raw_y + correction * x * 12)
        for x, raw_y in raw_nodes
    ]

    for x0_in, h, y0, theta0, k0, linear, quadratic in segments:
        def slope_at(t: float) -> float:
            return (
                theta0 + k0 * t + linear * t * t / 2
                + quadratic * t * t * t / 3 + correction
            )

        def deflection_at(t: float) -> float:
            return (
                y0 + theta0 * t + k0 * t * t / 2
                + linear * t * t * t / 6 + quadratic * t * t * t * t / 12
                + correction * (x0_in + t)
            )

        mid = h / 2
        for left, right in ((0.0, mid), (mid, h)):
            left_slope = slope_at(left)
            right_slope = slope_at(right)
            if left_slope == 0:
                root = left
            elif right_slope == 0:
                root = right
            elif left_slope * right_slope < 0:
                root = _bisect_root(slope_at, left, right)
            else:
                continue
            x = (x0_in + root) / 12
            points.append(CurvePoint(x, deflection_at(root)))

    return tuple(sorted(points, key=lambda point: point.x))


def _bisect_root(function, left: float, right: float) -> float:
    left_value = function(left)
    for _ in range(48):
        middle = (left + right) / 2
        middle_value = function(middle)
        if middle_value == 0:
            return middle
        if left_value * middle_value <= 0:
            right = middle
        else:
            left = middle
            left_value = middle_value
    return (left + right) / 2

"""Versioned JSON persistence for beam models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from beam_calculations import BeamModel, PointLoad, UniformLoad, validate_model


FORMAT_VERSION = 1


class BeamFileError(ValueError):
    """Raised when a saved beam file cannot be read as a valid model."""


def save_beam(model: BeamModel, path: str) -> None:
    validate_model(model)
    data = {
        "format_version": FORMAT_VERSION,
        "support": model.support,
        "span": model.span,
        "material": model.material,
        "section_name": model.section_name,
        "deflection_limit": model.deflection_limit,
        "point_loads": [
            {"magnitude": load.magnitude, "position": load.position}
            for load in model.point_loads
        ],
        "uniform_loads": [
            {"magnitude": load.magnitude, "start": load.start, "end": load.end}
            for load in model.uniform_loads
        ],
    }
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, allow_nan=False)
        file.write("\n")


def load_beam(path: str) -> BeamModel:
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BeamFileError(f"Could not read beam file: {error}") from error

    if not isinstance(data, dict):
        raise BeamFileError("Beam file must contain a JSON object.")
    if type(data.get("format_version")) is not int:
        raise BeamFileError("Beam file has no valid format version.")
    if data["format_version"] != FORMAT_VERSION:
        raise BeamFileError(
            f"Unsupported beam file version: {data['format_version']}."
        )

    support = _required_string(data, "support")
    material = _required_string(data, "material")
    section_name = _required_string(data, "section_name")
    span = _required_number(data, "span")
    deflection_limit = data.get("deflection_limit")
    if type(deflection_limit) is not int:
        raise BeamFileError("Deflection limit must be an integer.")

    point_load_data = _required_list(data, "point_loads")
    uniform_load_data = _required_list(data, "uniform_loads")
    point_loads = tuple(
        PointLoad(
            _load_number(load, "magnitude", f"point_loads[{index}]"),
            _load_number(load, "position", f"point_loads[{index}]"),
        )
        for index, load in enumerate(point_load_data)
    )
    uniform_loads = tuple(
        UniformLoad(
            _load_number(load, "magnitude", f"uniform_loads[{index}]"),
            _load_number(load, "start", f"uniform_loads[{index}]"),
            _load_number(load, "end", f"uniform_loads[{index}]"),
        )
        for index, load in enumerate(uniform_load_data)
    )

    model = BeamModel(
        support=support,
        span=span,
        point_loads=point_loads,
        uniform_loads=uniform_loads,
        material=material,
        section_name=section_name,
        deflection_limit=deflection_limit,
    )
    try:
        validate_model(model)
    except ValueError as error:
        raise BeamFileError(f"Invalid beam file: {error}") from error
    return model


def _required_string(data: Dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise BeamFileError(f"Beam file field '{key}' must be a string.")
    return value


def _required_number(data: Dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BeamFileError(f"Beam file field '{key}' must be numeric.")
    try:
        return float(value)
    except OverflowError as error:
        raise BeamFileError(f"Beam file field '{key}' is out of range.") from error


def _required_list(data: Dict[str, Any], key: str) -> List[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise BeamFileError(f"Beam file field '{key}' must be a list.")
    return value


def _load_number(load: Any, key: str, label: str) -> float:
    if not isinstance(load, dict):
        raise BeamFileError(f"{label} must be a JSON object.")
    value = load.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BeamFileError(f"{label}.{key} must be numeric.")
    try:
        return float(value)
    except OverflowError as error:
        raise BeamFileError(f"{label}.{key} is out of range.") from error

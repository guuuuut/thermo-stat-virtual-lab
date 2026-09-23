"""Strict schema and cross-field validation for the LJ comparison experiment."""

from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from .errors import SpecValidationError, ValidationIssue, json_safe

SCHEMA_VERSION = "1.0"
EXPERIMENT_TYPE = "lj_ensemble_comparison"

ROOT_FIELDS = {
    "schema_version", "experiment_type", "system", "potential",
    "run", "outputs", "comparison",
}
SYSTEM_FIELDS = {
    "units", "dimension", "boundary", "lattice", "cells", "density", "mass",
}
POTENTIAL_FIELDS = {
    "style", "epsilon", "sigma", "cutoff", "shift", "neighbor_skin",
}
RUN_FIELDS = {
    "temperature", "timestep", "seed", "equilibration_steps",
    "production_steps", "thermostat_damping",
}
OUTPUT_FIELDS = {"thermo_interval", "trajectory_interval", "sort_atoms"}
COMPARISON_FIELDS = {"ensembles", "shared_initial_state"}


class Validator:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def add(
        self,
        code: str,
        path: str,
        message: str,
        value: Any,
        expected: str,
        hint: str,
    ) -> None:
        self.issues.append(
            ValidationIssue(code, path, message, json_safe(value), expected, hint)
        )

    def obj(
        self,
        value: Any,
        path: str,
        required: set[str],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.add(
                "TYPE_MISMATCH", path, "Expected a JSON object.", value, "object",
                "Use an object with the documented fields.",
            )
            return None
        for key in sorted(required - set(value)):
            self.add(
                "MISSING_FIELD", f"{path}.{key}", "Required field is missing.", None,
                "field must be present", f"Add '{key}' to {path}.",
            )
        for key in sorted(set(value) - required):
            self.add(
                "UNKNOWN_FIELD", f"{path}.{key}",
                "Unknown fields are not accepted by this schema version.",
                value[key], f"one of {sorted(required)}",
                "Remove the field or migrate to a schema version that defines it.",
            )
        return value

    def enum(
        self,
        obj: Mapping[str, Any] | None,
        key: str,
        path: str,
        allowed: set[Any],
    ) -> Any:
        if obj is None or key not in obj:
            return None
        value = obj[key]
        allowed_types = {type(item) for item in allowed}
        if type(value) not in allowed_types:
            expected_type = "/".join(sorted(item.__name__ for item in allowed_types))
            self.add(
                "TYPE_MISMATCH", path,
                "Value has the wrong JSON type for this enumerated field.", value,
                expected_type,
                "Use the documented JSON type before choosing a supported value.",
            )
            return None
        if value not in allowed:
            self.add(
                "UNSUPPORTED_VALUE", path,
                "Value is not supported by this compiler.", value,
                "one of " + ", ".join(repr(x) for x in sorted(allowed, key=str)),
                "Choose an explicitly supported value; values are case-sensitive.",
            )
            return None
        return value

    def boolean(
        self,
        obj: Mapping[str, Any] | None,
        key: str,
        path: str,
    ) -> bool | None:
        if obj is None or key not in obj:
            return None
        value = obj[key]
        if type(value) is not bool:
            self.add(
                "TYPE_MISMATCH", path, "Expected a JSON boolean.", value,
                "true or false (not 0 or 1)", "Use an unquoted JSON boolean.",
            )
            return None
        return value

    def integer(
        self,
        obj: Mapping[str, Any] | None,
        key: str,
        path: str,
        minimum: int,
        maximum: int,
    ) -> int | None:
        if obj is None or key not in obj:
            return None
        value = obj[key]
        if type(value) is not int:
            self.add(
                "TYPE_MISMATCH", path, "Expected a JSON integer.", value,
                f"integer in [{minimum}, {maximum}]",
                "Do not use a decimal, string, or boolean for this field.",
            )
            return None
        if not minimum <= value <= maximum:
            self.add(
                "OUT_OF_RANGE", path, "Integer lies outside the supported range.",
                value, f"[{minimum}, {maximum}]",
                "Choose a value inside the inclusive range.",
            )
            return None
        return value

    def number(
        self,
        obj: Mapping[str, Any] | None,
        key: str,
        path: str,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if obj is None or key not in obj:
            return None
        value = obj[key]
        if type(value) not in {int, float}:
            self.add(
                "TYPE_MISMATCH", path, "Expected a JSON number.", value,
                f"finite number in [{minimum}, {maximum}]",
                "Use an unquoted number; booleans are not numbers here.",
            )
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            self.add(
                "NOT_FINITE", path, "NaN and infinity are forbidden.", value,
                "finite number", "Provide a finite numeric value.",
            )
            return None
        if not minimum <= numeric <= maximum:
            self.add(
                "OUT_OF_RANGE", path, "Number lies outside the supported range.",
                value, f"[{minimum}, {maximum}]",
                "Choose a value inside the inclusive range.",
            )
            return None
        return numeric


def default_spec() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_type": EXPERIMENT_TYPE,
        "system": {
            "units": "lj",
            "dimension": 3,
            "boundary": ["p", "p", "p"],
            "lattice": "fcc",
            "cells": 4,
            "density": 0.8,
            "mass": 1.0,
        },
        "potential": {
            "style": "lj/cut",
            "epsilon": 1.0,
            "sigma": 1.0,
            "cutoff": 2.5,
            "shift": True,
            "neighbor_skin": 0.3,
        },
        "run": {
            "temperature": 1.2,
            "timestep": 0.005,
            "seed": 20260824,
            "equilibration_steps": 5000,
            "production_steps": 10000,
            "thermostat_damping": 0.5,
        },
        "outputs": {
            "thermo_interval": 100,
            "trajectory_interval": 500,
            "sort_atoms": True,
        },
        "comparison": {
            "ensembles": ["nve", "nvt"],
            "shared_initial_state": True,
        },
    }


def validate_spec(raw: Any) -> dict[str, Any]:
    """Return a defensive copy or raise one aggregate SpecValidationError."""

    v = Validator()
    root = v.obj(raw, "$", ROOT_FIELDS)
    if root is None:
        raise SpecValidationError(v.issues)

    v.enum(root, "schema_version", "$.schema_version", {SCHEMA_VERSION})
    v.enum(root, "experiment_type", "$.experiment_type", {EXPERIMENT_TYPE})

    system = v.obj(root.get("system"), "$.system", SYSTEM_FIELDS) if "system" in root else None
    potential = v.obj(root.get("potential"), "$.potential", POTENTIAL_FIELDS) if "potential" in root else None
    run = v.obj(root.get("run"), "$.run", RUN_FIELDS) if "run" in root else None
    outputs = v.obj(root.get("outputs"), "$.outputs", OUTPUT_FIELDS) if "outputs" in root else None
    comparison = v.obj(root.get("comparison"), "$.comparison", COMPARISON_FIELDS) if "comparison" in root else None

    v.enum(system, "units", "$.system.units", {"lj"})
    v.enum(system, "dimension", "$.system.dimension", {3})
    v.enum(system, "lattice", "$.system.lattice", {"fcc"})
    cells = v.integer(system, "cells", "$.system.cells", 2, 20)
    density = v.number(system, "density", "$.system.density", 0.01, 1.4)
    v.number(system, "mass", "$.system.mass", 0.01, 100.0)

    if system is not None and "boundary" in system:
        boundary = system["boundary"]
        if not isinstance(boundary, list):
            v.add(
                "TYPE_MISMATCH", "$.system.boundary",
                "Boundary must be a three-element JSON array.", boundary,
                '["p", "p", "p"]',
                "This homogeneous-fluid compiler supports only fully periodic boundaries.",
            )
        elif boundary != ["p", "p", "p"]:
            v.add(
                "UNSUPPORTED_BOUNDARY", "$.system.boundary",
                "Only fully periodic boundaries are valid for this ensemble comparison.",
                boundary, '["p", "p", "p"]',
                "Wall/slab experiments require a different experiment type.",
            )

    v.enum(potential, "style", "$.potential.style", {"lj/cut"})
    v.number(potential, "epsilon", "$.potential.epsilon", 0.01, 100.0)
    sigma = v.number(potential, "sigma", "$.potential.sigma", 0.1, 10.0)
    cutoff = v.number(potential, "cutoff", "$.potential.cutoff", 0.15, 50.0)
    v.boolean(potential, "shift", "$.potential.shift")
    skin = v.number(
        potential, "neighbor_skin", "$.potential.neighbor_skin", 0.05, 2.0
    )

    temperature = v.number(run, "temperature", "$.run.temperature", 0.05, 10.0)
    timestep = v.number(run, "timestep", "$.run.timestep", 0.0001, 0.02)
    v.integer(run, "seed", "$.run.seed", 1, 2_147_483_646)
    v.integer(
        run, "equilibration_steps", "$.run.equilibration_steps", 100, 10_000_000
    )
    production_steps = v.integer(
        run, "production_steps", "$.run.production_steps", 100, 10_000_000
    )
    damping = v.number(
        run, "thermostat_damping", "$.run.thermostat_damping", 0.001, 100.0
    )

    thermo_interval = v.integer(
        outputs, "thermo_interval", "$.outputs.thermo_interval", 1, 10_000_000
    )
    trajectory_interval = v.integer(
        outputs, "trajectory_interval", "$.outputs.trajectory_interval", 1, 10_000_000
    )
    v.boolean(outputs, "sort_atoms", "$.outputs.sort_atoms")

    if comparison is not None and "ensembles" in comparison:
        ensembles = comparison["ensembles"]
        if not isinstance(ensembles, list):
            v.add(
                "TYPE_MISMATCH", "$.comparison.ensembles",
                "Ensembles must be a JSON array.", ensembles, '["nve", "nvt"]',
                "Provide both ensemble names exactly once.",
            )
        elif (
            len(ensembles) != 2
            or any(type(item) is not str for item in ensembles)
            or set(ensembles) != {"nve", "nvt"}
        ):
            v.add(
                "INVALID_ENSEMBLE_COMPARISON", "$.comparison.ensembles",
                "This experiment requires exactly one NVE case and one NVT case.",
                ensembles, '["nve", "nvt"] in either order, without duplicates',
                "Add the missing ensemble and remove duplicates or unsupported names.",
            )

    shared = v.boolean(
        comparison, "shared_initial_state", "$.comparison.shared_initial_state"
    )
    if shared is False:
        v.add(
            "COMPARABILITY_REQUIRED", "$.comparison.shared_initial_state",
            "NVE and NVT must use the same deterministic preparation protocol.",
            shared, "true",
            "Set this field to true; independent states are a different study design.",
        )

    if sigma is not None and cutoff is not None:
        lower, upper = 1.5 * sigma, 5.0 * sigma
        if not lower <= cutoff <= upper:
            v.add(
                "CUTOFF_SIGMA_RATIO", "$.potential.cutoff",
                "Cutoff is inconsistent with the Lennard-Jones sigma value.",
                cutoff,
                f"between 1.5*sigma and 5.0*sigma (here [{lower:.6g}, {upper:.6g}])",
                "For the standard truncated LJ model, 2.5*sigma is recommended.",
            )

    if (
        cells is not None
        and density is not None
        and cutoff is not None
        and skin is not None
    ):
        lattice_constant = (4.0 / density) ** (1.0 / 3.0)
        box_length = cells * lattice_constant
        if cutoff + skin > box_length / 2.0:
            v.add(
                "PERIODIC_BOX_TOO_SMALL", "$.system.cells",
                "The neighbor reach exceeds half the periodic box length.",
                {
                    "cells": cells,
                    "density": density,
                    "cutoff": cutoff,
                    "neighbor_skin": skin,
                    "box_length": round(box_length, 8),
                },
                "cutoff + neighbor_skin <= box_length / 2",
                "Increase cells, or reduce cutoff/neighbor_skin.",
            )

    if timestep is not None and damping is not None:
        lower, upper = 10.0 * timestep, 1000.0 * timestep
        if not lower <= damping <= upper:
            v.add(
                "THERMOSTAT_DAMPING_RATIO", "$.run.thermostat_damping",
                "Nose-Hoover damping is inconsistent with the integration timestep.",
                damping,
                f"between 10*timestep and 1000*timestep (here [{lower:.6g}, {upper:.6g}])",
                "A value near 100*timestep is a conventional starting point.",
            )

    if production_steps is not None:
        for path, interval in (
            ("$.outputs.thermo_interval", thermo_interval),
            ("$.outputs.trajectory_interval", trajectory_interval),
        ):
            if interval is None:
                continue
            if interval > production_steps:
                v.add(
                    "INTERVAL_EXCEEDS_RUN", path,
                    "Sampling interval exceeds production length.", interval,
                    f"<= {production_steps}",
                    "Reduce the interval or increase production_steps.",
                )
            elif production_steps % interval != 0:
                v.add(
                    "INTERVAL_NOT_DIVISOR", path,
                    "Production length must be divisible by the sampling interval.",
                    interval, f"a positive divisor of {production_steps}",
                    "Choose an interval that includes an exact final sample.",
                )

    if (
        temperature is not None
        and density is not None
        and temperature < 0.1
        and density > 1.2
    ):
        v.add(
            "HIGH_RISK_STATE_POINT", "$.run.temperature",
            "Very low temperature combined with high density is outside this short-demo reliability envelope.",
            {"temperature": temperature, "density": density},
            "temperature >= 0.1 when density > 1.2",
            "Use a longer specialized solid-state protocol for this state point.",
        )

    if v.issues:
        raise SpecValidationError(v.issues)
    return copy.deepcopy(root)

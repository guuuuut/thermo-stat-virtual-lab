"""Reproducible valid, invalid, and boundary ExperimentSpec samples."""

from __future__ import annotations

import copy
from typing import Any

from experiment_compiler.schema import default_spec


def set_path(obj: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor = obj
    for part in parts[:-1]:
        cursor = cursor[part]
    cursor[parts[-1]] = value


def delete_path(obj: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    cursor = obj
    for part in parts[:-1]:
        cursor = cursor[part]
    del cursor[parts[-1]]


def sample(name: str, valid: bool, expected_codes: list[str], *operations: tuple) -> dict:
    return {
        "name": name,
        "valid": valid,
        "expected_codes": expected_codes,
        "operations": list(operations),
    }


CASES = [
    sample("valid_default", True, []),
    sample("valid_temperature_min", True, [], ("set", "run.temperature", 0.05)),
    sample("valid_temperature_max", True, [], ("set", "run.temperature", 10.0)),
    sample("valid_density_min", True, [], ("set", "system.density", 0.01)),
    sample("valid_density_max", True, [], ("set", "system.density", 1.4)),
    sample("valid_cells_max", True, [], ("set", "system.cells", 20)),
    sample(
        "valid_timestep_min_ratio_edge", True, [],
        ("set", "run.timestep", 0.0001),
        ("set", "run.thermostat_damping", 0.001),
    ),
    sample(
        "valid_timestep_max_ratio_edge", True, [],
        ("set", "run.timestep", 0.02),
        ("set", "run.thermostat_damping", 0.2),
    ),
    sample("valid_seed_min", True, [], ("set", "run.seed", 1)),
    sample("valid_seed_max", True, [], ("set", "run.seed", 2147483646)),
    sample(
        "valid_sampling_at_run_length", True, [],
        ("set", "outputs.thermo_interval", 10000),
        ("set", "outputs.trajectory_interval", 10000),
    ),
    sample(
        "valid_alternate_sampling", True, [],
        ("set", "outputs.thermo_interval", 125),
        ("set", "outputs.trajectory_interval", 1000),
    ),
    sample("valid_reversed_ensembles", True, [], ("set", "comparison.ensembles", ["nvt", "nve"])),
    sample("valid_shift_disabled", True, [], ("set", "potential.shift", False)),
    sample("valid_sort_disabled", True, [], ("set", "outputs.sort_atoms", False)),
    sample("valid_cutoff_ratio_lower", True, [], ("set", "potential.cutoff", 1.5)),
    sample(
        "valid_cutoff_ratio_upper_large_box", True, [],
        ("set", "potential.cutoff", 5.0),
        ("set", "system.cells", 8),
    ),
    sample("invalid_root_type", False, ["TYPE_MISMATCH"], ("root", [])),
    sample("invalid_missing_system", False, ["MISSING_FIELD"], ("delete", "system")),
    sample("invalid_unknown_root_field", False, ["UNKNOWN_FIELD"], ("set", "notes", "free text")),
    sample("invalid_unknown_nested_field", False, ["UNKNOWN_FIELD"], ("set", "run.command", "shell rm")),
    sample("invalid_schema_version", False, ["UNSUPPORTED_VALUE"], ("set", "schema_version", "2.0")),
    sample("invalid_experiment_type", False, ["UNSUPPORTED_VALUE"], ("set", "experiment_type", "free_form")),
    sample("invalid_units", False, ["UNSUPPORTED_VALUE"], ("set", "system.units", "real")),
    sample("invalid_dimension", False, ["UNSUPPORTED_VALUE"], ("set", "system.dimension", 2)),
    sample("invalid_boundary_nonperiodic", False, ["UNSUPPORTED_BOUNDARY"], ("set", "system.boundary", ["p", "p", "f"])),
    sample("invalid_boundary_type", False, ["TYPE_MISMATCH"], ("set", "system.boundary", "p p p")),
    sample("invalid_lattice", False, ["UNSUPPORTED_VALUE"], ("set", "system.lattice", "sc")),
    sample("invalid_cells_boolean", False, ["TYPE_MISMATCH"], ("set", "system.cells", True)),
    sample("invalid_cells_below_min", False, ["OUT_OF_RANGE"], ("set", "system.cells", 1)),
    sample("invalid_small_periodic_box", False, ["PERIODIC_BOX_TOO_SMALL"], ("set", "system.cells", 2)),
    sample("invalid_density_zero", False, ["OUT_OF_RANGE"], ("set", "system.density", 0.0)),
    sample("invalid_density_above_max", False, ["OUT_OF_RANGE"], ("set", "system.density", 1.400001)),
    sample("invalid_mass_string", False, ["TYPE_MISMATCH"], ("set", "system.mass", "1.0")),
    sample("invalid_potential_style", False, ["UNSUPPORTED_VALUE"], ("set", "potential.style", "eam")),
    sample("invalid_sigma_zero", False, ["OUT_OF_RANGE"], ("set", "potential.sigma", 0.0)),
    sample("invalid_cutoff_sigma_ratio", False, ["CUTOFF_SIGMA_RATIO"], ("set", "potential.cutoff", 1.0)),
    sample("invalid_neighbor_skin_negative", False, ["OUT_OF_RANGE"], ("set", "potential.neighbor_skin", -0.1)),
    sample("invalid_temperature_infinite", False, ["NOT_FINITE"], ("set", "run.temperature", float("inf"))),
    sample("invalid_temperature_below_min", False, ["OUT_OF_RANGE"], ("set", "run.temperature", 0.049)),
    sample("invalid_high_risk_state", False, ["HIGH_RISK_STATE_POINT"], ("set", "run.temperature", 0.05), ("set", "system.density", 1.3)),
    sample("invalid_timestep_zero", False, ["OUT_OF_RANGE"], ("set", "run.timestep", 0.0)),
    sample("invalid_seed_zero", False, ["OUT_OF_RANGE"], ("set", "run.seed", 0)),
    sample("invalid_equilibration_too_short", False, ["OUT_OF_RANGE"], ("set", "run.equilibration_steps", 99)),
    sample("invalid_production_too_short", False, ["OUT_OF_RANGE"], ("set", "run.production_steps", 99)),
    sample("invalid_damping_too_small", False, ["THERMOSTAT_DAMPING_RATIO"], ("set", "run.thermostat_damping", 0.01)),
    sample("invalid_damping_too_large", False, ["THERMOSTAT_DAMPING_RATIO"], ("set", "run.thermostat_damping", 6.0)),
    sample("invalid_thermo_interval_zero", False, ["OUT_OF_RANGE"], ("set", "outputs.thermo_interval", 0)),
    sample("invalid_interval_exceeds_run", False, ["INTERVAL_EXCEEDS_RUN"], ("set", "outputs.trajectory_interval", 20000)),
    sample("invalid_interval_not_divisor", False, ["INTERVAL_NOT_DIVISOR"], ("set", "outputs.thermo_interval", 333)),
    sample("invalid_ensembles_type", False, ["TYPE_MISMATCH"], ("set", "comparison.ensembles", "nve,nvt")),
    sample("invalid_ensemble_missing_nvt", False, ["INVALID_ENSEMBLE_COMPARISON"], ("set", "comparison.ensembles", ["nve"])),
    sample("invalid_ensemble_duplicate", False, ["INVALID_ENSEMBLE_COMPARISON"], ("set", "comparison.ensembles", ["nve", "nve"])),
    sample("invalid_shared_state_false", False, ["COMPARABILITY_REQUIRED"], ("set", "comparison.shared_initial_state", False)),
    sample(
        "invalid_multiple_issues", False,
        ["OUT_OF_RANGE", "COMPARABILITY_REQUIRED", "INTERVAL_NOT_DIVISOR"],
        ("set", "run.temperature", -1),
        ("set", "outputs.thermo_interval", 333),
        ("set", "comparison.shared_initial_state", False),
    ),
]


def build_case(case: dict) -> Any:
    spec: Any = copy.deepcopy(default_spec())
    for operation in case["operations"]:
        if operation[0] == "root":
            spec = copy.deepcopy(operation[1])
        elif operation[0] == "set":
            set_path(spec, operation[1], copy.deepcopy(operation[2]))
        elif operation[0] == "delete":
            delete_path(spec, operation[1])
        else:
            raise AssertionError(f"unknown operation: {operation[0]}")
    return spec

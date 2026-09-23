"""Deterministic, allow-listed LAMMPS template compilation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .errors import SpecValidationError, TemplateCompileError, ValidationIssue
from .schema import EXPERIMENT_TYPE, SCHEMA_VERSION, validate_spec

TEMPLATE_NAME = "lj_ensemble.in.tpl"
TOKEN_PATTERN = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
FORBIDDEN_COMMANDS = {"shell", "python", "include", "jump", "quit"}


@dataclass(frozen=True)
class CompilationResult:
    spec: dict[str, Any]
    fingerprint: str
    scripts: dict[str, str]
    manifest: dict[str, Any]


def _format_number(value: int | float) -> str:
    return format(value, ".12g")


def render_template(template: str, values: Mapping[str, str]) -> str:
    """Render only known uppercase tokens and reject mismatch in either direction."""

    required = set(TOKEN_PATTERN.findall(template))
    missing = sorted(required - set(values))
    extra = sorted(set(values) - required)
    if missing or extra:
        raise TemplateCompileError(
            "TEMPLATE_TOKEN_MISMATCH",
            "Template token set does not match compiler values.",
            {"missing_tokens": missing, "unexpected_values": extra},
        )
    rendered = TOKEN_PATTERN.sub(lambda match: values[match.group(1)], template)
    unresolved = sorted(set(re.findall(r"\{\{[^{}]+\}\}", rendered)))
    if unresolved:
        raise TemplateCompileError(
            "UNRESOLVED_TEMPLATE_TOKEN",
            "Rendered script still contains template tokens.",
            {"tokens": unresolved},
        )
    return rendered


def validate_generated_script(script: str, ensemble: str) -> None:
    commands: list[str] = []
    for line_number, raw_line in enumerate(script.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        command = line.split(None, 1)[0].lower()
        commands.append(command)
        if command in FORBIDDEN_COMMANDS:
            raise TemplateCompileError(
                "FORBIDDEN_LAMMPS_COMMAND",
                f"Generated script contains forbidden command '{command}'.",
                {"ensemble": ensemble, "line": line_number, "command": command},
            )

    required = {
        "clear", "units", "dimension", "boundary", "atom_style",
        "pair_style", "run", "write_data",
    }
    missing = sorted(required - set(commands))
    if missing:
        raise TemplateCompileError(
            "INCOMPLETE_LAMMPS_SCRIPT",
            "Generated script is missing required commands.",
            {"ensemble": ensemble, "missing_commands": missing},
        )

    expected = (
        "fix             production all nve"
        if ensemble == "nve"
        else "fix             production all nvt"
    )
    if expected not in script:
        raise TemplateCompileError(
            "ENSEMBLE_FIX_MISMATCH",
            "Generated production integrator does not match the requested ensemble.",
            {"ensemble": ensemble, "expected_fragment": expected},
        )


def compile_experiment(
    raw: Any,
    template_path: str | Path | None = None,
) -> CompilationResult:
    spec = validate_spec(raw)
    canonical = json.dumps(
        spec, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    if template_path is None:
        template_path = (
            Path(__file__).resolve().parents[1]
            / "lammps"
            / "templates"
            / TEMPLATE_NAME
        )
    template = Path(template_path).read_text(encoding="utf-8")

    system = spec["system"]
    potential = spec["potential"]
    run = spec["run"]
    outputs = spec["outputs"]
    scripts: dict[str, str] = {}

    for ensemble in ("nve", "nvt"):
        if ensemble == "nve":
            production_fix = "fix             production all nve"
        else:
            production_fix = (
                "fix             production all nvt temp "
                "${temperature} ${temperature} "
                "${thermostat_damping}"
            )

        values = {
            "SPEC_SHA256": fingerprint,
            "ENSEMBLE_UPPER": ensemble.upper(),
            "UNITS": system["units"],
            "DIMENSION": str(system["dimension"]),
            "BOUNDARY": " ".join(system["boundary"]),
            "LATTICE": system["lattice"],
            "CELLS": str(system["cells"]),
            "DENSITY": _format_number(system["density"]),
            "MASS": _format_number(system["mass"]),
            "PAIR_STYLE": potential["style"],
            "EPSILON": _format_number(potential["epsilon"]),
            "SIGMA": _format_number(potential["sigma"]),
            "CUTOFF": _format_number(potential["cutoff"]),
            "SHIFT": "yes" if potential["shift"] else "no",
            "NEIGHBOR_SKIN": _format_number(potential["neighbor_skin"]),
            "TEMPERATURE": _format_number(run["temperature"]),
            "TIMESTEP": _format_number(run["timestep"]),
            "SEED": str(run["seed"]),
            "EQUILIBRATION_STEPS": str(run["equilibration_steps"]),
            "PRODUCTION_STEPS": str(run["production_steps"]),
            "THERMOSTAT_DAMPING": _format_number(run["thermostat_damping"]),
            "THERMO_INTERVAL": str(outputs["thermo_interval"]),
            "TRAJECTORY_INTERVAL": str(outputs["trajectory_interval"]),
            "SORT_ATOMS": (
                "dump_modify     trajectory sort id"
                if outputs["sort_atoms"]
                else "# atom sorting disabled by spec"
            ),
            "PRODUCTION_FIX": production_fix,
        }
        script = render_template(template, values)
        validate_generated_script(script, ensemble)
        scripts[f"in.lj_{ensemble}"] = script

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "experiment_type": EXPERIMENT_TYPE,
        "spec_sha256": fingerprint,
        "deterministic_preparation": True,
        "scripts": {
            name: {
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "bytes": len(text.encode("utf-8")),
            }
            for name, text in scripts.items()
        },
    }
    return CompilationResult(
        spec=spec,
        fingerprint=fingerprint,
        scripts=scripts,
        manifest=manifest,
    )

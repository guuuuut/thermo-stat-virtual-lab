"""Compile a JSON ExperimentSpec into two deterministic LAMMPS scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiment_compiler import (  # noqa: E402
    SpecValidationError,
    TemplateCompileError,
    compile_experiment,
)


def emit_error(payload: dict, exit_code: int) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate ExperimentSpec JSON and compile safe LAMMPS inputs."
    )
    parser.add_argument("spec", type=Path, help="Path to ExperimentSpec JSON")
    parser.add_argument("--output", type=Path, required=True, help="Output directory")
    args = parser.parse_args()

    try:
        raw = json.loads(args.spec.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return emit_error(
            {"error": {"code": "SPEC_FILE_NOT_FOUND", "message": str(args.spec)}}, 2
        )
    except (OSError, UnicodeError) as exc:
        return emit_error(
            {"error": {"code": "SPEC_FILE_READ_FAILED", "message": str(exc)}}, 2
        )
    except json.JSONDecodeError as exc:
        return emit_error(
            {
                "error": {
                    "code": "INVALID_JSON",
                    "message": exc.msg,
                    "line": exc.lineno,
                    "column": exc.colno,
                }
            },
            2,
        )

    try:
        result = compile_experiment(raw)
    except SpecValidationError as exc:
        return emit_error(exc.to_dict(), 3)
    except TemplateCompileError as exc:
        return emit_error(exc.to_dict(), 4)

    try:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, script in result.scripts.items():
            (args.output / name).write_text(script, encoding="utf-8", newline="\n")
        (args.output / "manifest.json").write_text(
            json.dumps(result.manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        (args.output / "normalized_spec.json").write_text(
            json.dumps(result.spec, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except OSError as exc:
        return emit_error(
            {"error": {"code": "OUTPUT_WRITE_FAILED", "message": str(exc)}}, 5
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output.resolve()),
                "spec_sha256": result.fingerprint,
                "scripts": sorted(result.scripts),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

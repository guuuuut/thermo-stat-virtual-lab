from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAMMPS_INPUT = PROJECT_ROOT / "lammps" / "in.lj_diffusion_pressure"
DEFAULT_LMP = PROJECT_ROOT / ".venv" / "Scripts" / "lmp.exe"
RESULTS_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure_preview"
PRESSURES = (0.10, 0.20, 0.30, 0.40, 0.50)
TEMPERATURE = 2.0
PRODUCTION_STEPS = 20_000
DUMP_INTERVAL = 250
TIMESTEP_SIZE = 0.005


def pressure_slug(pressure: float) -> str:
    return f"p_{pressure:.2f}".replace(".", "p")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate short, finely sampled trajectories for the 3D preview."
    )
    parser.add_argument("--lammps", type=Path, default=DEFAULT_LMP)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.lammps.is_file():
        raise FileNotFoundError(f"LAMMPS executable not found: {args.lammps}")
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)

    manifest = {
        "temperature": TEMPERATURE,
        "pressures": list(PRESSURES),
        "protocol": "NPT equilibration followed by a short fixed-volume NVT preview",
        "timestep_size": TIMESTEP_SIZE,
        "production_steps": PRODUCTION_STEPS,
        "duration_lj": PRODUCTION_STEPS * TIMESTEP_SIZE,
        "dump_interval_steps": DUMP_INTERVAL,
        "frame_interval_lj": DUMP_INTERVAL * TIMESTEP_SIZE,
        "cases": [],
    }
    for index, pressure in enumerate(PRESSURES):
        case_root = RESULTS_ROOT / pressure_slug(pressure)
        case_root.mkdir(parents=True, exist_ok=True)
        required = [
            case_root / "thermo.csv",
            case_root / "msd.csv",
            case_root / "trajectory.lammpstrj",
        ]
        if all(path.is_file() for path in required) and not args.force:
            print(f"Skipping existing P*={pressure:.2f}: {case_root}")
        else:
            seed = 20260922 + index * 1009
            initial_density = pressure / TEMPERATURE
            command = [
                str(args.lammps),
                "-in", str(LAMMPS_INPUT),
                "-log", "log.lammps",
                "-screen", "screen.txt",
                "-var", "temperature", f"{TEMPERATURE:.8g}",
                "-var", "target_pressure", f"{pressure:.8g}",
                "-var", "initial_density", f"{initial_density:.8g}",
                "-var", "seed", str(seed),
                "-var", "prod_steps", str(PRODUCTION_STEPS),
                "-var", "dump_interval", str(DUMP_INTERVAL),
            ]
            print(f"Running preview P*={pressure:.2f} ...", flush=True)
            completed = subprocess.run(command, cwd=case_root, check=False)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"LAMMPS failed for P*={pressure:.2f}; see {case_root / 'screen.txt'}"
                )
        manifest["cases"].append(
            {
                "target_pressure": pressure,
                "directory": case_root.name,
                "initial_density": pressure / TEMPERATURE,
            }
        )

    (RESULTS_ROOT / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Completed {len(PRESSURES)} preview cases in {RESULTS_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

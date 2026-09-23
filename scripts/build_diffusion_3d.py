from __future__ import annotations

import csv
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = PROJECT_ROOT / "results" / "diffusion_3d_reflective"
TEMPLATE_PATH = PROJECT_ROOT / "visualization" / "diffusion_3d_template.html"
OUTPUT_PATH = PROJECT_ROOT / "visualization" / "diffusion_3d.html"

TIMESTEP_SIZE = 0.005
CONCENTRATION_BINS = 20


def parse_thermo(path: Path) -> dict[int, dict[str, float]]:
    with path.open("r", encoding="utf-8") as handle:
        return {
            int(float(row["step"])): {
                "temperature": round(float(row["temp"]), 7),
                "pressure": round(float(row["pressure"]), 7),
            }
            for row in csv.DictReader(handle)
        }


def concentration_metrics(
    atoms: list[list[float | int]], bounds: list[list[float]], bins: int
) -> tuple[float, list[list[float | int]]]:
    x_low, x_high = bounds[0]
    width = x_high - x_low
    counts = [[0, 0] for _ in range(bins)]
    for atom in atoms:
        atom_type = int(atom[1])
        x = float(atom[2])
        index = min(bins - 1, max(0, int((x - x_low) / width * bins)))
        counts[index][atom_type - 1] += 1

    total = sum(a + b for a, b in counts)
    segregation = sum(abs(a - b) for a, b in counts) / total
    mixing_index = 1.0 - segregation
    profile: list[list[float | int]] = []
    for index, (count_a, count_b) in enumerate(counts):
        occupancy = count_a + count_b
        fraction_a = count_a / occupancy if occupancy else 0.5
        profile.append(
            [round((index + 0.5) / bins, 4), round(fraction_a, 5), occupancy]
        )
    return round(mixing_index, 6), profile


def parse_trajectory(
    path: Path, thermo: dict[int, dict[str, float]]
) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    frames: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(lines):
        if lines[cursor] != "ITEM: TIMESTEP":
            cursor += 1
            continue

        step = int(lines[cursor + 1])
        if lines[cursor + 2] != "ITEM: NUMBER OF ATOMS":
            raise ValueError(f"Unexpected atom-count header at line {cursor + 3}")
        atom_count = int(lines[cursor + 3])
        if not lines[cursor + 4].startswith("ITEM: BOX BOUNDS"):
            raise ValueError(f"Unexpected box header at line {cursor + 5}")
        bounds = [
            [round(float(value), 8) for value in lines[cursor + 5 + axis].split()[:2]]
            for axis in range(3)
        ]

        atom_header = lines[cursor + 8].split()[2:]
        required = {"id", "type", "x", "y", "z"}
        if not required.issubset(atom_header):
            raise ValueError(f"Trajectory fields missing: {required - set(atom_header)}")
        indices = {name: atom_header.index(name) for name in required}

        atoms: list[list[float | int]] = []
        for line in lines[cursor + 9 : cursor + 9 + atom_count]:
            fields = line.split()
            atoms.append(
                [
                    int(fields[indices["id"]]),
                    int(fields[indices["type"]]),
                    round(float(fields[indices["x"]]), 5),
                    round(float(fields[indices["y"]]), 5),
                    round(float(fields[indices["z"]]), 5),
                ]
            )
        atoms.sort(key=lambda atom: int(atom[0]))
        mixing_index, profile = concentration_metrics(
            atoms, bounds, CONCENTRATION_BINS
        )
        if step not in thermo:
            raise ValueError(f"No thermo sample at step {step}")
        frames.append(
            {
                "step": step,
                "time": round(step * TIMESTEP_SIZE, 6),
                "atoms": atoms,
                "mixing_index": mixing_index,
                "concentration": profile,
                **thermo[step],
            }
        )
        cursor += 9 + atom_count

    if not frames:
        raise ValueError(f"No trajectory frames found in {path}")
    frames[0]["bounds"] = bounds
    return frames


def argon_time_unit_ps() -> float:
    sigma_m = 3.405e-10
    mass_kg = 39.948 * 1.66053906660e-27
    epsilon_j = 119.8 * 1.380649e-23
    return sigma_m * math.sqrt(mass_kg / epsilon_j) * 1e12


def main() -> None:
    thermo = parse_thermo(RESULT_ROOT / "thermo.csv")
    frames = parse_trajectory(RESULT_ROOT / "trajectory.lammpstrj", thermo)
    payload = {
        "title": "三维气体示踪扩散",
        "timestep_size": TIMESTEP_SIZE,
        "time_unit": "LJ reduced time",
        "boundary": "reflective",
        "argon_time_unit_ps": round(argon_time_unit_ps(), 6),
        "particle_count": len(frames[0]["atoms"]),
        "species_counts": {
            "A": sum(atom[1] == 1 for atom in frames[0]["atoms"]),
            "B": sum(atom[1] == 2 for atom in frames[0]["atoms"]),
        },
        "frames": frames,
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count("__DIFFUSION_DATA__") != 1:
        raise ValueError("Template must contain exactly one data placeholder")
    rendered = template.replace(
        "__DIFFUSION_DATA__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        f"Wrote {OUTPUT_PATH} with {len(frames)} frames, "
        f"{payload['particle_count']} particles, "
        f"t*={frames[0]['time']:.3f}..{frames[-1]['time']:.3f}."
    )


if __name__ == "__main__":
    main()

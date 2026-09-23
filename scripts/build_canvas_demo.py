from __future__ import annotations

import csv
import json
import math
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = PROJECT_ROOT / "results"
TEMPLATE_PATH = PROJECT_ROOT / "visualization" / "canvas_template.html"
OUTPUT_PATH = PROJECT_ROOT / "visualization" / "canvas_animation.html"


def parse_thermo(path: Path) -> dict[int, dict[str, float]]:
    with path.open("r", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {
            int(float(row["step"])): {
                "temp": round(float(row["temp"]), 8),
                "pressure": round(float(row["pressure"]), 8),
                "etotal": round(float(row["etotal"]), 8),
                "atoms": int(float(row["atoms"])),
            }
            for row in rows
        }


def parse_trajectory(path: Path, thermo: dict[int, dict[str, float]]) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    frames: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(lines):
        if lines[cursor] != "ITEM: TIMESTEP":
            cursor += 1
            continue

        step = int(lines[cursor + 1])
        if lines[cursor + 2] != "ITEM: NUMBER OF ATOMS":
            raise ValueError(f"Unexpected atom-count header near line {cursor + 3} in {path}")
        atom_count = int(lines[cursor + 3])
        if not lines[cursor + 4].startswith("ITEM: BOX BOUNDS"):
            raise ValueError(f"Unexpected box header near line {cursor + 5} in {path}")

        bounds = [
            [round(float(value), 8) for value in lines[cursor + 5 + axis].split()[:2]]
            for axis in range(3)
        ]
        atom_header = lines[cursor + 8].split()[2:]
        required = {"id", "x", "y", "z", "vx", "vy", "vz"}
        if not required.issubset(atom_header):
            raise ValueError(f"Trajectory is missing required fields: {required - set(atom_header)}")
        indices = {name: atom_header.index(name) for name in required}

        atoms: list[list[float | int]] = []
        for line in lines[cursor + 9 : cursor + 9 + atom_count]:
            fields = line.split()
            vx = float(fields[indices["vx"]])
            vy = float(fields[indices["vy"]])
            vz = float(fields[indices["vz"]])
            atoms.append(
                [
                    int(fields[indices["id"]]),
                    round(float(fields[indices["x"]]), 6),
                    round(float(fields[indices["y"]]), 6),
                    round(float(fields[indices["z"]]), 6),
                    round(math.sqrt(vx * vx + vy * vy + vz * vz), 6),
                ]
            )
        atoms.sort(key=lambda atom: atom[0])
        if step not in thermo:
            raise ValueError(f"No thermodynamic sample for trajectory step {step} in {path.parent}")
        frames.append({"step": step, "bounds": bounds, "atoms": atoms, "thermo": thermo[step]})
        cursor += 9 + atom_count

    if not frames:
        raise ValueError(f"No trajectory frames found in {path}")
    return frames


def build_case(case_name: str, label: str) -> dict[str, object]:
    case_root = RESULTS_ROOT / case_name
    thermo = parse_thermo(case_root / "thermo.csv")
    frames = parse_trajectory(case_root / "trajectory.lammpstrj", thermo)
    speeds = sorted(float(atom[4]) for frame in frames for atom in frame["atoms"])
    percentile_index = min(len(speeds) - 1, round(0.98 * (len(speeds) - 1)))
    return {
        "label": label,
        "atom_count": len(frames[0]["atoms"]),
        "speed_scale": round(speeds[percentile_index], 6),
        "frames": frames,
    }


def main() -> None:
    payload = {
        "timestep_size": 0.005,
        "cases": {
            "nve": build_case("nve", "NVE"),
            "nvt": build_case("nvt", "NVT"),
        },
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count("__TRAJECTORY_DATA__") != 1:
        raise ValueError("Canvas template must contain exactly one data placeholder")
    rendered = template.replace(
        "__TRAJECTORY_DATA__",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {OUTPUT_PATH} with "
        f"{len(payload['cases']['nve']['frames'])} NVE frames and "
        f"{len(payload['cases']['nvt']['frames'])} NVT frames."
    )


if __name__ == "__main__":
    main()

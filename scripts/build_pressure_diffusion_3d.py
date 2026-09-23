from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure"
TRAJECTORY_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure_preview"
TEMPLATE_PATH = PROJECT_ROOT / "visualization" / "pressure_diffusion_template.html"
OUTPUT_PATH = PROJECT_ROOT / "visualization" / "pressure_diffusion.html"
TIMESTEP_SIZE = 0.005
CONCENTRATION_BINS = 20


def mixing_index(atoms: list[list[float | int]], bounds: list[list[float]]) -> float:
    x_low, x_high = bounds[0]
    width = x_high - x_low
    counts = [[0, 0] for _ in range(CONCENTRATION_BINS)]
    for atom in atoms:
        atom_type = int(atom[0])
        x = float(atom[1])
        index = min(
            CONCENTRATION_BINS - 1,
            max(0, int((x - x_low) / width * CONCENTRATION_BINS)),
        )
        counts[index][atom_type - 1] += 1
    total = sum(a + b for a, b in counts)
    return round(1.0 - sum(abs(a - b) for a, b in counts) / total, 6)


def parse_trajectory(path: Path, time_unit_ps: float) -> list[dict[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    frames: list[dict[str, object]] = []
    cursor = 0
    while cursor < len(lines):
        if lines[cursor] != "ITEM: TIMESTEP":
            cursor += 1
            continue
        step = int(lines[cursor + 1])
        atom_count = int(lines[cursor + 3])
        bounds = [
            [round(float(value), 7) for value in lines[cursor + 5 + axis].split()[:2]]
            for axis in range(3)
        ]
        header = lines[cursor + 8].split()[2:]
        required = {"type", "x", "y", "z"}
        if not required.issubset(header):
            raise ValueError(f"Missing fields in {path}: {required - set(header)}")
        indices = {name: header.index(name) for name in required}
        id_index = header.index("id")
        ordered: list[tuple[int, list[float | int]]] = []
        for line in lines[cursor + 9 : cursor + 9 + atom_count]:
            values = line.split()
            ordered.append(
                (
                    int(values[id_index]),
                    [
                        int(values[indices["type"]]),
                        round(float(values[indices["x"]]), 5),
                        round(float(values[indices["y"]]), 5),
                        round(float(values[indices["z"]]), 5),
                    ],
                )
            )
        ordered.sort(key=lambda item: item[0])
        atoms = [item[1] for item in ordered]
        time_lj = step * TIMESTEP_SIZE
        frame = {
            "step": step,
            "time_lj": round(time_lj, 6),
            "time_ps": round(time_lj * time_unit_ps, 6),
            "mixing_index": mixing_index(atoms, bounds),
            "atoms": atoms,
        }
        if not frames:
            frame["bounds"] = bounds
        frames.append(frame)
        cursor += 9 + atom_count
    if not frames:
        raise ValueError(f"No frames found in {path}")
    return frames


def main() -> None:
    summary = json.loads((ANALYSIS_ROOT / "summary.json").read_text(encoding="utf-8"))
    run_manifest = json.loads(
        (TRAJECTORY_ROOT / "run_manifest.json").read_text(encoding="utf-8")
    )
    directories = {
        float(case["target_pressure"]): case["directory"]
        for case in run_manifest["cases"]
    }
    time_unit_ps = float(summary["argon_mapping"]["time_unit_ps"])
    cases = []
    for result in summary["cases"]:
        target = float(result["target_pressure"])
        frames = parse_trajectory(
            TRAJECTORY_ROOT / directories[target] / "trajectory.lammpstrj",
            time_unit_ps,
        )
        cases.append(
            {
                "key": f"p{target:.2f}".replace(".", "_"),
                "target_pressure": target,
                "mean_pressure": result["mean_pressure"],
                "mean_density": result["mean_density"],
                "mean_temperature": result["mean_temperature"],
                "diffusion_lj": result["diffusion_lj"],
                "diffusion_m2_s": result["diffusion_m2_s_argon"],
                "msd_fit_r2": result["msd_fit_r2"],
                "frames": frames,
            }
        )

    payload = {
        "temperature_lj": summary["temperature_lj"],
        "timestep_size": TIMESTEP_SIZE,
        "time_unit_ps": time_unit_ps,
        "boundary": "periodic",
        "particle_count": len(cases[0]["frames"][0]["atoms"]),
        "inverse_pressure_fit": summary["inverse_pressure_fit"],
        "power_law_fit": summary["power_law_fit"],
        "dp_constancy": summary["dp_constancy"],
        "cases": cases,
    }
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if template.count("__PRESSURE_DIFFUSION_DATA__") != 1:
        raise ValueError("Template must contain exactly one data placeholder")
    OUTPUT_PATH.write_text(
        template.replace(
            "__PRESSURE_DIFFUSION_DATA__",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"Wrote {OUTPUT_PATH} with {len(cases)} pressures, "
        f"{len(cases[0]['frames'])} frames/case and {payload['particle_count']} particles."
    )


if __name__ == "__main__":
    main()

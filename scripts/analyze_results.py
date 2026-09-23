from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
import numpy as np

# The Demo is a batch job and must not depend on a desktop/Tk installation.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_thermo(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No thermodynamic samples in {path}")
    columns = rows[0].keys()
    data = {name: np.asarray([float(row[name]) for row in rows]) for name in columns}
    if not all(np.all(np.isfinite(values)) for values in data.values()):
        raise ValueError(f"Non-finite value found in {path}")
    return data


def read_last_velocities(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="utf-8").splitlines()
    frame_starts = [i for i, line in enumerate(lines) if line == "ITEM: ATOMS id type x y z vx vy vz"]
    if not frame_starts:
        raise ValueError(f"No velocity frames in {path}")
    start = frame_starts[-1] + 1
    velocities: list[tuple[float, float, float]] = []
    for line in lines[start:]:
        if line.startswith("ITEM:"):
            break
        fields = line.split()
        velocities.append((float(fields[5]), float(fields[6]), float(fields[7])))
    return np.asarray(velocities)


def summarize_case(data: dict[str, np.ndarray]) -> dict[str, float | int]:
    atoms = int(round(data["atoms"][0]))
    etotal_per_atom = data["etotal"] / atoms
    denominator = max(abs(float(np.mean(etotal_per_atom))), 1.0e-12)
    return {
        "samples": int(data["step"].size),
        "atoms": atoms,
        "mean_temperature": float(np.mean(data["temp"])),
        "std_temperature": float(np.std(data["temp"], ddof=1)),
        "mean_pressure": float(np.mean(data["pressure"])),
        "std_pressure": float(np.std(data["pressure"], ddof=1)),
        "mean_etotal_per_atom": float(np.mean(etotal_per_atom)),
        "std_etotal_per_atom": float(np.std(etotal_per_atom, ddof=1)),
        "relative_endpoint_energy_drift": float(abs(etotal_per_atom[-1] - etotal_per_atom[0]) / denominator),
    }


def maxwell_speed(speed: np.ndarray, temperature: float) -> np.ndarray:
    prefactor = 4.0 * math.pi * (1.0 / (2.0 * math.pi * temperature)) ** 1.5
    return prefactor * speed**2 * np.exp(-(speed**2) / (2.0 * temperature))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--target-temperature", type=float, required=True)
    args = parser.parse_args()

    cases = {
        name: read_thermo(args.results / name / "thermo.csv")
        for name in ("nve", "nvt")
    }
    velocities = {
        name: read_last_velocities(args.results / name / "trajectory.lammpstrj")
        for name in ("nve", "nvt")
    }
    summaries = {name: summarize_case(data) for name, data in cases.items()}

    checks = {
        "nve_energy_drift_below_2_percent": summaries["nve"]["relative_endpoint_energy_drift"] < 0.02,
        "nvt_mean_temperature_within_0.2": abs(summaries["nvt"]["mean_temperature"] - args.target_temperature) < 0.2,
        "at_least_50_samples_per_case": all(summary["samples"] >= 50 for summary in summaries.values()),
    }
    output = {
        "units": "reduced_lj",
        "target_temperature": args.target_temperature,
        "cases": summaries,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    (args.results / "summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    colors = {"nve": "#1769aa", "nvt": "#d95f02"}
    for name, data in cases.items():
        time = data["step"] * 0.005
        axes[0, 0].plot(time, data["temp"], label=name.upper(), color=colors[name], alpha=0.85)
        axes[0, 1].plot(time, data["etotal"] / data["atoms"], label=name.upper(), color=colors[name], alpha=0.85)
        axes[1, 0].plot(time, data["pressure"], label=name.upper(), color=colors[name], alpha=0.7)

        speeds = np.linalg.norm(velocities[name], axis=1)
        axes[1, 1].hist(speeds, bins=24, density=True, histtype="step", linewidth=1.8, label=name.upper(), color=colors[name])

    vmax = max(float(np.linalg.norm(value, axis=1).max()) for value in velocities.values())
    grid = np.linspace(0.0, vmax * 1.05, 300)
    axes[1, 1].plot(grid, maxwell_speed(grid, args.target_temperature), "k--", label="Maxwell (target T)")

    axes[0, 0].axhline(args.target_temperature, color="black", linestyle="--", linewidth=1)
    axes[0, 0].set(title="Temperature", xlabel="Reduced time", ylabel="T")
    axes[0, 1].set(title="Total energy per atom", xlabel="Reduced time", ylabel="E/N")
    axes[1, 0].set(title="Pressure", xlabel="Reduced time", ylabel="P")
    axes[1, 1].set(title="Last-frame speed distribution", xlabel="Speed", ylabel="Probability density")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        axis.legend()
    fig.suptitle("Lennard-Jones fluid: NVE vs NVT")
    fig.savefig(args.results / "comparison.png", dpi=160)
    plt.close(fig)

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["all_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

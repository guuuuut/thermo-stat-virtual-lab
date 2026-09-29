from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure"
MSD_CSV = RESULTS_ROOT / "msd_theory_curves.csv"
SPEED_CSV = RESULTS_ROOT / "speed_distribution.csv"
MSD_PNG = RESULTS_ROOT / "msd_theory_comparison.png"
DIFFUSION_PNG = RESULTS_ROOT / "diffusion_pressure_comparison.png"
SPEED_PNG = RESULTS_ROOT / "speed_distribution_comparison.png"
TIMESTEP_SIZE = 0.005
SPEED_HISTOGRAM_BINS = 40
SPEED_SAMPLE_START_LJ = 50.0


def read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return {
        key: np.asarray([float(row[key]) for row in rows], dtype=float)
        for key in rows[0]
    }


def read_speed_samples(path: Path, minimum_step: int) -> np.ndarray:
    speeds: list[float] = []
    with path.open("r", encoding="utf-8") as handle:
        while True:
            marker = handle.readline()
            if not marker:
                break
            if marker.strip() != "ITEM: TIMESTEP":
                continue
            step = int(handle.readline())
            if handle.readline().strip() != "ITEM: NUMBER OF ATOMS":
                raise ValueError(f"Invalid atom-count header in {path}")
            atom_count = int(handle.readline())
            if not handle.readline().startswith("ITEM: BOX BOUNDS"):
                raise ValueError(f"Invalid box header in {path}")
            for _ in range(3):
                handle.readline()
            atom_header = handle.readline().split()[2:]
            required = ("vx", "vy", "vz")
            if any(name not in atom_header for name in required):
                raise ValueError(f"Missing velocity fields in {path}")
            indices = [atom_header.index(name) for name in required]
            for _ in range(atom_count):
                values = handle.readline().split()
                if step >= minimum_step:
                    vx, vy, vz = (float(values[index]) for index in indices)
                    speeds.append(math.sqrt(vx * vx + vy * vy + vz * vz))
    if not speeds:
        raise ValueError(f"No speed samples found in {path}")
    return np.asarray(speeds, dtype=float)


def maxwell_speed_density(speed: np.ndarray, temperature: float) -> np.ndarray:
    coefficient = 4.0 * math.pi * (1.0 / (2.0 * math.pi * temperature)) ** 1.5
    return coefficient * speed**2 * np.exp(-(speed**2) / (2.0 * temperature))


def main() -> None:
    summary = json.loads((RESULTS_ROOT / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (RESULTS_ROOT / "run_manifest.json").read_text(encoding="utf-8")
    )
    directories = {
        float(case["target_pressure"]): str(case["directory"])
        for case in manifest["cases"]
    }
    cases = sorted(summary["cases"], key=lambda item: item["mean_pressure"])

    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
        }
    )

    msd_rows: list[dict[str, float | int]] = []
    figure, axes = plt.subplots(2, 3, figsize=(11.4, 6.7), sharex=True)
    axes_flat = axes.ravel()
    for axis, case in zip(axes_flat, cases, strict=False):
        target = float(case["target_pressure"])
        msd = read_csv(RESULTS_ROOT / directories[target] / "msd.csv")
        model = 6.0 * float(case["diffusion_lj"]) * msd["time"]
        axis.plot(msd["time"], msd["msd"], color="#176b8f", linewidth=1.25, label="LAMMPS MSD")
        axis.plot(msd["time"], model, color="#d36f32", linewidth=1.25, linestyle="--", label="Einstein model: 6D*t")
        axis.axvspan(
            float(case["fit_time_start"]),
            float(case["fit_time_end"]),
            color="#7d8f9a",
            alpha=0.10,
            label="fit window",
        )
        axis.set_title(
            f"target P*={target:.2f}; mean P*={float(case['mean_pressure']):.3f}\n"
            f"D*={float(case['diffusion_lj']):.3f}, fit R²={float(case['msd_fit_r2']):.4f}"
        )
        axis.grid(alpha=0.22)
        for time, actual, predicted in zip(msd["time"], msd["msd"], model, strict=False):
            msd_rows.append(
                {
                    "target_pressure": target,
                    "timestep": int(round(time / TIMESTEP_SIZE)),
                    "time_lj": float(time),
                    "msd_actual": float(actual),
                    "msd_einstein_model": float(predicted),
                    "in_fit_window": int(
                        float(case["fit_time_start"])
                        <= time
                        <= float(case["fit_time_end"])
                    ),
                }
            )
    axes_flat[-1].axis("off")
    handles, labels = axes_flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower right", bbox_to_anchor=(0.96, 0.08), frameon=False)
    figure.supxlabel("reduced time t*")
    figure.supylabel("MSD*")
    figure.suptitle("Mean-squared displacement: simulation and Einstein diffusion model")
    figure.tight_layout(rect=(0.03, 0.04, 1.0, 0.94))
    figure.savefig(MSD_PNG, dpi=180)
    plt.close(figure)

    with MSD_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(msd_rows[0]))
        writer.writeheader()
        writer.writerows(msd_rows)

    pressure = np.asarray([float(case["mean_pressure"]) for case in cases])
    pressure_std = np.asarray([float(case["pressure_std"]) for case in cases])
    diffusion = np.asarray([float(case["diffusion_lj"]) for case in cases])
    inverse_fit = summary["inverse_pressure_fit"]
    pressure_line = np.linspace(float(np.min(pressure)) * 0.92, float(np.max(pressure)) * 1.04, 300)
    diffusion_line = float(inverse_fit["a"]) / pressure_line + float(inverse_fit["b"])
    figure, axis = plt.subplots(figsize=(7.4, 4.8))
    axis.errorbar(
        pressure,
        diffusion,
        xerr=pressure_std,
        fmt="o",
        color="#176b8f",
        ecolor="#7d8f9a",
        capsize=3,
        label="LAMMPS estimate",
    )
    axis.plot(
        pressure_line,
        diffusion_line,
        color="#d36f32",
        linewidth=1.7,
        label="theory-guided fit: D*=a/P*+b",
    )
    axis.text(
        0.97,
        0.95,
        f"a={float(inverse_fit['a']):.4f}\n"
        f"b={float(inverse_fit['b']):.4f}\n"
        f"R²={float(inverse_fit['r_squared']):.4f}",
        transform=axis.transAxes,
        horizontalalignment="right",
        verticalalignment="top",
    )
    axis.set_xlabel("mean pressure P*")
    axis.set_ylabel("diffusion coefficient D*")
    axis.set_title("Pressure dependence of the diffusion coefficient")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(DIFFUSION_PNG, dpi=180)
    plt.close(figure)

    minimum_step = int(round(SPEED_SAMPLE_START_LJ / TIMESTEP_SIZE))
    speed_samples: dict[float, np.ndarray] = {}
    for case in cases:
        target = float(case["target_pressure"])
        speed_samples[target] = read_speed_samples(
            RESULTS_ROOT / directories[target] / "trajectory.lammpstrj", minimum_step
        )
    global_max = max(float(np.max(values)) for values in speed_samples.values())
    speed_max = math.ceil(global_max * 2.0) / 2.0
    bin_edges = np.linspace(0.0, speed_max, SPEED_HISTOGRAM_BINS + 1)
    centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    speed_rows: list[dict[str, float | int]] = []
    figure, axes = plt.subplots(2, 3, figsize=(11.4, 6.7), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    for axis, case in zip(axes_flat, cases, strict=False):
        target = float(case["target_pressure"])
        values = speed_samples[target]
        observed, _ = np.histogram(values, bins=bin_edges, density=True)
        temperature = float(case["mean_temperature"])
        theory = maxwell_speed_density(centers, temperature)
        axis.bar(
            centers,
            observed,
            width=np.diff(bin_edges),
            color="#6fb6d2",
            alpha=0.72,
            label="LAMMPS histogram",
        )
        axis.plot(centers, theory, color="#d36f32", linewidth=1.7, label="Maxwell theory")
        axis.set_title(
            f"target P*={target:.2f}; mean T*={temperature:.3f}\n"
            f"samples={values.size}"
        )
        axis.grid(alpha=0.20)
        for index, (left, right, center, measured, predicted) in enumerate(
            zip(bin_edges[:-1], bin_edges[1:], centers, observed, theory, strict=False)
        ):
            speed_rows.append(
                {
                    "target_pressure": target,
                    "bin_index": index,
                    "speed_left": float(left),
                    "speed_right": float(right),
                    "speed_center": float(center),
                    "observed_density": float(measured),
                    "maxwell_density": float(predicted),
                    "mean_temperature": temperature,
                    "sample_count": int(values.size),
                    "sample_start_time_lj": SPEED_SAMPLE_START_LJ,
                }
            )
    axes_flat[-1].axis("off")
    handles, labels = axes_flat[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower right", bbox_to_anchor=(0.95, 0.10), frameon=False)
    figure.supxlabel("reduced speed v*")
    figure.supylabel("probability density")
    figure.suptitle("Speed distribution: LAMMPS samples and Maxwell theory")
    figure.tight_layout(rect=(0.03, 0.04, 1.0, 0.94))
    figure.savefig(SPEED_PNG, dpi=180)
    plt.close(figure)

    with SPEED_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(speed_rows[0]))
        writer.writeheader()
        writer.writerows(speed_rows)

    print(f"Wrote {MSD_CSV}")
    print(f"Wrote {SPEED_CSV}")
    print(f"Wrote {MSD_PNG}, {DIFFUSION_PNG}, and {SPEED_PNG}")


if __name__ == "__main__":
    main()

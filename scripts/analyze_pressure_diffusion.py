from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure"
OUTPUT_CSV = RESULTS_ROOT / "diffusion_vs_pressure.csv"
OUTPUT_JSON = RESULTS_ROOT / "summary.json"
OUTPUT_PNG = RESULTS_ROOT / "diffusion_vs_pressure.png"

SIGMA_M = 3.405e-10
ARGON_TIME_UNIT_S = 2.156349e-12
DIFFUSION_UNIT_M2_S = SIGMA_M**2 / ARGON_TIME_UNIT_S


def read_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"No rows found in {path}")
    return {
        key: np.asarray([float(row[key]) for row in rows], dtype=float)
        for key in rows[0]
    }


def linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residual = float(np.sum((y - predicted) ** 2))
    total = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - residual / total if total > 0 else 1.0
    return float(slope), float(intercept), r_squared


def analyze_case(case_root: Path, target_pressure: float) -> dict[str, float]:
    thermo = read_csv(case_root / "thermo.csv")
    msd = read_csv(case_root / "msd.csv")

    maximum_time = float(msd["time"][-1])
    fit_start = maximum_time * 0.20
    fit_end = maximum_time * 0.90
    fit_mask = (msd["time"] >= fit_start) & (msd["time"] <= fit_end)
    slope, intercept, msd_r2 = linear_fit(msd["time"][fit_mask], msd["msd"][fit_mask])
    diffusion = slope / 6.0

    production_mask = thermo["time"] >= maximum_time * 0.10
    mean_pressure = float(np.mean(thermo["pressure"][production_mask]))
    pressure_std = float(np.std(thermo["pressure"][production_mask], ddof=1))
    mean_density = float(np.mean(thermo["density"][production_mask]))
    mean_temperature = float(np.mean(thermo["temp"][production_mask]))

    return {
        "target_pressure": target_pressure,
        "mean_pressure": mean_pressure,
        "pressure_std": pressure_std,
        "mean_density": mean_density,
        "mean_temperature": mean_temperature,
        "fit_time_start": fit_start,
        "fit_time_end": fit_end,
        "msd_slope": slope,
        "msd_intercept": intercept,
        "msd_fit_r2": msd_r2,
        "diffusion_lj": diffusion,
        "diffusion_m2_s_argon": diffusion * DIFFUSION_UNIT_M2_S,
        "diffusion_times_pressure": diffusion * mean_pressure,
    }


def main() -> None:
    manifest = json.loads((RESULTS_ROOT / "run_manifest.json").read_text(encoding="utf-8"))
    cases = [
        analyze_case(
            RESULTS_ROOT / entry["directory"],
            float(entry["target_pressure"]),
        )
        for entry in manifest["cases"]
    ]
    cases.sort(key=lambda item: item["mean_pressure"])

    pressure = np.asarray([case["mean_pressure"] for case in cases])
    diffusion = np.asarray([case["diffusion_lj"] for case in cases])
    inverse_pressure = 1.0 / pressure
    inv_slope, inv_intercept, inv_r2 = linear_fit(inverse_pressure, diffusion)
    log_slope, log_intercept, log_r2 = linear_fit(np.log(pressure), np.log(diffusion))
    dp = diffusion * pressure
    dp_cv = float(np.std(dp, ddof=1) / np.mean(dp))

    summary = {
        "temperature_lj": manifest["temperature"],
        "protocol": manifest["protocol"],
        "diffusion_definition": "D = (1/6) d(MSD)/dt in 3D",
        "fit_window": "20% to 90% of NVT production time",
        "argon_mapping": {
            "time_unit_ps": ARGON_TIME_UNIT_S * 1e12,
            "diffusion_unit_m2_s": DIFFUSION_UNIT_M2_S,
        },
        "cases": cases,
        "inverse_pressure_fit": {
            "model": "D = a/P + b",
            "a": inv_slope,
            "b": inv_intercept,
            "r_squared": inv_r2,
        },
        "power_law_fit": {
            "model": "D = C * P^n",
            "exponent_n": log_slope,
            "coefficient_C": math.exp(log_intercept),
            "r_squared_log_space": log_r2,
        },
        "dp_constancy": {
            "mean": float(np.mean(dp)),
            "coefficient_of_variation": dp_cv,
        },
        "supports_inverse_pressure": bool(
            inv_r2 >= 0.95 and abs(log_slope + 1.0) <= 0.20 and dp_cv <= 0.20
        ),
        "limitations": [
            "One trajectory per pressure; no independent-repeat uncertainty estimate.",
            "NPT determines equilibrium volume, then NVT at fixed volume is used for MSD to avoid barostat coordinate scaling.",
            "Argon SI conversion is illustrative; the simulated model is in LJ reduced units.",
        ],
    }

    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)
    OUTPUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.4))
    order = np.argsort(inverse_pressure)
    fitted = inv_slope * inverse_pressure[order] + inv_intercept
    axes[0].scatter(inverse_pressure, diffusion, color="#176b8f", s=48, label="LAMMPS")
    axes[0].plot(inverse_pressure[order], fitted, color="#d36f32", label=f"fit, R²={inv_r2:.4f}")
    axes[0].set_xlabel("1 / mean pressure P*")
    axes[0].set_ylabel("diffusion coefficient D*")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.25)

    axes[1].loglog(pressure, diffusion, "o", color="#176b8f", label="LAMMPS")
    pressure_line = np.linspace(float(np.min(pressure)), float(np.max(pressure)), 200)
    axes[1].loglog(
        pressure_line,
        math.exp(log_intercept) * pressure_line**log_slope,
        color="#d36f32",
        label=f"D ∝ P^{log_slope:.3f}",
    )
    axes[1].set_xlabel("mean pressure P*")
    axes[1].set_ylabel("diffusion coefficient D*")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.25, which="both")
    figure.suptitle("Isothermal LJ gas diffusion at T*=2.0")
    figure.tight_layout()
    figure.savefig(OUTPUT_PNG, dpi=180)
    plt.close(figure)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

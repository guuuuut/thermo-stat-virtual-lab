from __future__ import annotations

import base64
import html
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = PROJECT_ROOT / "results" / "diffusion_pressure"
TEMPLATE_PATH = PROJECT_ROOT / "visualization" / "pressure_analysis_template.html"
OUTPUT_PATH = PROJECT_ROOT / "visualization" / "pressure_analysis.html"


def image_data(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> None:
    summary = json.loads((RESULTS_ROOT / "summary.json").read_text(encoding="utf-8"))
    rows = []
    for case in sorted(summary["cases"], key=lambda item: item["mean_pressure"]):
        rows.append(
            "<tr>"
            f"<td>{float(case['target_pressure']):.2f}</td>"
            f"<td>{float(case['mean_pressure']):.4f}</td>"
            f"<td>{float(case['mean_temperature']):.4f}</td>"
            f"<td>{float(case['diffusion_lj']):.4f}</td>"
            f"<td>{float(case['msd_fit_r2']):.4f}</td>"
            f"<td>{float(case['diffusion_times_pressure']):.4f}</td>"
            "</tr>"
        )
    inverse_fit = summary["inverse_pressure_fit"]
    power_fit = summary["power_law_fit"]
    replacements = {
        "__MSD_IMAGE__": image_data(RESULTS_ROOT / "msd_theory_comparison.png"),
        "__DIFFUSION_IMAGE__": image_data(RESULTS_ROOT / "diffusion_pressure_comparison.png"),
        "__SPEED_IMAGE__": image_data(RESULTS_ROOT / "speed_distribution_comparison.png"),
        "__CASE_ROWS__": "\n".join(rows),
        "__INV_R2__": f"{float(inverse_fit['r_squared']):.4f}",
        "__POWER_EXPONENT__": f"{float(power_fit['exponent_n']):.3f}",
        "__DP_CV__": f"{float(summary['dp_constancy']['coefficient_of_variation']) * 100:.1f}%",
        "__FIT_FORMULA__": html.escape(
            f"D* = {float(inverse_fit['a']):.4f}/P* "
            f"{float(inverse_fit['b']):+.4f}"
        ),
    }
    page = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        if page.count(placeholder) != 1:
            raise ValueError(f"Expected one placeholder {placeholder}")
        page = page.replace(placeholder, value)
    OUTPUT_PATH.write_text(page, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

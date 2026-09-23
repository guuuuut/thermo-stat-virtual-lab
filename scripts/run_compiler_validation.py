"""Run the ExperimentSpec sample matrix and generate Markdown/JSON reports."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from experiment_compiler import SpecValidationError, compile_experiment, validate_spec  # noqa: E402
from experiment_compiler.schema import default_spec  # noqa: E402
from tests.case_matrix import CASES, build_case  # noqa: E402


def run_case(case: dict) -> dict:
    record = {
        "name": case["name"],
        "expected": "valid" if case["valid"] else "invalid",
        "expected_codes": case["expected_codes"],
    }
    try:
        spec = build_case(case)
        validate_spec(spec)
        compile_experiment(spec)
        actual = "valid"
        codes: list[str] = []
        issues: list[dict] = []
    except SpecValidationError as exc:
        actual = "invalid"
        codes = sorted({issue.code for issue in exc.issues})
        issues = [issue.to_dict() for issue in exc.issues]

    record.update(
        {
            "actual": actual,
            "codes": codes,
            "issues": issues,
            "passed": (
                actual == record["expected"]
                and set(case["expected_codes"]).issubset(codes)
            ),
        }
    )
    return record


def run_lammps_parse(lmp: Path, scripts: dict[str, str]) -> list[dict]:
    checks = []
    with tempfile.TemporaryDirectory(prefix="experiment-compiler-") as temp:
        temp_root = Path(temp)
        for name, text in scripts.items():
            case_root = temp_root / name.replace(".", "_")
            case_root.mkdir()
            input_path = case_root / name
            input_path.write_text(text, encoding="utf-8", newline="\n")
            try:
                completed = subprocess.run(
                    [str(lmp), "-skiprun", "-in", str(input_path), "-log", "none"],
                    cwd=case_root,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                combined = (completed.stdout or "") + "\n" + (completed.stderr or "")
                checks.append(
                    {
                        "script": name,
                        "exit_code": completed.returncode,
                        "passed": completed.returncode == 0 and "ERROR:" not in combined,
                        "warnings": [
                            line.strip()
                            for line in combined.splitlines()
                            if "WARNING:" in line
                        ],
                        "error_excerpt": "\n".join(
                            line for line in combined.splitlines() if "ERROR:" in line
                        )[:2000],
                    }
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                checks.append(
                    {
                        "script": name,
                        "exit_code": None,
                        "passed": False,
                        "warnings": [],
                        "error_excerpt": str(exc),
                    }
                )
    return checks


def markdown_report(report: dict) -> str:
    stats = report["summary"]
    lines = [
        "# ExperimentSpec → LAMMPS 编译与规则校验测试报告",
        "",
        f"- 生成时间（UTC）：`{report['generated_at']}`",
        f"- Python：`{report['environment']['python']}`",
        f"- 样例总数：**{stats['total']}**",
        f"- 有效样例：**{stats['valid']}**；无效样例：**{stats['invalid']}**",
        f"- 通过：**{stats['passed']}**；失败：**{stats['failed']}**",
        f"- 不同错误码覆盖：**{stats['error_code_count']}**",
        "",
        "## 结论",
        "",
        (
            "全部样例均符合预期；编译器对模式、类型、数值范围、跨字段物理约束、"
            "系综可比性和模板安全性进行严格校验。"
            if stats["failed"] == 0
            else "存在未通过样例，不能将该编译器视为通过验收。"
        ),
        "",
        "## 校验边界",
        "",
        "- 仅接受 `schema_version=1.0` 与 `lj_ensemble_comparison`。",
        "- 仅支持三维、FCC、单组分 `lj/cut`、全周期边界。",
        "- 拒绝未知字段、错误类型、布尔值冒充整数、NaN/Infinity。",
        "- 检查 cutoff/σ、cutoff+skin/盒长、阻尼/时间步以及采样整除关系。",
        "- 比较实验必须恰好包含 NVE 与 NVT，并共享确定性准备协议。",
        "- 模板仅替换编译器生成的白名单 token，并二次扫描危险 LAMMPS 命令。",
        "",
        "## 样例结果",
        "",
        "| # | 样例 | 预期 | 实际 | 错误码 | 结果 |",
        "|---:|---|---|---|---|---|",
    ]
    for index, case in enumerate(report["cases"], start=1):
        codes = ", ".join(case["codes"]) or "—"
        lines.append(
            f"| {index} | `{case['name']}` | {case['expected']} | "
            f"{case['actual']} | `{codes}` | {'PASS' if case['passed'] else 'FAIL'} |"
        )

    lines.extend(["", "## LAMMPS 解析检查", ""])
    if report["lammps_checks"]:
        lines.extend(
            [
                "| 脚本 | 退出码 | Warning 数 | 结果 |",
                "|---|---:|---:|---|",
            ]
        )
        for check in report["lammps_checks"]:
            lines.append(
                f"| `{check['script']}` | {check['exit_code']} | "
                f"{len(check['warnings'])} | {'PASS' if check['passed'] else 'FAIL'} |"
            )
    else:
        lines.append("未提供 `--lammps`，未执行 LAMMPS `-skiprun` 解析检查。")

    lines.extend(
        [
            "",
            "## 错误返回示例",
            "",
            "每次失败返回顶层 `SPEC_VALIDATION_FAILED`，并在 `issues` 中聚合全部问题。",
            "每条问题固定包含 `code`、`path`、`message`、`value`、`expected`、`hint`。",
            "完整逐样例问题对象保存在同目录 JSON 报告中。",
            "",
            "## 尚未覆盖",
            "",
            "该报告验证的是受控模板和 LAMMPS 语法解析，不等同于长时间物理收敛验证。",
            "正式教学实验还应针对每个状态点执行平衡诊断、独立重复和统计误差分析。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, default=PROJECT_ROOT / "reports")
    parser.add_argument("--lammps", type=Path)
    args = parser.parse_args()

    cases = [run_case(case) for case in CASES]
    compiled = compile_experiment(default_spec())
    lammps_checks = run_lammps_parse(args.lammps, compiled.scripts) if args.lammps else []
    error_codes = sorted({code for case in cases for code in case["codes"]})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
        "summary": {
            "total": len(cases),
            "valid": sum(case["expected"] == "valid" for case in cases),
            "invalid": sum(case["expected"] == "invalid" for case in cases),
            "passed": sum(case["passed"] for case in cases),
            "failed": sum(not case["passed"] for case in cases),
            "error_code_count": len(error_codes),
            "error_codes": error_codes,
        },
        "compiler": {
            "spec_sha256": compiled.fingerprint,
            "manifest": compiled.manifest,
        },
        "cases": cases,
        "lammps_checks": lammps_checks,
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.report_dir / "experiment_compiler_validation.json"
    md_path = args.report_dir / "experiment_compiler_validation.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    md_path.write_text(markdown_report(report), encoding="utf-8", newline="\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["failed"] == 0 and all(
        check["passed"] for check in lammps_checks
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

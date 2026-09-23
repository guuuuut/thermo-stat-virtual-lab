from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from experiment_compiler import SpecValidationError, TemplateCompileError, compile_experiment, validate_spec
from experiment_compiler.compiler import render_template, validate_generated_script
from experiment_compiler.schema import default_spec
from tests.case_matrix import CASES, build_case


class ValidationMatrixTests(unittest.TestCase):
    def test_all_samples_match_expected_outcome(self) -> None:
        self.assertGreaterEqual(len(CASES), 20)
        for case in CASES:
            with self.subTest(case=case["name"]):
                spec = build_case(case)
                if case["valid"]:
                    validated = validate_spec(spec)
                    self.assertEqual(validated, spec)
                else:
                    with self.assertRaises(SpecValidationError) as caught:
                        validate_spec(spec)
                    codes = {issue.code for issue in caught.exception.issues}
                    self.assertTrue(
                        set(case["expected_codes"]).issubset(codes),
                        f"expected {case['expected_codes']}, got {sorted(codes)}",
                    )

    def test_validation_returns_defensive_copy(self) -> None:
        original = default_spec()
        validated = validate_spec(original)
        validated["run"]["temperature"] = 9.0
        self.assertEqual(original["run"]["temperature"], 1.2)

    def test_error_payload_is_complete_and_json_serializable(self) -> None:
        spec = default_spec()
        spec["run"]["temperature"] = float("inf")
        spec["comparison"]["shared_initial_state"] = False
        with self.assertRaises(SpecValidationError) as caught:
            validate_spec(spec)
        payload = caught.exception.to_dict()
        json.dumps(payload, allow_nan=False)
        error = payload["error"]
        self.assertEqual(error["code"], "SPEC_VALIDATION_FAILED")
        self.assertEqual(error["issue_count"], 2)
        for issue in error["issues"]:
            self.assertEqual(
                set(issue), {"code", "path", "message", "value", "expected", "hint"}
            )


class CompilationTests(unittest.TestCase):
    def test_compiles_nve_and_nvt(self) -> None:
        result = compile_experiment(default_spec())
        self.assertEqual(set(result.scripts), {"in.lj_nve", "in.lj_nvt"})
        self.assertIn("fix             production all nve", result.scripts["in.lj_nve"])
        self.assertIn("fix             production all nvt", result.scripts["in.lj_nvt"])
        self.assertNotIn("{{", "".join(result.scripts.values()))

    def test_compilation_is_deterministic(self) -> None:
        first = compile_experiment(default_spec())
        second = compile_experiment(copy.deepcopy(default_spec()))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.scripts, second.scripts)
        self.assertEqual(first.manifest, second.manifest)

    def test_spec_change_changes_fingerprint(self) -> None:
        changed = default_spec()
        changed["run"]["temperature"] = 1.3
        self.assertNotEqual(
            compile_experiment(default_spec()).fingerprint,
            compile_experiment(changed).fingerprint,
        )

    def test_manifest_hashes_match_script_bytes(self) -> None:
        import hashlib

        result = compile_experiment(default_spec())
        for name, text in result.scripts.items():
            expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self.assertEqual(result.manifest["scripts"][name]["sha256"], expected)

    def test_template_token_mismatch_is_rejected(self) -> None:
        with self.assertRaises(TemplateCompileError) as caught:
            render_template("units {{UNITS}}\n{{MISSING}}\n", {"UNITS": "lj"})
        self.assertEqual(caught.exception.code, "TEMPLATE_TOKEN_MISMATCH")

    def test_forbidden_generated_command_is_rejected(self) -> None:
        script = """clear
units lj
dimension 3
boundary p p p
atom_style atomic
pair_style lj/cut 2.5
fix             production all nve
shell echo unsafe
run 100
write_data final.data
"""
        with self.assertRaises(TemplateCompileError) as caught:
            validate_generated_script(script, "nve")
        self.assertEqual(caught.exception.code, "FORBIDDEN_LAMMPS_COMMAND")

    def test_custom_template_cannot_add_unbound_token(self) -> None:
        bad_template = Path(tempfile.gettempdir()) / "bad_lammps_template.in.tpl"
        bad_template.write_text("clear\n{{USER_COMMAND}}\n", encoding="utf-8")
        try:
            with self.assertRaises(TemplateCompileError) as caught:
                compile_experiment(default_spec(), bad_template)
            self.assertEqual(caught.exception.code, "TEMPLATE_TOKEN_MISMATCH")
        finally:
            bad_template.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

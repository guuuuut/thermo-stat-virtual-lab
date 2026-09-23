# ExperimentSpec → LAMMPS 编译与规则校验测试报告

- 生成时间（UTC）：`2026-08-28T05:53:47.538625+00:00`
- Python：`3.11.5`
- 样例总数：**55**
- 有效样例：**17**；无效样例：**38**
- 通过：**55**；失败：**0**
- 不同错误码覆盖：**15**

## 结论

全部样例均符合预期；编译器对模式、类型、数值范围、跨字段物理约束、系综可比性和模板安全性进行严格校验。

## 校验边界

- 仅接受 `schema_version=1.0` 与 `lj_ensemble_comparison`。
- 仅支持三维、FCC、单组分 `lj/cut`、全周期边界。
- 拒绝未知字段、错误类型、布尔值冒充整数、NaN/Infinity。
- 检查 cutoff/σ、cutoff+skin/盒长、阻尼/时间步以及采样整除关系。
- 比较实验必须恰好包含 NVE 与 NVT，并共享确定性准备协议。
- 模板仅替换编译器生成的白名单 token，并二次扫描危险 LAMMPS 命令。

## 样例结果

| # | 样例 | 预期 | 实际 | 错误码 | 结果 |
|---:|---|---|---|---|---|
| 1 | `valid_default` | valid | valid | `—` | PASS |
| 2 | `valid_temperature_min` | valid | valid | `—` | PASS |
| 3 | `valid_temperature_max` | valid | valid | `—` | PASS |
| 4 | `valid_density_min` | valid | valid | `—` | PASS |
| 5 | `valid_density_max` | valid | valid | `—` | PASS |
| 6 | `valid_cells_max` | valid | valid | `—` | PASS |
| 7 | `valid_timestep_min_ratio_edge` | valid | valid | `—` | PASS |
| 8 | `valid_timestep_max_ratio_edge` | valid | valid | `—` | PASS |
| 9 | `valid_seed_min` | valid | valid | `—` | PASS |
| 10 | `valid_seed_max` | valid | valid | `—` | PASS |
| 11 | `valid_sampling_at_run_length` | valid | valid | `—` | PASS |
| 12 | `valid_alternate_sampling` | valid | valid | `—` | PASS |
| 13 | `valid_reversed_ensembles` | valid | valid | `—` | PASS |
| 14 | `valid_shift_disabled` | valid | valid | `—` | PASS |
| 15 | `valid_sort_disabled` | valid | valid | `—` | PASS |
| 16 | `valid_cutoff_ratio_lower` | valid | valid | `—` | PASS |
| 17 | `valid_cutoff_ratio_upper_large_box` | valid | valid | `—` | PASS |
| 18 | `invalid_root_type` | invalid | invalid | `TYPE_MISMATCH` | PASS |
| 19 | `invalid_missing_system` | invalid | invalid | `MISSING_FIELD` | PASS |
| 20 | `invalid_unknown_root_field` | invalid | invalid | `UNKNOWN_FIELD` | PASS |
| 21 | `invalid_unknown_nested_field` | invalid | invalid | `UNKNOWN_FIELD` | PASS |
| 22 | `invalid_schema_version` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 23 | `invalid_experiment_type` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 24 | `invalid_units` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 25 | `invalid_dimension` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 26 | `invalid_boundary_nonperiodic` | invalid | invalid | `UNSUPPORTED_BOUNDARY` | PASS |
| 27 | `invalid_boundary_type` | invalid | invalid | `TYPE_MISMATCH` | PASS |
| 28 | `invalid_lattice` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 29 | `invalid_cells_boolean` | invalid | invalid | `TYPE_MISMATCH` | PASS |
| 30 | `invalid_cells_below_min` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 31 | `invalid_small_periodic_box` | invalid | invalid | `PERIODIC_BOX_TOO_SMALL` | PASS |
| 32 | `invalid_density_zero` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 33 | `invalid_density_above_max` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 34 | `invalid_mass_string` | invalid | invalid | `TYPE_MISMATCH` | PASS |
| 35 | `invalid_potential_style` | invalid | invalid | `UNSUPPORTED_VALUE` | PASS |
| 36 | `invalid_sigma_zero` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 37 | `invalid_cutoff_sigma_ratio` | invalid | invalid | `CUTOFF_SIGMA_RATIO` | PASS |
| 38 | `invalid_neighbor_skin_negative` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 39 | `invalid_temperature_infinite` | invalid | invalid | `NOT_FINITE` | PASS |
| 40 | `invalid_temperature_below_min` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 41 | `invalid_high_risk_state` | invalid | invalid | `HIGH_RISK_STATE_POINT` | PASS |
| 42 | `invalid_timestep_zero` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 43 | `invalid_seed_zero` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 44 | `invalid_equilibration_too_short` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 45 | `invalid_production_too_short` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 46 | `invalid_damping_too_small` | invalid | invalid | `THERMOSTAT_DAMPING_RATIO` | PASS |
| 47 | `invalid_damping_too_large` | invalid | invalid | `THERMOSTAT_DAMPING_RATIO` | PASS |
| 48 | `invalid_thermo_interval_zero` | invalid | invalid | `OUT_OF_RANGE` | PASS |
| 49 | `invalid_interval_exceeds_run` | invalid | invalid | `INTERVAL_EXCEEDS_RUN` | PASS |
| 50 | `invalid_interval_not_divisor` | invalid | invalid | `INTERVAL_NOT_DIVISOR` | PASS |
| 51 | `invalid_ensembles_type` | invalid | invalid | `TYPE_MISMATCH` | PASS |
| 52 | `invalid_ensemble_missing_nvt` | invalid | invalid | `INVALID_ENSEMBLE_COMPARISON` | PASS |
| 53 | `invalid_ensemble_duplicate` | invalid | invalid | `INVALID_ENSEMBLE_COMPARISON` | PASS |
| 54 | `invalid_shared_state_false` | invalid | invalid | `COMPARABILITY_REQUIRED` | PASS |
| 55 | `invalid_multiple_issues` | invalid | invalid | `COMPARABILITY_REQUIRED, INTERVAL_NOT_DIVISOR, OUT_OF_RANGE` | PASS |

## LAMMPS 解析检查

| 脚本 | 退出码 | Warning 数 | 结果 |
|---|---:|---:|---|
| `in.lj_nve` | 0 | 0 | PASS |
| `in.lj_nvt` | 0 | 0 | PASS |

## 错误返回示例

每次失败返回顶层 `SPEC_VALIDATION_FAILED`，并在 `issues` 中聚合全部问题。
每条问题固定包含 `code`、`path`、`message`、`value`、`expected`、`hint`。
完整逐样例问题对象保存在同目录 JSON 报告中。

## 尚未覆盖

该报告验证的是受控模板和 LAMMPS 语法解析，不等同于长时间物理收敛验证。
正式教学实验还应针对每个状态点执行平衡诊断、独立重复和统计误差分析。

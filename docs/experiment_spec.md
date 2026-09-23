# ExperimentSpec 1.0（LJ 系综对比）

`ExperimentSpec` 是受控 JSON，不允许直接携带 LAMMPS 命令。当前实验类型固定为
`lj_ensemble_comparison`，编译结果为一份 NVE 与一份 NVT 输入脚本。

## 字段与范围

| 路径 | 类型 | 支持范围 |
|---|---|---|
| `schema_version` | string | 仅 `1.0` |
| `experiment_type` | string | 仅 `lj_ensemble_comparison` |
| `system.units` | string | 仅 `lj` |
| `system.dimension` | integer | 仅 `3` |
| `system.boundary` | array | 仅 `["p","p","p"]` |
| `system.lattice` | string | 仅 `fcc` |
| `system.cells` | integer | `[2,20]`，并受周期盒条件约束 |
| `system.density` | number | `[0.01,1.4]` |
| `system.mass` | number | `[0.01,100]` |
| `potential.style` | string | 仅 `lj/cut` |
| `potential.epsilon` | number | `[0.01,100]` |
| `potential.sigma` | number | `[0.1,10]` |
| `potential.cutoff` | number | `[0.15,50]`，且在 `[1.5σ,5σ]` |
| `potential.shift` | boolean | `true/false` |
| `potential.neighbor_skin` | number | `[0.05,2]` |
| `run.temperature` | number | `[0.05,10]` |
| `run.timestep` | number | `[0.0001,0.02]` |
| `run.seed` | integer | `[1,2147483646]` |
| `run.equilibration_steps` | integer | `[100,10000000]` |
| `run.production_steps` | integer | `[100,10000000]` |
| `run.thermostat_damping` | number | `[0.001,100]`，且在 `[10dt,1000dt]` |
| `outputs.thermo_interval` | integer | 生产步数的正因子 |
| `outputs.trajectory_interval` | integer | 生产步数的正因子 |
| `outputs.sort_atoms` | boolean | `true/false` |
| `comparison.ensembles` | array | 恰好包含一次 `nve` 和一次 `nvt` |
| `comparison.shared_initial_state` | boolean | 必须为 `true` |

所有对象均为封闭对象：缺少字段和出现未知字段都会报错。JSON 中的字符串数字、整数位置的
小数、以 `true/false` 冒充整数，以及 NaN/Infinity 都会被拒绝。

## 跨字段规则

1. `cutoff + neighbor_skin <= box_length / 2`，避免最小镜像条件失效；
2. `1.5*sigma <= cutoff <= 5*sigma`；
3. `10*timestep <= thermostat_damping <= 1000*timestep`；
4. 两个采样间隔均不得超过生产步数，并须整除生产步数；
5. 当密度大于 `1.2` 时，短 Demo 不接受低于 `0.1` 的温度；
6. NVE/NVT 必须使用相同参数、随机种子和确定性平衡协议。

## 编译

```powershell
.\.venv\Scripts\python.exe .\scripts\compile_experiment.py `
  .\specs\lj_nve_nvt.example.json `
  --output .\generated\lj_nve_nvt
```

成功时生成 `in.lj_nve`、`in.lj_nvt`、`normalized_spec.json` 和 `manifest.json`。
manifest 记录规范 SHA-256 以及每个脚本的 SHA-256，便于复现实验。

## 错误合同

规范错误退出码为 `3`，并返回聚合 JSON：

```json
{
  "error": {
    "code": "SPEC_VALIDATION_FAILED",
    "message": "ExperimentSpec validation failed with 2 issue(s)",
    "issue_count": 2,
    "issues": [
      {
        "code": "OUT_OF_RANGE",
        "path": "$.run.temperature",
        "message": "Number lies outside the supported range.",
        "value": -1,
        "expected": "[0.05, 10.0]",
        "hint": "Choose a value inside the inclusive range."
      }
    ]
  }
}
```

文件不存在/JSON 语法错误使用退出码 `2`，模板编译错误使用退出码 `4`，输出写入错误使用
退出码 `5`。模板 token 必须与编译器白名单完全一致；生成后还会检查未解析 token、必需命令
以及 `shell`、`python`、`include`、`jump`、`quit` 等禁用命令。

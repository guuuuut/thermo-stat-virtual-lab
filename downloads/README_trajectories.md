# 五组压强 LJ 气体扩散轨迹数据说明

本数据包用于“等温条件下压强与气体扩散”教学实验。体系采用 Lennard–Jones（LJ）约化单位，包含 500 个质量和相互作用完全相同的粒子；粒子类型 1、2 只是示踪标签，分别表示 NVT 生产阶段开始时位于模拟盒左半区和右半区的粒子。
Lennard-Jones势:
$$U(r) = 4\epsilon[(\sigma/r)^{12} - (\sigma/r)^{6}]$$
其中：
$r^{-12}$ 表示近距离强排斥；
$r^{-6}$ 表示较远距离的吸引；
$\sigma$ 决定粒子的有效尺寸；
$\varepsilon$ 决定相互作用强度。

固定条件：

- 约化温度：T* = 2.0
- 目标约化压强：P* = 0.10、0.20、0.30、0.40、0.50
- 时间步长：dt* = 0.005
- 粒子数：N = 500

## 一、数据包包含什么

```text
pressure_diffusion_trajectories/
├─ README.md                         本说明
├─ preview/                          三维动画使用的短轨迹
│  ├─ run_manifest.json              预览模拟参数
│  └─ p_0p10 ... p_0p50/
│     └─ trajectory.lammpstrj        每个压强一条反射墙轨迹
├─ analysis/                         扩散系数分析使用的长轨迹和表格
│  ├─ run_manifest.json              分析模拟参数
│  ├─ summary.json                   拟合结果与氩参数换算
│  ├─ diffusion_vs_pressure.csv      五个压强的扩散系数汇总
│  ├─ msd_theory_curves.csv          实际 MSD 与 Einstein 模型曲线数据
│  ├─ speed_distribution.csv         实际速率直方图与 Maxwell 理论数据
│  └─ p_0p10 ... p_0p50/
│     ├─ trajectory.lammpstrj        每个压强一条周期边界长轨迹
│     ├─ msd.csv                     均方位移时间序列
│     └─ thermo.csv                  温度、压强、密度和体积
└─ lammps/                           生成两类数据的 LAMMPS 输入
```

### preview/：展示用反射墙轨迹

- NPT 平衡阶段使用周期边界，以获得目标压强对应的平衡盒体积。
- 固定平衡后的盒体积，再将 NVT 生产阶段切换为六面反射墙。
- 模拟时间为 0–100 t*，每 1.25 t* 输出一帧，共 81 帧。
- 适合观察左右两类示踪粒子的混合过程和墙面反弹。

### analysis/：扩散分析用周期轨迹

- NPT 平衡后，在固定体积下进行周期边界 NVT 生产模拟。
- 模拟时间为 0–500 t*，每 12.5 t* 输出一帧，共 41 帧。
- 周期边界避免有限封闭盒中的 MSD 长时间饱和，因此用于扩散系数拟合。
- preview/ 和 analysis/ 来自独立模拟，不能首尾拼接成一条连续轨迹。
  **思考：**为什么在模拟中我们要使用周期性轨迹（粒子从右边离开盒会从左边进入）？

## 二、轨迹字段如何理解

每帧 trajectory.lammpstrj 的原子字段为：

```text
id type x y z xu yu zu vx vy vz
```

| 字段     | 含义                                            |
| -------- | ----------------------------------------------- |
| id       | 粒子的固定编号                                  |
| type     | 示踪标签；1 为初始左半箱，2 为初始右半箱        |
| x y z    | 当前坐标；用于三维显示、空间分箱和浓度分析      |
| xu yu zu | 未折返坐标；周期边界长轨迹中用于位移和 MSD 分析 |
| vx vy vz | 三个方向的约化速度分量                          |

时间由 t* = timestep × 0.005 得到。网页采用氩参数作示意换算：1 t* ≈ 2.156349 ps。

## 三、可以怎样使用

1. **查看三维轨迹**：在 OVITO 中直接打开 .lammpstrj；用 type 给两类粒子着色，播放轨迹即可观察混合或反弹。
2. **研究混合动力学**：沿 x 方向分箱，统计每个分箱中两类粒子数，计算混合度随时间的变化。
3. **研究扩散与压强**：读取 analysis/diffusion_vs_pressure.csv，绘制 D*–P*、D*–1/P* 或 log D*–log P*。
4. **重新计算扩散系数**：使用 analysis/*/msd.csv，在线性时间窗内拟合 MSD 斜率，并用三维关系 D* = slope/6。
5. **比较理论曲线**：analysis/msd_theory_curves.csv 已对齐实际 MSD 与 6D*t；analysis/speed_distribution.csv 已对齐实际速率密度与 Maxwell 理论密度。
6. **检查热力学状态**：使用 analysis/*/thermo.csv 检查平均温度、平均压强、密度和平衡稳定性。

## 四、如何从 LAMMPS 数据提取分析量

压缩包不附完整分析程序。下面片段只说明字段选择和核心公式，便于学生自行完成数据处理。

### 1. 从 msd.csv 得到扩散系数

msd.csv 已包含 time 与 msd 两列。在选定线性时间窗后拟合斜率：

```python
import numpy as np
import pandas as pd

data = pd.read_csv("analysis/p_0p30/msd.csv")
window = data[(data.time >= 100) & (data.time <= 450)]
slope, intercept = np.polyfit(window.time, window.msd, 1)
D = slope / 6                 # 三维 Einstein 关系
msd_model = 6 * D * data.time
```

### 2. 从 trajectory.lammpstrj 得到速率

读取每帧 ITEM: ATOMS 标题，找到 vx、vy、vz 三列，再逐粒子计算：

```python
header = atom_header.split()[2:]
ivx, ivy, ivz = [header.index(name) for name in ("vx", "vy", "vz")]
vx, vy, vz = [float(values[i]) for i in (ivx, ivy, ivz)]
speed = (vx**2 + vy**2 + vz**2) ** 0.5
```

将速率样本归一化为概率密度直方图，并与 LJ 约化单位下的 Maxwell 分布比较：

```text
f(v*) = 4π [1/(2πT*)]^(3/2) v*² exp[-v*²/(2T*)]
```

### 3. 从汇总表得到 D–P 关系

```python
table = pd.read_csv("analysis/diffusion_vs_pressure.csv")
P = table["mean_pressure"]
D = table["diffusion_lj"]

# 稀薄气体近似：D* = a/P* + b
a, b = np.polyfit(1 / P, D, 1)
```

### 4. 从反射墙轨迹得到混合度

把 preview 轨迹的模拟盒沿 x 方向均分为 20 层，统计每层两类粒子数：

```text
M = 1 - Σ_i |n_A,i - n_B,i| / N
```

其中 n_A,i、n_B,i 是第 i 层中两类粒子数，N 是总粒子数。M = 0 表示两类粒子在各层完全分离，越接近 1 表示局部混合越均匀。

需要注意：若两类粒子总数不相等，原始 M 的理论上限小于 1。默认 P*=0.30 范例中 N_A=259、N_B=241，因此 M_max = 1 - |259-241|/500 = 0.964。末帧 M=0.884 相当于达到该理论上限的约 91.7%。

P*=0.30 的反射墙轨迹共有 81 帧，按该定义得到初始 M=0.000、末帧 M=0.884。由于两类粒子数为 259 和 241，其理论上限 M_max=0.964，末帧约达到上限的 91.7%。

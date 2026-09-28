# 五组压强 LJ 气体扩散轨迹数据说明

本数据包用于“等温条件下压强与气体扩散”教学实验。体系采用 Lennard–Jones（LJ）约化单位，包含 500 个质量和相互作用完全相同的粒子；粒子类型 1、2 只是示踪标签，分别表示 NVT 生产阶段开始时位于模拟盒左半区和右半区的粒子。

固定条件：

- 约化温度：T* = 2.0
- 目标约化压强：P* = 0.10、0.20、0.30、0.40、0.50
- 时间步长：dt* = 0.005
- 粒子数：N = 500

## 一、数据包包含什么

~~~text
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
│  └─ p_0p10 ... p_0p50/
│     ├─ trajectory.lammpstrj        每个压强一条周期边界长轨迹
│     ├─ msd.csv                     均方位移时间序列
│     └─ thermo.csv                  温度、压强、密度和体积
├─ lammps/                           生成两类数据的 LAMMPS 输入
└─ examples/
   ├─ analyze_mixing.py              混合度分析范例
   └─ mixing_p030.csv                范例输出
~~~

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

## 二、轨迹字段如何理解

每帧 trajectory.lammpstrj 的原子字段为：

~~~text
id type x y z xu yu zu vx vy vz
~~~

| 字段 | 含义 |
| --- | --- |
| id | 粒子的固定编号 |
| type | 示踪标签；1 为初始左半箱，2 为初始右半箱 |
| x y z | 当前坐标；用于三维显示、空间分箱和浓度分析 |
| xu yu zu | 未折返坐标；周期边界长轨迹中用于位移和 MSD 分析 |
| vx vy vz | 三个方向的约化速度分量 |

时间由 t* = timestep × 0.005 得到。网页采用氩参数作示意换算：1 t* ≈ 2.156349 ps。该换算只用于教学时间轴，模拟本身仍是 LJ 约化模型。

## 三、可以怎样使用

1. **查看三维轨迹**：在 OVITO 中直接打开 .lammpstrj；用 type 给两类粒子着色，播放轨迹即可观察混合或反弹。
2. **研究混合动力学**：沿 x 方向分箱，统计每个分箱中两类粒子数，计算混合度随时间的变化。
3. **研究扩散与压强**：读取 analysis/diffusion_vs_pressure.csv，绘制 D*–P*、D*–1/P* 或 log D*–log P*。
4. **重新计算扩散系数**：使用 analysis/*/msd.csv，在线性时间窗内拟合 MSD 斜率，并用三维关系 D* = slope/6。
5. **检查热力学状态**：使用 analysis/*/thermo.csv 检查平均温度、平均压强、密度和平衡稳定性。

## 四、Python 范例：计算混合度

范例脚本读取 preview/p_0p30/trajectory.lammpstrj，把模拟盒沿 x 方向均分为 20 层，并计算：

~~~text
M = 1 - Σ_i |n_A,i - n_B,i| / N
~~~

其中 n_A,i、n_B,i 是第 i 层中两类粒子数，N 是总粒子数。M = 0 表示两类粒子在各层完全分离，越接近 1 表示局部混合越均匀。

需要注意：若两类粒子总数不相等，原始 M 的理论上限小于 1。默认 P*=0.30 范例中 N_A=259、N_B=241，因此 M_max = 1 - |259-241|/500 = 0.964。末帧 M=0.884 相当于达到该理论上限的约 91.7%。课堂上可以进一步讨论是否应展示归一化指标 M/M_max。

解压后，在数据包根目录运行：

~~~powershell
python examples/analyze_mixing.py
~~~

也可以指定其他轨迹和输出文件：

~~~powershell
python examples/analyze_mixing.py preview/p_0p50/trajectory.lammpstrj --bins 20 --output examples/mixing_p050.csv
~~~

输出 CSV 包含：timestep、time_lj、mixing_index、type1_count、type2_count。脚本仅使用 Python 标准库。

随包提供的默认范例共读取 81 帧，得到初始混合度 M=0.000、末帧 M=0.884；完整逐帧结果见 examples/mixing_p030.csv。

## 五、使用时的注意事项

- 类型 1、2 的质量和 LJ 参数完全相同，颜色差异不代表两种不同气体。
- 反射墙预览轨迹适合展示混合；长时间扩散系数应使用周期边界分析轨迹。
- 旧的周期长轨迹在 P*=0.10、P*=0.40 的首帧各有一个处于周期盒边界附近的粒子，其显示位置与示踪标签分区不一致；这不改变粒子动力学或 MSD 结果。
- 当前每个压强只有一条独立轨迹，不能据此给出严格的不确定度；正式研究应增加不同随机种子的重复模拟。

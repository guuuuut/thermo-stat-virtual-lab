# 热力学与统计物理虚拟仿真实验 Demo

这个仓库保存第一版可运行的 Lennard–Jones（LJ）教学实验：LAMMPS 模拟、受控参数到脚本的编译与校验、五个等温压强下的气体扩散，以及预计算轨迹的三维可视化。

## 动画与数据

- [五组压强的三维扩散动画](visualization/pressure_diffusion.html)：0–100 个 LJ 约化时间单位，81 个真实轨迹帧/组；拖动旋转视角，0.25×、0.5×、1×、2× 播放。
- [MSD、扩散系数与速率分布分析页](visualization/pressure_analysis.html)：比较 LAMMPS 数据与 Einstein、反压强和 Maxwell 理论曲线。
- [动画预览图](visualization/pressure_diffusion_preview.png)。
- [五组压强的轨迹下载包](downloads/pressure_diffusion_trajectories.zip)：包含 0–100 t* 预览轨迹、0–500 t* 分析轨迹及对应的 MSD、热力学数据；文件说明见 [README_trajectories.md](downloads/README_trajectories.md)。
- [扩散系数与压强数据](results/diffusion_pressure/diffusion_vs_pressure.csv)：供课后分析，动画页面不预先展示幂律结论。
- [实验与校验说明](docs/experiment_spec.md)、[压强扩散计算报告](reports/pressure_diffusion_report.md)。

在仓库根目录运行本地静态服务器，再访问 http://127.0.0.1:8000/visualization/pressure_diffusion.html：

    python -m http.server 8000 --bind 127.0.0.1

页面使用 CDN 加载 Three.js，首次打开需要网络连接。轨迹数据已嵌入 HTML；CSV 下载链接从仓库的 results 目录读取文件。

## 一键同步到云服务器

默认使用现有阿里云轻量服务器、公网 IP 和项目专用 SSH 密钥：

    .\scripts\deploy_site.ps1

脚本会依次完成：重新生成 MSD、扩散系数和速率分布分析，重建动画与分析 HTML，按白名单重建无完整源码的轨迹 ZIP，计算本地哈希，上传临时文件，备份线上页面/ZIP/CSV，原子切换，核对服务器哈希，并从公网实际下载 ZIP 和 CSV 再次验证。任一步失败都会停止；服务器切换后的健康检查失败时会自动恢复备份。

如需改用正式域名进行公网检查：

    .\scripts\deploy_site.ps1 -PublicBaseUrl "https://boltzmann.me"

如服务器、用户或密钥路径发生变化，可使用 `-ServerAddress`、`-RemoteUser` 和 `-KeyPath` 参数覆盖默认值。脚本只负责构建和部署，不会自动执行 Git 提交或推送。

## 复现实验

环境：Windows 10/11、PowerShell、64 位 Python 3.11 或更新版本。LAMMPS 的 Windows wheel 依赖 Microsoft MPI 运行时。

    .\scripts\install_msmpi.ps1
    .\scripts\setup.ps1

运行基础 NVE/NVT 对比与编译器测试：

    .\scripts\run_demo.ps1
    .\.venv\Scripts\python.exe -m unittest discover -s tests

重新计算五组压强的分析数据、短预览轨迹并生成页面：

    .\.venv\Scripts\python.exe scripts\run_pressure_diffusion.py
    .\.venv\Scripts\python.exe scripts\analyze_pressure_diffusion.py
    .\.venv\Scripts\python.exe scripts\run_pressure_diffusion_preview.py
    .\.venv\Scripts\python.exe scripts\build_pressure_diffusion_3d.py

分析轨迹使用周期边界，在 NPT 平衡后的固定体积 NVT 阶段计算 MSD。预览轨迹在相同的 NPT 平衡后切换为六面反射墙，用于 0–100 个约化时间单位的动画。这样既能展示真实反弹，又避免有限反射盒使长时间 MSD 饱和而破坏扩散拟合。仓库包含预览轨迹和复算扩散系数所需的 CSV，完整长轨迹与运行日志可按上述命令重新生成。

## 目录

| 路径 | 内容 |
| --- | --- |
| experiment_compiler/、lammps/templates/ | ExperimentSpec 校验与 LAMMPS 模板编译 |
| lammps/、scripts/ | 模拟输入、执行和分析脚本 |
| visualization/ | 独立的 HTML 动画与模板 |
| results/diffusion_pressure_preview/ | 五组预计算短轨迹 |
| results/diffusion_pressure/ | MSD、热力学数据及分析结果 |
| tests/、reports/ | 测试与实验报告 |

本项目是教学概念验证。压强扩散结果来自每个压强一条轨迹，尚未通过独立重复估计不确定度；氩参数换算仅用于时间轴示意。

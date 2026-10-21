# 热力学与统计物理虚拟仿真实验 Demo

这个仓库保存第一版可运行的 Lennard–Jones（LJ）教学实验：LAMMPS 模拟、受控参数到脚本的编译与校验、五个等温压强下的气体扩散，以及预计算轨迹的三维可视化。

## 动画与数据

- [五组压强的三维扩散动画](visualization/pressure_diffusion.html)：0–100 个 LJ 约化时间单位，81 个真实轨迹帧/组；拖动旋转视角，0.25×、0.5×、1×、2× 播放。
- [分子动力学、LJ 模型与数据链路学习指南](visualization/learning.html)：面向初次接触 LAMMPS 的学生，包含原始文献和约化单位换算。
- [动画预览图](visualization/pressure_diffusion_preview.png)。
- [五组压强的轨迹下载包](downloads/pressure_diffusion_trajectories.zip)：包含 0–100 t* 预览轨迹、0–500 t* 分析轨迹及对应的 MSD、热力学数据；文件说明见 [README_trajectories.md](downloads/README_trajectories.md)。
- [实验与校验说明](docs/experiment_spec.md)、[压强扩散计算报告](reports/pressure_diffusion_report.md)。

在仓库根目录运行本地静态服务器，再访问 http://127.0.0.1:8000/visualization/pressure_diffusion.html：

    python -m http.server 8000 --bind 127.0.0.1

页面使用 CDN 加载 Three.js，首次打开需要网络连接。轨迹数据已嵌入 HTML；网站不提供现成分析结果，学生可下载基础输出自行完成统计与作图。

## 一键同步到云服务器

默认使用现有阿里云轻量服务器、公网 IP 和项目专用 SSH 密钥：

    .\scripts\deploy_site.ps1

脚本会依次完成：重建三维动画页面，部署学习指南，按白名单重建只含轨迹和基础输出的 ZIP，计算本地哈希，上传临时文件，备份线上版本，原子切换，核对服务器哈希，并从公网实际下载 ZIP 再次验证。部署时会撤下旧分析页和扩散系数汇总 CSV；任一步失败都会停止并自动恢复备份。

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

重新生成五组压强的长轨迹、短预览轨迹和动画页面：

    .\.venv\Scripts\python.exe scripts\run_pressure_diffusion.py
    .\.venv\Scripts\python.exe scripts\run_pressure_diffusion_preview.py
    .\.venv\Scripts\python.exe scripts\build_pressure_diffusion_3d.py

长轨迹使用周期边界，在 NPT 平衡后的固定体积 NVT 阶段输出 MSD、热力学量和粒子轨迹，供学生自行分析。预览轨迹在相同的 NPT 平衡后切换为六面反射墙，用于 0–100 个约化时间单位的动画。这样既能展示真实反弹，又为扩散系数拟合保留不受有限反射盒长期饱和影响的基础数据。

## 目录

| 路径 | 内容 |
| --- | --- |
| experiment_compiler/、lammps/templates/ | ExperimentSpec 校验与 LAMMPS 模板编译 |
| lammps/、scripts/ | 模拟输入、执行与页面构建脚本 |
| visualization/ | 独立的 HTML 动画与模板 |
| results/diffusion_pressure_preview/ | 五组预计算短轨迹 |
| results/diffusion_pressure/ | 供学生处理的周期轨迹、MSD 与热力学基础数据 |
| tests/、reports/ | 测试与实验报告 |

本项目是教学概念验证。压强扩散结果来自每个压强一条轨迹，尚未通过独立重复估计不确定度；氩参数换算仅用于时间轴示意。

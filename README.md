# 热力学与统计物理虚拟仿真实验 Demo

这个仓库保存第一版可运行的 Lennard–Jones（LJ）教学实验：LAMMPS 模拟、受控参数到脚本的编译与校验、五个等温压强下的气体扩散，以及预计算轨迹的三维可视化。

## 动画与数据

- [五组压强的三维扩散动画](visualization/pressure_diffusion.html)：0–100 个 LJ 约化时间单位，81 个真实轨迹帧/组；拖动旋转视角，0.25×、0.5×、1×、2× 播放。
- [分子动力学、LJ 模型与数据链路学习指南](visualization/learning.html)：面向初次接触 LAMMPS 的学生，包含原始文献和约化单位换算。
- [动画预览图](visualization/pressure_diffusion_preview.png)。
- [旧下载地址兼容入口](downloads/pressure_diffusion_trajectories.zip)：同样提供当前六选一作业包，供旧页面和历史分享链接使用。历史五组压强轨迹仍保存在 `results/` 中。
- [实验与校验说明](docs/experiment_spec.md)、[压强扩散计算报告](reports/pressure_diffusion_report.md)。
- [六选一数据分析小作业](visualization/homework.html)：任选一题，提交 1–2 张图与 200–400 字说明；包含温度与扩散、体系大小、速度自相关等选题。
- [六选一学生数据包](downloads/homework_20261027.zip)：47 个服务器 GPU 算例整理出的轻量 CSV、题单、字段说明及每题一个工况的原始 LAMMPS 输入文件，约 2.2 MB；不含教师示例报告和答案图。

在仓库根目录运行本地静态服务器，再访问 http://127.0.0.1:8000/visualization/pressure_diffusion.html：

    python -m http.server 8000 --bind 127.0.0.1

页面使用 CDN 加载 Three.js，首次打开需要网络连接。轨迹数据已嵌入 HTML；网站不提供现成分析结果，学生可下载基础输出自行完成统计与作图。

## 一键同步到云服务器

默认使用现有阿里云轻量服务器、公网 IP 和项目专用 SSH 密钥：

    .\scripts\deploy_site.ps1

脚本会依次完成：重建三维动画页面，部署学习指南，按白名单重建六选一作业 ZIP，并将旧下载地址同步为同一份作业包，计算本地哈希，上传临时文件，备份线上版本，原子切换，核对服务器哈希，并从公网实际下载 ZIP 再次验证。部署时会撤下旧分析页和扩散系数汇总 CSV；任一步失败都会停止并自动恢复备份。

同一命令还会根据 `docs/homework_20261027.md`、`visualization/homework_template.html`、`downloads/README_homework.md` 和 `results/homework_20261027/student_data/` 重建作业页及学生包，并一起备份、部署、校验和回滚。网站主下载入口统一指向六选一作业包；旧地址 `downloads/pressure_diffusion_trajectories.zip` 也提供完全相同的作业包，不再重新打包历史轨迹。部署同时核对两个公网下载地址与新版作业包的 SHA-256。六选一学生包单独校验 73 个文件及逐文件 SHA-256，并检查每题文件夹均有一个 `input.lmp`。

日常更新请修改上述源文件，随后执行一键部署。`visualization/pressure_diffusion.html` 和 `visualization/homework.html` 是生成文件，不应直接修改。教师示例报告、答案图和完整分析代码保留在本地，不随本次学生网站更新提交到公开仓库。

如需改用正式域名进行公网检查：

    .\scripts\deploy_site.ps1 -PublicBaseUrl "https://boltzmann.me"

如服务器、用户或密钥路径发生变化，可使用 `-ServerAddress`、`-RemoteUser` 和 `-KeyPath` 参数覆盖默认值。脚本只负责构建和部署，不会自动执行 Git 提交或推送。

固定发布顺序为：修改源文件 → 执行一键部署 → 确认公网页面和下载正常 → 查看 `git status --short`，只暂存本次相关文件 → 提交并推送。不要用手动逐文件上传替代脚本中的备份、校验和回滚。

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

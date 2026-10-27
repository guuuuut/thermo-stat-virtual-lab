#!/usr/bin/env bash
set -euo pipefail
base="$HOME/visual_lab_course_20261027"
cuda=/usr/local/cuda-13.0
mkdir -p "$base/source" "$base/logs" "$base/bin"
tar -xzf "$base/source/lammps-minimal-stable_30Sep2026.tar.gz" -C "$base/source"
tar -xzf "$base/source/lammps-third-party.tar.gz" -C "$base/source"
# The official install target also installs its man page, benchmarks and potentials.
tar -xzf "$base/source/lammps-stable_30Sep2026.tar.gz" -C "$base/source" --wildcards \
  'lammps-stable_30Sep2026/doc/lammps.1' \
  'lammps-stable_30Sep2026/bench/*' \
  'lammps-stable_30Sep2026/potentials/*'
export PATH="$cuda/bin:$PATH"
export LD_LIBRARY_PATH="$cuda/lib64:${LD_LIBRARY_PATH:-}"
cmake -S "$base/source/lammps-stable_30Sep2026/cmake" -B "$base/build" \
  -D CMAKE_BUILD_TYPE=Release \
  -D CMAKE_INSTALL_PREFIX="$base/install" \
  -D BUILD_MPI=OFF -D BUILD_OMP=ON -D BUILD_SHARED_LIBS=OFF \
  -D PKG_GPU=ON -D GPU_API=cuda -D GPU_ARCH=sm_120 -D GPU_PREC=double \
  -D CUDPP_OPT=OFF -D CUDA_BUILD_MULTIARCH=OFF \
  -D CUDA_TOOLKIT_ROOT_DIR="$cuda" \
  -D CUDA_NVCC_EXECUTABLE="$cuda/bin/nvcc" \
  -D DOWNLOAD_POTENTIALS=OFF -D ENABLE_TESTING=OFF -D BUILD_TOOLS=OFF
cmake --build "$base/build" -j 12
cmake --install "$base/build"
cat > "$base/bin/lmp-gpu" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
base="$HOME/visual_lab_course_20261027"
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=4
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/lib64:${LD_LIBRARY_PATH:-}"
exec "$base/install/bin/lmp" -sf gpu -pk gpu 1 neigh no "$@"
EOF
chmod +x "$base/bin/lmp-gpu"
"$base/install/bin/lmp" -help > "$base/logs/lammps-help.txt"
printf '%s\n' 'stable_30Sep2026' 'commit 8de817dd79bfe4525d5d39246a212d833e6dee07' \
  'CUDA 13.0, sm_120, GPU_PREC=double, GPU 0 only' > "$base/logs/environment.txt"
touch "$base/logs/build.complete"

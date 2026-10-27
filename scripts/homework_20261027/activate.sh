# Source this file; no system configuration or shell profile is changed.
source "$HOME/visual_lab_course_20261027/venv/bin/activate"
export PATH="$HOME/visual_lab_course_20261027/bin:$HOME/visual_lab_course_20261027/install/bin:/usr/local/cuda-13.0/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda-13.0/lib64:${LD_LIBRARY_PATH:-}"
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=4

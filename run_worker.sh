#!/bin/bash
# Research Reader — RunPod TTS Worker start script
#
# RunPod now runs ONLY the TTS worker.
# The full app (UI, library, player) runs on your local PC.
#
# Usage:
#   bash /workspace/research_reader/run_worker.sh

set -e

PROJECT_DIR="/workspace/research_reader"
cd "$PROJECT_DIR"

# XTTS model cache on network volume — survives pod termination
export XDG_DATA_HOME="/workspace/.cache"
mkdir -p "/workspace/.cache"

# Pull latest code from GitHub
echo "=== Pulling latest code... ==="
git pull --ff-only 2>&1 || echo "WARNING: git pull failed. Running existing code."

source venv/bin/activate

echo ""
echo "=== Research Reader TTS Worker ==="
python - <<'EOF'
import torch
if torch.cuda.is_available():
    print(f"Device : {torch.cuda.get_device_name(0)}")
    mem = torch.cuda.get_device_properties(0).total_memory // (1024**3)
    print(f"Memory : {mem} GB")
else:
    print("Device : CPU (no CUDA)")
EOF

PORT=${PORT:-8000}
echo ""
echo "Worker listening on 0.0.0.0:${PORT}"
echo "Set RUNPOD_WORKER_URL=https://<pod-id>-${PORT}.proxy.runpod.net on your local server."
echo ""
python -m uvicorn worker:app --host 0.0.0.0 --port "${PORT}"

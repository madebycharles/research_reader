#!/bin/bash
# Research Reader — RunPod start script
# Pulls latest code from GitHub then starts the server.
#
# Usage:
#   bash /workspace/research_reader/run_runpod.sh

set -e

PROJECT_DIR="/workspace/research_reader"
cd "$PROJECT_DIR"

# Keep the XTTS model cache on the network volume so it survives pod termination.
export XDG_DATA_HOME="/workspace/.cache"
mkdir -p "/workspace/.cache"

# ── Pull latest code from GitHub ─────────────────────────────────────────────
echo "=== Pulling latest code... ==="
if git pull --ff-only 2>&1; then
  echo "Code up to date."
else
  echo "WARNING: git pull failed (local changes or conflict). Running existing code."
fi

# ── Activate venv ─────────────────────────────────────────────────────────────
source venv/bin/activate

# ── Show device ───────────────────────────────────────────────────────────────
echo ""
echo "=== Research Reader ==="
python - <<'EOF'
import torch
if torch.cuda.is_available():
    print(f"Device : {torch.cuda.get_device_name(0)}")
else:
    print("Device : CPU (no CUDA)")
EOF

# ── Start server ──────────────────────────────────────────────────────────────
PORT=${PORT:-8000}
echo "Starting server on 0.0.0.0:${PORT} ..."
echo ""
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT}"

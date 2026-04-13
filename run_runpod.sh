#!/bin/bash
# Research Reader — RunPod start script
# Run from the project directory after setup_runpod.sh has been run.
#
# Usage:
#   cd /workspace/research_reader
#   bash run_runpod.sh

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

source venv/bin/activate

echo "=== Research Reader ==="
python - <<'EOF'
import torch
if torch.cuda.is_available():
    print(f"Device : {torch.cuda.get_device_name(0)}")
else:
    print("Device : CPU (no CUDA)")
EOF

PORT=${PORT:-8000}
echo "Starting server on 0.0.0.0:${PORT} ..."
echo ""
python -m uvicorn main:app --host 0.0.0.0 --port "${PORT}"

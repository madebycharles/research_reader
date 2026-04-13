#!/bin/bash
# Research Reader — RunPod one-time setup
# Run this once after uploading the project to /workspace/research_reader/
# Network volume must be mounted at /workspace (persists between sessions).
#
# Usage:
#   cd /workspace/research_reader
#   bash setup_runpod.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Research Reader — RunPod Setup ==="
echo "Project dir: $PROJECT_DIR"
cd "$PROJECT_DIR"

# ── 1. Data directories on network volume ───────────────────────────────────
echo ""
echo "[1/5] Creating data directories..."
mkdir -p data/papers data/voices data/audio
touch data/.gitkeep

# ── 2. Virtual environment ───────────────────────────────────────────────────
echo ""
echo "[2/5] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# ── 3. PyTorch (CUDA 12.1 build, pinned for Coqui TTS compatibility) ────────
echo ""
echo "[3/5] Installing PyTorch 2.5.1 + CUDA 12.1..."
pip install --upgrade pip --quiet
pip install torch==2.5.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu121 \
    --quiet

# ── 4. spaCy (must be installed before TTS to pin at <3.8) ──────────────────
echo ""
echo "[4/5] Installing spaCy and remaining dependencies..."
pip install "spacy>=3.7.0,<3.8.0" --quiet
pip install -r requirements.txt --quiet

# ── 5. Verify CUDA is visible ────────────────────────────────────────────────
echo ""
echo "[5/5] Verifying CUDA..."
python - <<'EOF'
import torch
if torch.cuda.is_available():
    name = torch.cuda.get_device_name(0)
    mem  = torch.cuda.get_device_properties(0).total_memory // (1024**3)
    print(f"  CUDA OK — {name} ({mem} GB)")
else:
    print("  WARNING: CUDA not detected — will run on CPU")
EOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "The XTTS v2 model (~2 GB) downloads automatically on first voice test."
echo ""
echo "Start the server with:"
echo "  bash run_runpod.sh"

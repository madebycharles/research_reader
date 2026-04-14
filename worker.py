"""
Research Reader — RunPod TTS Worker

Minimal FastAPI service. The local Research Reader server sends text chunks
here during paper preparation and receives WAV bytes back. No database,
no paper management — pure TTS.

Endpoints:
  GET  /health     — liveness check, reports device
  POST /voice      — upload a voice WAV (cached for the session)
  POST /generate   — synthesise text in a cached voice, return WAV bytes
"""

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from tts_engine import engine

app = FastAPI(title="Research Reader TTS Worker")

# Voice WAVs are stored here for the lifetime of the pod session.
# The path is on the network volume so it survives within a session,
# but is recreated fresh each time the worker starts.
_VOICE_DIR = Path(os.getenv("XDG_DATA_HOME", "/tmp")) / "rr_voices"
_VOICE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status":       "ok",
        "model_loaded": engine.is_loaded,
        "device":       engine.device or "not loaded",
    }


# ---------------------------------------------------------------------------
# Voice upload
# ---------------------------------------------------------------------------

@app.post("/voice")
async def upload_voice(
    voice_id: str    = Form(...),
    file:     UploadFile = File(...),
):
    """
    Store a voice WAV on the worker for use during this session.
    Call this once per voice before the first /generate request.
    Latent caching is handled lazily on the first /generate call.
    """
    wav_path = _VOICE_DIR / f"{voice_id}.wav"
    wav_path.write_bytes(await file.read())
    return {"voice_id": voice_id, "ready": True}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    text:     str
    voice_id: str
    language: str = "en"


@app.post("/generate")
def generate(req: GenerateRequest):
    """
    Synthesise *text* in the given voice.
    Returns raw WAV bytes (audio/wav, 24 kHz mono).
    """
    if not req.text.strip():
        raise HTTPException(400, "Text is empty.")

    wav_path = _VOICE_DIR / f"{req.voice_id}.wav"
    if not wav_path.exists():
        raise HTTPException(
            400,
            f"Voice '{req.voice_id}' not uploaded to this worker. "
            "Call POST /voice first.",
        )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name

    try:
        engine.generate(req.text, str(wav_path), out_path, req.language)
        audio_bytes = Path(out_path).read_bytes()
    finally:
        Path(out_path).unlink(missing_ok=True)

    return Response(content=audio_bytes, media_type="audio/wav")

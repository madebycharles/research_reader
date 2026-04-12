"""
Coqui XTTS v2 wrapper.

The model (~2 GB) is downloaded automatically on first use from HuggingFace.
Model is loaded once into memory and reused for all requests.
A threading lock prevents concurrent inference (XTTS is not thread-safe).
"""

import threading
from pathlib import Path
from typing import Optional

_lock = threading.Lock()


class TTSEngine:
    def __init__(self):
        self._tts = None
        self._loaded = False
        self._device: Optional[str] = None

    def _load(self):
        if self._loaded:
            return

        import torch
        from TTS.api import TTS  # noqa: PLC0415  (deferred import — model is large)

        # PyTorch 2.6 changed torch.load to default weights_only=True.
        # Coqui TTS was written against 2.4/2.5 and passes custom config
        # classes (XttsConfig) that aren't on the safe-globals allowlist.
        # Patch torch.load for the duration of the model load, then restore.
        _orig_load = torch.load
        torch.load = lambda *a, **kw: _orig_load(*a, **{**kw, "weights_only": False})

        try:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[TTS] Loading XTTS v2 on {self._device} "
                  f"(first run downloads ~2 GB — please wait)...")

            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2",
                            gpu=(self._device == "cuda"))
            self._loaded = True
            print(f"[TTS] Model ready on {self._device}.")
        finally:
            torch.load = _orig_load  # always restore, even on failure

    def generate(self, text: str, speaker_wav: str, output_path: str,
                 language: str = "en") -> None:
        """Synthesise *text* in the voice of *speaker_wav* and save to *output_path*."""
        self._load()
        with _lock:
            self._tts.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=language,
                file_path=output_path,
            )

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> Optional[str]:
        return self._device


# Module-level singleton — imported by main.py
engine = TTSEngine()

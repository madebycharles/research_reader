"""
Coqui XTTS v2 wrapper.

The model (~2 GB) is downloaded automatically on first use from HuggingFace.
Model is loaded once into memory and reused for all requests.
A threading lock prevents concurrent inference (XTTS is not thread-safe).

Speaker conditioning latents are computed once per voice WAV and cached in
memory, so a 470-paragraph paper doesn't re-process the WAV 470 times.
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
        self._speaker_cache: dict = {}  # wav_path → (gpt_cond_latent, speaker_embedding)

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

            # TTS(gpu=True) doesn't reliably move all XTTS components to CUDA
            # when using the lower-level inference API directly. Explicitly move
            # the model to the correct device to guarantee GPU inference.
            if self._device == "cuda":
                self._tts.synthesizer.tts_model.cuda()

            self._loaded = True
            actual = next(self._tts.synthesizer.tts_model.parameters()).device
            print(f"[TTS] Model ready — confirmed on {actual}.")
        finally:
            torch.load = _orig_load  # always restore, even on failure

    def _get_latents(self, speaker_wav: str):
        """Return cached (gpt_cond_latent, speaker_embedding) for a WAV file.

        Computed once per unique WAV path and held in memory for the lifetime
        of the process — avoids re-processing the speaker WAV on every paragraph.
        Tensors are explicitly moved to the model's device so inference stays on GPU.
        """
        if speaker_wav not in self._speaker_cache:
            import torch
            xtts = self._tts.synthesizer.tts_model
            gpt_cond_latent, speaker_embedding = xtts.get_conditioning_latents(
                audio_path=[speaker_wav]
            )
            if self._device == "cuda":
                gpt_cond_latent   = gpt_cond_latent.cuda()
                speaker_embedding = speaker_embedding.cuda()
            self._speaker_cache[speaker_wav] = (gpt_cond_latent, speaker_embedding)
            print(f"[TTS] Speaker latents cached for {Path(speaker_wav).name} "
                  f"on {gpt_cond_latent.device}")
        return self._speaker_cache[speaker_wav]

    def generate(self, text: str, speaker_wav: str, output_path: str,
                 language: str = "en") -> None:
        """Synthesise *text* in the voice of *speaker_wav* and save to *output_path*."""
        self._load()
        with _lock:
            import numpy as np
            import soundfile as sf

            xtts = self._tts.synthesizer.tts_model
            gpt_cond_latent, speaker_embedding = self._get_latents(speaker_wav)

            out = xtts.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
            )

            wav = np.array(out["wav"])
            sf.write(output_path, wav, 24000)

    def clear_speaker_cache(self, speaker_wav: str = None) -> None:
        """Remove a specific WAV from the cache (e.g. after voice deletion),
        or clear the entire cache if called with no argument."""
        if speaker_wav:
            self._speaker_cache.pop(speaker_wav, None)
        else:
            self._speaker_cache.clear()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def device(self) -> Optional[str]:
        return self._device


# Module-level singleton — imported by main.py
engine = TTSEngine()

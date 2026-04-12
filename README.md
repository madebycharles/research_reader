# Research Reader

A mobile-first web app that reads academic papers aloud using a cloned voice, built for passive listening during moments where you want to engage your audio-sensory cognitive channels even while occupied with other task e.g long commutes, boring night shifts to earn enough to pay rent while being a broke researcher (This is why I built this).

Common "read aloud" features on browsers are just text readers. No context, voices are very robotic, I am silly enough to enjoy listening to my own voice, and that of my girlfriend. Also, screen readers will basically try to read everything - even headers and footers! No context whatsoever that it is a research paper. Commercial readers are also EXPENSIVE! 

So I built this with the help of ClaudeCode. You might find it helpful.

## How it Works

Upload a PDF, clone a voice from a short WAV recording, and listen hands-free. Audio is pre-generated in batch so playback is instant.

---

## Features

- **Intelligent PDF parsing** — detects two-column layouts and reads in correct order, fixes hyphenated line breaks, strips inline citations (`[1]`, `(Smith, 2023)`), replaces figure/table references with verbal equivalents
- **Content processing for audio** — injects section announcements, expands acronyms on first use (e.g. `LLM` → _Large Language Model (LLM)_), normalises symbols and Greek letters for natural speech
- **Voice cloning** — upload 30–60 seconds of clean WAV speech; Coqui XTTS v2 synthesises in that voice for all future papers
- **Batch pre-generation** — generate all audio in the background before you start listening; fully cached, zero wait at playback time
- **Mobile player** — dark-mode UI with play/pause, paragraph skip, speed control (0.75×–2×), section navigator, and lock screen controls via the Media Session API
- **Progress persistence** — resumes from where you left off per paper
- **Audio caching** — generated WAV files are reused on replay; no regeneration cost
- **Server log viewer** — in-app log panel showing full tracebacks for any errors

---

## Tech Stack

| Layer               | Technology                                                               |
| ------------------- | ------------------------------------------------------------------------ |
| Backend             | Python 3.11, FastAPI, Uvicorn                                            |
| PDF parsing         | PyMuPDF (fitz)                                                           |
| TTS / Voice cloning | Coqui XTTS v2 (`TTS` library)                                            |
| Storage             | SQLite (papers, voices, progress) + local filesystem (audio, PDFs, WAVs) |
| Frontend            | Vanilla HTML/CSS/JS, mobile-first, dark theme                            |
| Remote access       | Tailscale (optional, for phone access away from home network)            |

---

## Prerequisites

- **Python 3.11** — Coqui TTS does not support Python 3.12+
- **Windows 10/11** (instructions below are Windows-specific; Linux/Mac paths differ slightly)
- ~4 GB free disk space (2 GB for the XTTS v2 model, rest for audio cache)
- No GPU required — CPU generation works fine with batch pre-generation

---

## Installation

### 1. Install Python 3.11

Coqui TTS requires Python 3.9–3.11. If you only have Python 3.12+:

```
winget install Python.Python.3.11
```

Or download `python-3.11.10-amd64.exe` from [python.org](https://www.python.org/downloads/release/python-31110/) and tick **Add to PATH** during install.

Verify:
```
py -3.11 --version
```

### 2. Clone / download the project

```
cd c:\Projects
git clone <repo-url> research_reader
cd research_reader
```

### 3. Run setup

```
setup.bat
```

This will:
- Find Python 3.11 via the Windows `py` launcher
- Create a virtual environment (`venv/`)
- Install PyTorch 2.5.1 (CPU build)
- Install all dependencies with pinned versions for Coqui TTS compatibility
- Create the `data/` subdirectories

> **First TTS use**: the XTTS v2 model (~2 GB) downloads automatically from HuggingFace on the first voice test or prepare run. This happens once and is cached at `C:\Users\<you>\AppData\Local\tts\`.

---

## Running the server

```
run.bat
```

The server starts at `http://localhost:8000`. Your local network IP is printed at startup for phone access.

To keep it running in the background, use Windows Terminal or run it as a scheduled task.

---

## Phone access via Tailscale

[Tailscale](https://tailscale.com) creates a private network between your PC and phone without port forwarding.

1. Install Tailscale on your PC and phone
2. Sign in on both with the same account
3. Start the Research Reader server (`run.bat`)
4. On your phone, open `http://<your-pc-tailscale-ip>:8000`

Your PC's Tailscale IP is shown in the Tailscale tray icon or at `tailscale ip -4` in a terminal.

---

## Usage

### First-time setup

1. Open the app in a browser
2. Tap the **microphone icon** (top right) to open Voice Profiles
3. Enter a name, select a clean WAV file (30–60 seconds of speech, no background noise), tap **Save Voice**
4. Tap **Test** to verify the voice sounds correct — this also triggers the model download on first run

### Listening to a paper

1. Tap **+** to upload a PDF
2. The paper appears in your library with a **Prepare for listening** button
3. Tap **Prepare** — audio is generated for every paragraph in the background
4. When the progress bar reaches 100% (or the **Ready** badge appears), open the paper
5. Select your voice, tap play

### Player controls

| Control       | Action                                   |
| ------------- | ---------------------------------------- |
| Play / Pause  | Start or pause playback                  |
| ⏮ / ⏭         | Previous / next paragraph                |
| Speed buttons | 0.75× · 1× · 1.25× · 1.5× · 2×           |
| Section list  | Tap any section to jump directly to it   |
| Lock screen   | Play/pause/skip via phone media controls |

---

## Voice cloning guide

### Recording a good voice sample

- **Duration**: 30–60 seconds minimum; 2–3 minutes gives better results
- **Environment**: quiet room, no echo, no background noise
- **Consistency**: same distance from mic throughout
- **Content**: read naturally — any text works, doesn't need to match your papers
- **Format**: WAV (16-bit, any sample rate — XTTS resamples internally)

A bad sample produces robotic or inconsistent output. If the test sounds off, re-record in a quieter space.

### Multiple voices

You can save multiple voices (e.g. your own voice, a colleague's, a preferred podcast speaker). Select the active voice per paper in the reader screen.

Audio is cached per voice — switching voice on a paper that was already prepared will trigger re-generation for the new voice.

---

## Project structure

```
research_reader/
├── main.py           — FastAPI app: all routes, batch prepare logic, logging
├── pdf_parser.py     — PDF parsing: column detection, dehyphenation, section extraction
├── processor.py      — Text processing: acronym expansion, symbol normalisation, TTS chunking
├── tts_engine.py     — Coqui XTTS v2 wrapper: lazy load, thread lock, torch.load patch
├── database.py       — SQLite: papers, voices, progress tables
├── requirements.txt  — Pinned dependencies
├── setup.bat         — One-time setup script (Windows)
├── run.bat           — Start server (Windows)
├── static/
│   ├── index.html    — Mobile UI (two screens: library + reader)
│   ├── style.css     — Dark theme, mobile-first layout
│   └── app.js        — Player engine, library, voice management, log viewer
└── data/             — Runtime data (gitignored)
    ├── papers/       — Uploaded PDFs
    ├── voices/       — Voice WAV samples
    ├── audio/        — Generated audio chunks (cached)
    ├── reader.db     — SQLite database
    └── reader.log    — Server log
```

---

## API reference

### Papers

| Method   | Endpoint             | Description                                |
| -------- | -------------------- | ------------------------------------------ |
| `POST`   | `/api/papers/upload` | Upload a PDF (multipart)                   |
| `GET`    | `/api/papers`        | List all papers                            |
| `GET`    | `/api/papers/{id}`   | Get paper with full section/paragraph data |
| `DELETE` | `/api/papers/{id}`   | Delete paper and its cached audio          |

### Voices

| Method   | Endpoint                | Description                            |
| -------- | ----------------------- | -------------------------------------- |
| `POST`   | `/api/voices/upload`    | Upload a WAV + name (multipart)        |
| `GET`    | `/api/voices`           | List saved voices                      |
| `POST`   | `/api/voices/{id}/test` | Generate a test phrase with this voice |
| `DELETE` | `/api/voices/{id}`      | Delete voice                           |

### TTS

| Method | Endpoint            | Description                                                                       |
| ------ | ------------------- | --------------------------------------------------------------------------------- |
| `POST` | `/api/tts/generate` | Generate audio for one paragraph (`?paper_id&voice_id&section_idx&paragraph_idx`) |

### Batch preparation

| Method | Endpoint                          | Description                                                              |
| ------ | --------------------------------- | ------------------------------------------------------------------------ |
| `POST` | `/api/papers/{id}/prepare`        | Start background pre-generation (`?voice_id`)                            |
| `GET`  | `/api/papers/{id}/prepare/status` | Poll progress (`?voice_id`) — derived from filesystem, survives restarts |

### Progress & utilities

| Method | Endpoint                   | Description                                  |
| ------ | -------------------------- | -------------------------------------------- |
| `GET`  | `/api/progress/{paper_id}` | Get last listened position                   |
| `POST` | `/api/progress/{paper_id}` | Save position (`?section_idx&paragraph_idx`) |
| `GET`  | `/api/status`              | Model load status and device                 |
| `GET`  | `/api/log`                 | Last N server log lines (`?lines=60`)        |

---

## Dependency version notes

Coqui TTS has strict compatibility requirements that conflict with the latest versions of several packages. These are pinned in `requirements.txt` and `setup.bat`:

| Package                | Pinned          | Reason                                                                                                                                   |
| ---------------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `torch` / `torchaudio` | `==2.5.1`       | 2.6 changed `torch.load` default (`weights_only=True`) and switched torchaudio's audio backend to require `torchcodec` — both break XTTS |
| `transformers`         | `>=4.33, <4.40` | 4.40+ removed `BeamSearchScorer` from the top-level namespace                                                                            |
| `spacy`                | `>=3.7, <3.8`   | 3.8+ requires `thinc>=8.3.12` which does not exist on PyPI (version jumped from 8.3.0 to 8.4.0)                                          |
| `Python`               | `3.11`          | Coqui TTS uses runtime type syntax (`X \| None`) incompatible with 3.9; 3.12+ not yet supported                                          |

---

## Roadmap

- [ ] Mental notes — tap during playback to drop a timestamped marker, review per-paper later
- [ ] End-of-section pause — brief silence between sections for natural listening breaks
- [ ] Skip section button — dedicated in-player control (in addition to section list tap)
- [ ] MP3 output — smaller files, faster streaming over Tailscale
- [ ] Kokoro TTS backend — optional swap for real-time CPU generation without voice cloning
- [ ] Session-persistent acronym tracking — don't re-expand the same acronym across paragraphs

---

## License

### This project

Copyright (c) 2026 Charles Njoku

Released under the **MIT License** — see [LICENSE](LICENSE) for the full text.

You are free to use, modify, and distribute this software for any purpose, including commercially, provided the copyright notice and license text are retained.

### Third-party components

This project depends on third-party software with their own licenses. Key ones to be aware of:

| Component | License | Notes |
| --- | --- | --- |
| [Coqui TTS](https://github.com/coqui-ai/TTS) | Mozilla Public License 2.0 (MPL-2.0) | Copyleft applies to TTS library modifications only, not this project |
| [XTTS v2 model weights](https://huggingface.co/coqui/XTTS-v2) | [Coqui Public Model License 1.0](https://coqui.ai/cpml) | **Non-commercial use only** — review before any commercial deployment |
| [PyTorch](https://github.com/pytorch/pytorch) | BSD-3-Clause | |
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | AGPL-3.0 / Commercial | Free for open-source use; commercial use requires a license from Artifex |

> **Important:** The XTTS v2 model weights are licensed for **non-commercial use only** under the Coqui Public Model License. If you intend to use this project commercially, you must replace the TTS backend with a commercially licensed alternative.

### Attribution (CC-BY)

Documentation and written content in this project (this README and inline comments) are additionally licensed under [Creative Commons Attribution 4.0 International (CC-BY 4.0)](https://creativecommons.org/licenses/by/4.0/). You may adapt and share the documentation with attribution.

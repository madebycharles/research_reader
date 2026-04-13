# Research Reader

A mobile-first web app that reads academic papers aloud using a cloned voice, built for passive listening during moments where you want to engage your audio-sensory cognitive channels even while occupied with other task e.g long commutes or during boring night shifts you do to earn enough to pay rent while being a broke researcher (Story of my life).

Common "read aloud" features on browsers are just text readers. They basically try to read everything including headers and footers! No context whatsoever that it is a research paper.

Voices are also very robotic. I am silly enough to enjoy listening to my own voice, and that of my lovely girlfriend, whose support makes listening to her voice the closest thing to keeping me sane. 

So I built this with the help of ClaudeCode. You might find it helpful.

## How it Works

Upload a PDF, clone a voice from a short WAV recording, and listen hands-free. Audio is pre-generated in batch so playback is instant.

---

## Features

- **Intelligent PDF parsing** — detects two-column layouts and reads in correct order; filters running page headers/footers, publisher footnotes (copyright, DOI, received/accepted dates), author affiliations, and figure/table captions using a three-layer detection pipeline (positional margins, cross-page repetition, pattern + font-size); fixes hyphenated line breaks; strips inline citations (`[1]`, `(Smith, 2023)`); replaces figure/table references with verbal equivalents
- **Content processing for audio** — injects section announcements, expands acronyms on first use (e.g. `LLM` → _Large Language Model (LLM)_), normalises symbols and Greek letters for natural speech
- **Voice cloning** — upload 30–60 seconds of clean WAV speech; Coqui XTTS v2 synthesises in that voice for all future papers; speaker embedding computed once per voice and cached in memory for the duration of a prepare job
- **Batch pre-generation** — generate all audio in the background before you start listening; fully cached, zero wait at playback time
- **Ready notification** — browser push notification fires when a prepare job completes; works on Android Chrome automatically, on iOS requires Add to Home Screen
- **Mobile player** — dark-mode UI with play/pause, paragraph skip, speed control (0.75×–2×), section navigator, and lock screen controls via the Media Session API
- **Progress persistence** — resumes from where you left off per paper
- **Audio caching** — generated WAV files are reused on replay; no regeneration cost
- **Re-parse** — apply updated parser to already-uploaded papers without re-uploading; clears stale audio cache automatically
- **Server log viewer** — in-app log panel showing full tracebacks for any errors
- **Cloud GPU support** — deploy to RunPod (or any Linux GPU server) for 15–25× faster generation; GitHub → RunPod pipeline via `git pull` on startup

---

## Tech Stack

| Layer               | Technology                                                               |
| ------------------- | ------------------------------------------------------------------------ |
| Backend             | Python 3.11, FastAPI, Uvicorn                                            |
| PDF parsing         | PyMuPDF (fitz) — dict-mode extraction with per-span font size metadata   |
| TTS / Voice cloning | Coqui XTTS v2 (`TTS` library)                                            |
| Storage             | SQLite (papers, voices, progress) + local filesystem (audio, PDFs, WAVs) |
| Frontend            | Vanilla HTML/CSS/JS, mobile-first, dark theme                            |
| Remote access       | Tailscale (optional, for phone access away from home network)            |
| Cloud GPU           | RunPod (optional) — RTX 3090/4090, network volume for persistence        |

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
git clone https://github.com/madebycharles/research_reader
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

## Cloud GPU deployment (RunPod)

For significantly faster audio generation (15–25× vs CPU), deploy to a RunPod GPU pod.

### One-time setup

1. Create a RunPod account and deploy a GPU pod (RTX 3090 recommended)
   - Attach a **network volume** (~25 GB) mounted at `/workspace` — persists between pod restarts
   - Expose port **8000** as an HTTP port
2. Open JupyterLab from the pod dashboard
3. In the terminal:

```bash
bash /workspace/setup_runpod.sh https://github.com/madebycharles/research_reader.git
```

This clones the repo, creates a venv on the network volume, and installs all dependencies with CUDA support.

### Starting the server (every session)

```bash
bash /workspace/research_reader/run_runpod.sh
```

This pulls the latest code from GitHub, activates the venv, and starts the server. Access via the RunPod HTTP proxy URL for port 8000.

### GitHub → RunPod pipeline

Any change committed and pushed to GitHub is automatically applied on the next pod startup — `run_runpod.sh` runs `git pull` before starting the server. No manual file uploads needed.

### Cost

| Resource | Price |
| -------- | ----- |
| RTX 3090 pod (on-demand) | ~$0.30–0.50 / hr |
| Network volume (25 GB) | ~$1.75 / month |

Spin the pod up to prepare papers, then terminate it. Data on the network volume (papers, voices, generated audio, venv, XTTS model cache) persists between sessions.

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

### Ready notifications

- **Android / desktop Chrome** — tap Prepare and allow notifications when prompted; a push notification fires when the job finishes
- **iPhone** — tap Share → Add to Home Screen to install as a PWA first; then tap the 🔔 bell in the progress bar to enable notifications

### Re-parsing existing papers

If you update the parser, tap the **↺** button on any paper card to re-parse it with the current parser. Cached audio is cleared automatically (paragraph indices may shift); you'll need to Prepare again after re-parsing.

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
├── main.py              — FastAPI app: all routes, batch prepare, reparse, logging
├── pdf_parser.py        — PDF parsing: 3-layer header/footer filtering, column detection,
│                          dehyphenation, citation stripping, section extraction
├── processor.py         — Text processing: acronym expansion, symbol normalisation, TTS chunking
├── tts_engine.py        — Coqui XTTS v2 wrapper: lazy load, speaker embedding cache,
│                          thread lock, torch.load patch
├── database.py          — SQLite: papers, voices, progress tables
├── requirements.txt     — Pinned dependencies
├── setup.bat            — One-time setup script (Windows)
├── run.bat              — Start server (Windows)
├── setup_runpod.sh      — One-time setup script (RunPod / Linux GPU)
├── run_runpod.sh        — Start server on RunPod (pulls latest code from GitHub)
├── static/
│   ├── index.html       — Mobile UI (library + reader screens)
│   ├── style.css        — Dark theme, mobile-first layout
│   └── app.js           — Player engine, library, voice management, notifications, log viewer
└── data/                — Runtime data (gitignored)
    ├── papers/          — Uploaded PDFs
    ├── voices/          — Voice WAV samples
    ├── audio/           — Generated audio chunks (cached)
    ├── reader.db        — SQLite database
    └── reader.log       — Server log
```

---

## PDF parsing pipeline

The parser operates in five passes over the raw PDF blocks:

1. **Block extraction** — uses PyMuPDF's dict-mode (`get_text("dict")`) to capture each text block with bounding box and per-span font size data
2. **Body font estimation** — computes the mode font size among substantial blocks; used as a baseline for small-text detection
3. **Rule-based classification** — labels each block as one of: `body`, `running_header`, `running_footer`, `publisher_note`, `affiliation`, or `figure_caption` based on:
   - Vertical position (top 7% / bottom 7% of page → header/footer candidate)
   - Pattern matching (copyright, DOI, received/accepted dates, emails, figure caption prefixes)
   - Font size relative to body (< 80% of body size + affiliation keywords → affiliation; small text in bottom 20% → publisher note)
4. **Cross-page repetition** — text normalised (digits replaced with `#`) appearing on 2+ pages in margin zones is confirmed as a running header or footer, catching journal names and page numbers that sit slightly outside the strict margin threshold
5. **Column-aware ordering** — body blocks are sorted top-to-bottom within each page, with left-column-first ordering applied for detected two-column layouts

Excluded content is collected in `ParsedPaper.metadata` and logged at upload/reparse time but never passed to TTS.

---

## API reference

### Papers

| Method   | Endpoint                    | Description                                     |
| -------- | --------------------------- | ----------------------------------------------- |
| `POST`   | `/api/papers/upload`        | Upload a PDF (multipart)                        |
| `GET`    | `/api/papers`               | List all papers                                 |
| `GET`    | `/api/papers/{id}`          | Get paper with full section/paragraph data      |
| `POST`   | `/api/papers/{id}/reparse`  | Re-parse stored PDF; clears audio cache         |
| `DELETE` | `/api/papers/{id}`          | Delete paper and its cached audio               |

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

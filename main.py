"""
Research Reader — FastAPI backend
"""

import asyncio
import json
import logging
import shutil
import threading
import traceback
import uuid
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import get_db, init_db
from pdf_parser import parse_pdf
from processor import chunk_text, is_boilerplate, prepare_for_tts
from tts_engine import engine as tts_engine

# ---------------------------------------------------------------------------
# Logging — writes to console AND data/reader.log
# ---------------------------------------------------------------------------
Path("data").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/reader.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("research_reader")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Research Reader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    log.error("Unhandled error on %s %s\n%s", request.method, request.url.path, tb)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )

DATA_DIR   = Path("data")
PAPERS_DIR = DATA_DIR / "papers"
VOICES_DIR = DATA_DIR / "voices"
AUDIO_DIR  = DATA_DIR / "audio"


@app.on_event("startup")
async def startup():
    for d in (DATA_DIR, PAPERS_DIR, VOICES_DIR, AUDIO_DIR):
        d.mkdir(parents=True, exist_ok=True)
    init_db()


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/audio",  StaticFiles(directory="data/audio"),  name="audio")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("static/index.html")


# ---------------------------------------------------------------------------
# Papers
# ---------------------------------------------------------------------------

@app.post("/api/papers/upload")
async def upload_paper(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")

    paper_id = uuid.uuid4().hex[:8]
    pdf_path = PAPERS_DIR / f"{paper_id}.pdf"

    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, parse_pdf, str(pdf_path))
    except Exception as exc:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(500, f"PDF parsing failed: {exc}")

    sections_data = [
        {"title": s.title, "paragraphs": s.paragraphs}
        for s in parsed.sections
    ]

    with get_db() as db:
        db.execute(
            "INSERT INTO papers (id, title, filename, sections, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (paper_id, parsed.title, file.filename,
             json.dumps(sections_data), datetime.now().isoformat()),
        )

    return {
        "paper_id":     paper_id,
        "title":        parsed.title,
        "section_count": len(sections_data),
        "sections": [
            {
                "index":           i,
                "title":           s["title"],
                "paragraph_count": len(s["paragraphs"]),
                "is_boilerplate":  is_boilerplate(s["title"]),
            }
            for i, s in enumerate(sections_data)
        ],
    }


@app.get("/api/papers")
async def list_papers():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, title, filename, created_at, sections "
            "FROM papers ORDER BY created_at DESC"
        ).fetchall()

    return [
        {
            "paper_id":      r["id"],
            "title":         r["title"],
            "filename":      r["filename"],
            "created_at":    r["created_at"],
            "section_count": len(json.loads(r["sections"])),
        }
        for r in rows
    ]


@app.get("/api/papers/{paper_id}")
async def get_paper(paper_id: str):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()

    if not row:
        raise HTTPException(404, "Paper not found.")

    sections = json.loads(row["sections"])
    return {
        "paper_id": row["id"],
        "title":    row["title"],
        "sections": [
            {
                "index":           i,
                "title":           s["title"],
                "paragraphs":      s["paragraphs"],
                "paragraph_count": len(s["paragraphs"]),
                "is_boilerplate":  is_boilerplate(s["title"]),
            }
            for i, s in enumerate(sections)
        ],
    }


@app.delete("/api/papers/{paper_id}")
async def delete_paper(paper_id: str):
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found.")
        db.execute("DELETE FROM papers   WHERE id       = ?", (paper_id,))
        db.execute("DELETE FROM progress WHERE paper_id = ?", (paper_id,))

    (PAPERS_DIR / f"{paper_id}.pdf").unlink(missing_ok=True)
    for f in AUDIO_DIR.glob(f"{paper_id}_*"):
        f.unlink(missing_ok=True)

    return {"message": "Paper deleted."}


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

@app.post("/api/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
):
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "Please upload a WAV file.")

    voice_id = uuid.uuid4().hex[:8]
    wav_path = VOICES_DIR / f"{voice_id}.wav"

    with open(wav_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with get_db() as db:
        db.execute(
            "INSERT INTO voices (id, name, filename, created_at) VALUES (?, ?, ?, ?)",
            (voice_id, name.strip(), file.filename, datetime.now().isoformat()),
        )

    return {"voice_id": voice_id, "name": name.strip()}


@app.post("/api/voices/{voice_id}/test")
async def test_voice(voice_id: str):
    """Generate a short phrase with the cloned voice to verify it works."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM voices WHERE id = ?", (voice_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Voice not found.")

    wav_path   = VOICES_DIR / f"{voice_id}.wav"
    out_path   = AUDIO_DIR  / f"test_{voice_id}.wav"
    test_text  = ("Hello. This is a test of your cloned voice. "
                  "If this sounds right, you are good to go.")

    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            partial(tts_engine.generate, test_text, str(wav_path), str(out_path)),
        )
    except Exception as exc:
        raise HTTPException(500, f"TTS generation failed: {exc}")

    return {"audio_url": f"/audio/test_{voice_id}.wav"}


@app.get("/api/voices")
async def list_voices():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, name, created_at FROM voices ORDER BY created_at DESC"
        ).fetchall()
    return [
        {"voice_id": r["id"], "name": r["name"], "created_at": r["created_at"]}
        for r in rows
    ]


@app.delete("/api/voices/{voice_id}")
async def delete_voice(voice_id: str):
    with get_db() as db:
        row = db.execute(
            "SELECT id FROM voices WHERE id = ?", (voice_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Voice not found.")
        db.execute("DELETE FROM voices WHERE id = ?", (voice_id,))

    (VOICES_DIR / f"{voice_id}.wav").unlink(missing_ok=True)
    return {"message": "Voice deleted."}


# ---------------------------------------------------------------------------
# TTS generation
# ---------------------------------------------------------------------------

@app.post("/api/tts/generate")
async def generate_tts(
    paper_id:      str,
    voice_id:      str,
    section_idx:   int,
    paragraph_idx: int,
):
    # Validate paper and voice
    with get_db() as db:
        paper = db.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        voice = db.execute(
            "SELECT id FROM voices WHERE id = ?", (voice_id,)
        ).fetchone()

    if not paper:
        raise HTTPException(404, "Paper not found.")
    if not voice:
        raise HTTPException(404, "Voice not found.")

    sections = json.loads(paper["sections"])
    if section_idx >= len(sections):
        raise HTTPException(400, "Section index out of range.")

    section = sections[section_idx]
    if paragraph_idx >= len(section["paragraphs"]):
        raise HTTPException(400, "Paragraph index out of range.")

    paragraph = section["paragraphs"][paragraph_idx]

    # Build TTS-ready text
    acronym_seen: set = set()  # fresh per request; session tracking is a Sprint 5 item
    prepared = prepare_for_tts(
        section["title"],
        paragraph,
        is_first_paragraph=(paragraph_idx == 0),
        acronym_seen=acronym_seen,
    )

    chunks = chunk_text(prepared)
    if not chunks:
        raise HTTPException(400, "No speakable text in this paragraph.")

    wav_path = VOICES_DIR / f"{voice_id}.wav"
    prefix   = f"{paper_id}_{voice_id}_{section_idx}_{paragraph_idx}"

    # Generate each chunk (skip if cached)
    audio_urls: List[str] = []
    loop = asyncio.get_event_loop()

    for i, chunk in enumerate(chunks):
        out_path = AUDIO_DIR / f"{prefix}_{i:04d}.wav"

        if not out_path.exists():
            try:
                await loop.run_in_executor(
                    None,
                    partial(tts_engine.generate, chunk, str(wav_path), str(out_path)),
                )
            except Exception as exc:
                raise HTTPException(500, f"TTS failed on chunk {i}: {exc}")

        audio_urls.append(f"/audio/{out_path.name}")

    return {
        "audio_urls":    audio_urls,
        "chunk_count":   len(audio_urls),
        "section_title": section["title"],
        "paragraph_idx": paragraph_idx,
    }


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

@app.get("/api/progress/{paper_id}")
async def get_progress(paper_id: str):
    with get_db() as db:
        row = db.execute(
            "SELECT section_idx, paragraph_idx FROM progress WHERE paper_id = ?",
            (paper_id,),
        ).fetchone()

    if not row:
        return {"section_idx": 0, "paragraph_idx": 0}

    return {"section_idx": row["section_idx"], "paragraph_idx": row["paragraph_idx"]}


@app.post("/api/progress/{paper_id}")
async def save_progress(paper_id: str, section_idx: int, paragraph_idx: int):
    with get_db() as db:
        db.execute(
            """INSERT INTO progress (paper_id, section_idx, paragraph_idx, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(paper_id) DO UPDATE SET
                   section_idx   = excluded.section_idx,
                   paragraph_idx = excluded.paragraph_idx,
                   updated_at    = excluded.updated_at""",
            (paper_id, section_idx, paragraph_idx, datetime.now().isoformat()),
        )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def status():
    return {
        "model_loaded": tts_engine.is_loaded,
        "device":       tts_engine.device,
    }


# ---------------------------------------------------------------------------
# Batch preparation (pre-generate all audio before listening)
# ---------------------------------------------------------------------------

# In-memory job tracker — resets on server restart, filesystem is source of truth
_prepare_jobs: dict = {}


def _count_generated(paper_id: str, voice_id: str, sections: list) -> tuple:
    """Count (generated_paragraphs, total_non_boilerplate_paragraphs) from cached files."""
    total = generated = 0
    for si, section in enumerate(sections):
        if is_boilerplate(section["title"]):
            continue
        for pi in range(len(section["paragraphs"])):
            total += 1
            if (AUDIO_DIR / f"{paper_id}_{voice_id}_{si}_{pi}_0000.wav").exists():
                generated += 1
    return generated, total


def _prepare_worker(job_key: str, paper_id: str, voice_id: str, sections: list):
    job = _prepare_jobs[job_key]
    wav_path = VOICES_DIR / f"{voice_id}.wav"
    acronym_seen: set = set()

    for si, section in enumerate(sections):
        if is_boilerplate(section["title"]):
            continue
        if job.get("cancelled"):
            break
        for pi, paragraph in enumerate(section["paragraphs"]):
            if job.get("cancelled"):
                break
            prepared = prepare_for_tts(section["title"], paragraph, pi == 0, acronym_seen)
            chunks   = chunk_text(prepared)
            for i, chunk in enumerate(chunks):
                out = AUDIO_DIR / f"{paper_id}_{voice_id}_{si}_{pi}_{i:04d}.wav"
                if not out.exists():
                    try:
                        tts_engine.generate(chunk, str(wav_path), str(out))
                    except Exception as exc:
                        job["errors"] += 1
                        log.error("Prepare %s §%d¶%d: %s", paper_id, si, pi, exc, exc_info=True)
            job["done"] += 1

    job["status"] = "cancelled" if job.get("cancelled") else "done"
    log.info("Prepare %s done — %d paragraphs, %d errors.", paper_id, job["done"], job["errors"])


@app.post("/api/papers/{paper_id}/prepare")
async def prepare_paper(paper_id: str, voice_id: str):
    with get_db() as db:
        paper = db.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        voice = db.execute("SELECT id FROM voices WHERE id = ?", (voice_id,)).fetchone()

    if not paper:
        raise HTTPException(404, "Paper not found.")
    if not voice:
        raise HTTPException(404, "Voice not found.")

    sections  = json.loads(paper["sections"])
    job_key   = f"{paper_id}_{voice_id}"
    existing  = _prepare_jobs.get(job_key)

    if existing and existing.get("status") == "running":
        return {"status": "already_running", "done": existing["done"], "total": existing["total"]}

    total = sum(
        len(s["paragraphs"]) for s in sections if not is_boilerplate(s["title"])
    )

    # Count what's already cached so progress starts correctly
    generated, _ = _count_generated(paper_id, voice_id, sections)

    _prepare_jobs[job_key] = {
        "status": "running",
        "done":   generated,   # resume from where cache left off
        "total":  total,
        "errors": 0,
    }

    threading.Thread(
        target=_prepare_worker,
        args=(job_key, paper_id, voice_id, sections),
        daemon=True,
    ).start()

    return {"status": "started", "total": total, "already_done": generated}


@app.get("/api/papers/{paper_id}/prepare/status")
async def prepare_status(paper_id: str, voice_id: str):
    with get_db() as db:
        paper = db.execute("SELECT sections FROM papers WHERE id = ?", (paper_id,)).fetchone()
    if not paper:
        raise HTTPException(404, "Paper not found.")

    sections            = json.loads(paper["sections"])
    generated, total    = _count_generated(paper_id, voice_id, sections)
    job                 = _prepare_jobs.get(f"{paper_id}_{voice_id}")

    if job:
        job_status = job["status"]
        errors     = job["errors"]
    else:
        # Derive from filesystem (survives server restarts)
        job_status = "done" if (total > 0 and generated >= total) else "idle"
        errors     = 0

    return {
        "status":    job_status,
        "done":      generated,
        "total":     total,
        "errors":    errors,
        "ready":     total > 0 and generated >= total,
    }


# ---------------------------------------------------------------------------
# Log viewer
# ---------------------------------------------------------------------------

@app.get("/api/log")
async def get_log(lines: int = 60):
    log_path = DATA_DIR / "reader.log"
    if not log_path.exists():
        return {"lines": ["No log file yet."]}
    with open(log_path, encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"lines": [l.rstrip() for l in all_lines[-lines:]]}

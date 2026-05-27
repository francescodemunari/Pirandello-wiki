"""TTS locale gratuito: clonazione voce con Coqui XTTS v2 (nessun abbonamento)."""

from __future__ import annotations

import asyncio
import hashlib
import re
import subprocess
import sys
import threading
from pathlib import Path

from loguru import logger

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BACKEND_ROOT / "outputs"
MIN_VALID_WAV_BYTES = 44

_tts_model = None
_device = None
_engine_lock = threading.Lock()
_worker_proc: subprocess.Popen | None = None
_worker_lock = threading.Lock()

_cached_gpt_cond_latent = None
_cached_speaker_embedding = None


TTS_CHUNK_MAX_CHARS = 200


def _split_into_chunks(text: str, max_chars: int = TTS_CHUNK_MAX_CHARS) -> list[str]:
    sentences = re.split(r'(?<=[.!?;:])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if not s.strip():
            continue
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            # If a single sentence exceeds max_chars, force-split it
            while len(s) > max_chars:
                chunks.append(s[:max_chars])
                s = s[max_chars:]
            current = s
    if current:
        chunks.append(current)
    return chunks


def clean_text_for_tts(text: str) -> str:
    """Rimuove markdown per una sintesi pulita."""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = text.rstrip(".")
    return text.strip()


def _lock_for(path: Path) -> asyncio.Lock:
    if not hasattr(_lock_for, "_locks"):
        _lock_for._locks: dict[str, asyncio.Lock] = {}
    key = str(path)
    if key not in _lock_for._locks:
        _lock_for._locks[key] = asyncio.Lock()
    return _lock_for._locks[key]


def _is_valid_wav(filepath: Path) -> bool:
    try:
        if not filepath.is_file():
            return False
        if filepath.stat().st_size < MIN_VALID_WAV_BYTES:
            return False
        with filepath.open("rb") as f:
            header = f.read(12)
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    except OSError:
        return False


def _resolve_reference_wav() -> Path:
    from backend.config import TTS_REFERENCE_WAV

    ref = Path(TTS_REFERENCE_WAV)
    if ref.is_file():
        return ref

    raise FileNotFoundError(
        f"Audio di riferimento voce non trovato: {ref}\n"
        "Esegui: py -3.11 backend/scripts/prepare_pirandello_ref.py\n"
        "(serve ffmpeg e l'MP3 di Pirandello nella root del progetto)"
    )


def _use_subprocess_worker() -> bool:
    """Coqui TTS richiede Python < 3.12; su 3.12+ usiamo worker 3.11."""
    return sys.version_info >= (3, 12)


def _get_python311_cmd() -> list[str]:
    from backend.config import TTS_PYTHON

    parts = TTS_PYTHON.split()
    return parts if parts else ["py", "-3.11"]


def _ensure_inprocess_model():
    global _tts_model, _device, _cached_gpt_cond_latent, _cached_speaker_embedding
    if _tts_model is not None:
        return _tts_model, _device

    with _engine_lock:
        if _tts_model is not None:
            return _tts_model, _device

        import os

        os.environ.setdefault("COQUI_TOS_AGREED", "1")

        from backend.agent.ffmpeg_path import ensure_ffmpeg_on_path

        ensure_ffmpeg_on_path()
        import TTS.utils.io as tts_io
        import torch

        _orig_load = tts_io.load_fsspec
        def _patched_load(path, map_location=None, cache=True, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _orig_load(path, map_location=map_location, cache=cache, **kwargs)
        tts_io.load_fsspec = _patched_load

        from TTS.api import TTS

        from backend.config import TTS_USE_GPU

        if TTS_USE_GPU == "cpu":
            _device = "cpu"
        elif TTS_USE_GPU == "cuda":
            _device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            _device = "cuda" if torch.cuda.is_available() else "cpu"

        from backend.agent.xtts_cache import ensure_xtts_cached

        logger.info("Caricamento XTTS v2 su {}...", _device)
        ensure_xtts_cached()
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(_device)
        logger.info("XTTS v2 pronto.")

        try:
            ref = _resolve_reference_wav()
            model = _tts_model.synthesizer.tts_model
            _cached_gpt_cond_latent, _cached_speaker_embedding = model.get_conditioning_latents(
                audio_path=str(ref),
                gpt_cond_len=30,
                gpt_cond_chunk_len=6,
                max_ref_length=10,
                sound_norm_refs=False,
            )
            logger.info("Speaker embedding pre-calcolata e cachet.")
        except Exception as e:
            logger.warning("Precalcolo speaker embedding non riuscito: {}", e)

        return _tts_model, _device


def _wait_worker_ready(proc: subprocess.Popen, timeout_sec: int = 900) -> dict:
    """Attende messaggi JSON dal worker; stderr va sulla console (evita deadlock)."""
    import json
    import time

    from backend.config import TTS_WORKER_TIMEOUT

    deadline = time.monotonic() + (TTS_WORKER_TIMEOUT or timeout_sec)
    if not proc.stdout:
        raise RuntimeError("Worker XTTS senza stdout")

    while True:
        if proc.poll() is not None:
            raise RuntimeError(
                f"Worker XTTS terminato prematuramente (exit code {proc.returncode}). "
                "Leggi i messaggi nella console sopra."
            )
        if time.monotonic() > deadline:
            proc.kill()
            raise TimeoutError(
                "Timeout avvio worker XTTS. Al primo avvio serve il download del modello "
                "(~1.8 GB). Riprova con connessione stabile o imposta TTS_PRELOAD=0 e "
                "attendi al primo messaggio vocale."
            )

        line = proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue

        try:
            status = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Worker XTTS output non-JSON: {}", line.strip())
            continue

        st = status.get("status")
        if st == "loading":
            logger.info("XTTS: {}", status.get("message", status))
            continue
        if st == "error":
            raise RuntimeError(status.get("error", "Errore worker XTTS"))
        if st == "ready":
            return status
        if status.get("ok") is False:
            raise RuntimeError(status.get("error", "Errore worker XTTS"))

        logger.warning("Worker XTTS messaggio ignorato: {}", status)


def _ensure_worker() -> subprocess.Popen:
    global _worker_proc
    if _worker_proc is not None and _worker_proc.poll() is None:
        return _worker_proc

    with _worker_lock:
        if _worker_proc is not None and _worker_proc.poll() is None:
            return _worker_proc

        script = BACKEND_ROOT / "scripts" / "xtts_worker.py"
        cmd = [*_get_python311_cmd(), str(script)]
        logger.info("Avvio worker XTTS: {}", " ".join(cmd))
        logger.info(
            "Al primo avvio il modello XTTS si scarica in background (~1.8 GB). "
            "I progressi compaiono in questa finestra."
        )
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )
        status = _wait_worker_ready(proc)
        _worker_proc = proc
        logger.info("Worker XTTS pronto (device={})", status.get("device"))
        return _worker_proc


def _synthesize_inprocess(clean_text: str, filepath: Path, ref_path: Path) -> None:
    from backend.config import TTS_LANG

    tts, _device = _ensure_inprocess_model()
    tts.tts_to_file(
        text=clean_text, file_path=str(filepath), speaker_wav=str(ref_path),
        language=TTS_LANG, split_sentences=True,
    )


def _synthesize_subprocess(clean_text: str, filepath: Path, ref_path: Path) -> None:
    import json
    import time

    from backend.config import TTS_LANG

    proc = _ensure_worker()
    req = {
        "text": clean_text,
        "out": str(filepath),
        "ref": str(ref_path),
        "lang": TTS_LANG,
    }
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()

    deadline = time.monotonic() + 120
    while True:
        if proc.poll() is not None:
            raise RuntimeError(f"Worker terminato (exit {proc.returncode})")
        if time.monotonic() > deadline:
            proc.kill()
            raise TimeoutError("Timeout risposta worker XTTS")

        line = proc.stdout.readline()
        if not line:
            continue

        resp = json.loads(line)
        if "ok" in resp:
            if not resp.get("ok"):
                raise RuntimeError(resp.get("error", "Errore worker XTTS"))
            return


def _concatenate_wavs(sources: list[Path], dest: Path) -> None:
    import wave
    frames = b""
    params = None
    for src in sources:
        with wave.open(str(src), "rb") as w:
            if params is None:
                params = w.getparams()
            frames += w.readframes(w.getnframes())
    with wave.open(str(dest), "wb") as out:
        if params:
            out.setparams(params)
        out.writeframes(frames)


def _synthesize_sync(clean_text: str, filepath: Path) -> None:
    ref_path = _resolve_reference_wav()
    chunks = _split_into_chunks(clean_text)

    def _synth(text: str, out: Path):
        if _use_subprocess_worker():
            _synthesize_subprocess(text, out, ref_path)
        else:
            _synthesize_inprocess(text, out, ref_path)

    if len(chunks) == 1:
        _synth(chunks[0], filepath)
        return

    logger.info("TTS diviso in {} chunks ({} caratteri totali)", len(chunks), len(clean_text))
    temp_files = []
    try:
        for i, chunk in enumerate(chunks):
            tmp = filepath.with_stem(f"{filepath.stem}_chunk{i}")
            _synth(chunk, tmp)
            temp_files.append(tmp)
        _concatenate_wavs(temp_files, filepath)
    finally:
        for p in temp_files:
            if p.exists():
                p.unlink()


def preload_tts_engine() -> None:
    """Precarica XTTS (modello o worker) per ridurre latenza al primo messaggio."""
    try:
        ref = _resolve_reference_wav()
        logger.info("Riferimento voce: {}", ref)
        if _use_subprocess_worker():
            _ensure_worker()
        else:
            _ensure_inprocess_model()
    except Exception as e:
        logger.warning("Precaricamento TTS non riuscito: {}", e)


async def generate_tts(text: str, session_id: str, voice: str | None = None) -> str:
    """
    Genera WAV con XTTS v2 (clonazione da pirandello_ref.wav).
    Restituisce URL web (/outputs/voice_...wav).
    """
    del voice

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        raise ValueError("Il testo per il TTS è vuoto dopo la pulizia.")

    text_hash = hashlib.md5(clean_text.encode("utf-8")).hexdigest()
    filename = f"voice_{session_id}_{text_hash}.wav"
    filepath = OUTPUT_DIR / filename

    async with _lock_for(filepath):
        if _is_valid_wav(filepath):
            logger.info("TTS cache hit: {}", filename)
            return f"/outputs/{filename}"

        if filepath.exists():
            try:
                filepath.unlink()
            except OSError:
                pass

        try:
            logger.info(
                "Sintesi XTTS per session {} ({} caratteri)...",
                session_id,
                len(clean_text),
            )
            await asyncio.to_thread(_synthesize_sync, clean_text, filepath)
            if not _is_valid_wav(filepath):
                raise ValueError(f"File audio generato non valido: {filename}")
            logger.info("TTS generato: {} ({} bytes)", filename, filepath.stat().st_size)
            return f"/outputs/{filename}"
        except Exception as e:
            if filepath.exists():
                try:
                    filepath.unlink()
                except OSError:
                    pass
            logger.error("Errore sintesi XTTS: {}", e)
            raise

"""Download e cache modello XTTS via Hugging Face (evita mirror Coqui scarf.sh)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from loguru import logger

MODEL_REPO = "coqui/XTTS-v2"
REQUIRED_FILES = ("model.pth", "config.json", "vocab.json")


def get_xtts_cache_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "tts" / "tts_models--multilingual--multi-dataset--xtts_v2"


def is_cache_complete(cache_dir: Path) -> bool:
    if not cache_dir.is_dir():
        return False
    return all((cache_dir / name).is_file() for name in REQUIRED_FILES)


def clear_xtts_cache() -> None:
    cache_dir = get_xtts_cache_dir()
    if cache_dir.exists():
        logger.warning("Rimozione cache XTTS incompleta: {}", cache_dir)
        shutil.rmtree(cache_dir, ignore_errors=True)


def ensure_xtts_cached(force_hf: bool = False) -> Path:
    """
    Scarica il modello da Hugging Face se mancante o incompleto.
    Utile dopo download interrotti (cache corrotta).
    """
    cache_dir = get_xtts_cache_dir()

    if is_cache_complete(cache_dir) and not force_hf:
        logger.info("Cache XTTS completa: {}", cache_dir)
        return cache_dir

    if cache_dir.exists():
        logger.warning("Cache XTTS incompleta, la ricreo: {}", cache_dir)
        shutil.rmtree(cache_dir, ignore_errors=True)

    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Download XTTS da Hugging Face ({}) → {}", MODEL_REPO, cache_dir)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise RuntimeError(
            "huggingface_hub mancante. Esegui: py -3.11 -m pip install huggingface_hub"
        ) from e

    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=str(cache_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    if not is_cache_complete(cache_dir):
        raise RuntimeError(
            f"Download XTTS incompleto in {cache_dir}. "
            "Riprova o esegui: py -3.11 backend/scripts/clear_xtts_cache.py"
        )

    logger.info("Download XTTS completato.")
    return cache_dir

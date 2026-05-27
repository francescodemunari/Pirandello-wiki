from pathlib import Path
from backend.config import WIKI_PATH

async def wiki_read(path: str) -> str:
    fpath = (WIKI_PATH / path).resolve()
    if not str(fpath).startswith(str(WIKI_PATH.resolve())):
        raise ValueError("Accesso negato: percorso fuori dalla wiki")
    if not fpath.exists():
        raise FileNotFoundError(f"Pagina non trovata: {path}")
    return fpath.read_text(encoding="utf-8")

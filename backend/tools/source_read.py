from backend.config import RAW_PATH

async def source_read(path: str) -> str:
    fpath = (RAW_PATH / path).resolve()
    if not str(fpath).startswith(str(RAW_PATH.resolve())):
        raise ValueError("Accesso negato: percorso fuori da raw/")
    if not fpath.exists():
        raise FileNotFoundError(f"File non trovato: {path}")
    if fpath.suffix not in (".txt", ".md"):
        raise ValueError(f"Formato non supportato: {fpath.suffix}. Usa .txt o .md")
    return fpath.read_text(encoding="utf-8")

"""Elimina cache XTTS corrotta (dopo download interrotto)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.agent.xtts_cache import clear_xtts_cache, get_xtts_cache_dir

if __name__ == "__main__":
    path = get_xtts_cache_dir()
    print(f"Rimozione: {path}")
    clear_xtts_cache()
    print("OK. Al prossimo avvio il modello si riscarica da Hugging Face.")

"""Worker XTTS su Python 3.11 (usato dal backend se Python >= 3.12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Path progetto per import backend.agent.xtts_cache
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import os

os.environ.setdefault("COQUI_TOS_AGREED", "1")

# PyTorch ≥2.6 usa weights_only=True di default, ma TTS necessita di weights_only=False
# per caricare checkpoint con classi custom. Applichiamo una patch al caricatore TTS.
def _patch_tts_io():
    import TTS.utils.io as tts_io
    import torch
    _orig_load = tts_io.load_fsspec

    def _patched_load(path, map_location=None, cache=True, **kwargs):
        kwargs.setdefault("weights_only", False)
        return _orig_load(path, map_location=map_location, cache=cache, **kwargs)

    tts_io.load_fsspec = _patched_load

_patch_tts_io()


def _emit(payload: dict) -> None:
    print(json.dumps(payload), flush=True)


def _load_tts_model():
    """Carica XTTS; stdout di Coqui → stderr per non rompere il protocollo JSON."""
    _emit({"status": "loading", "message": "Avvio worker TTS (import librerie)..."})

    from backend.agent.ffmpeg_path import ensure_ffmpeg_on_path

    ensure_ffmpeg_on_path()
    import torch

    _emit(
        {
            "status": "loading",
            "message": f"PyTorch OK — device cuda={torch.cuda.is_available()}",
        }
    )

    from TTS.api import TTS

    from backend.agent.xtts_cache import ensure_xtts_cached

    _emit(
        {
            "status": "loading",
            "message": (
                "Verifica/download modello XTTS da Hugging Face (~1.8 GB al primo avvio). "
                "Vedi log in backend/logs/backend.log"
            ),
        }
    )

    ensure_xtts_cached()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    finally:
        sys.stdout = real_stdout

    return tts, device


def main() -> int:
    try:
        tts, device = _load_tts_model()
    except Exception as e:
        _emit({"status": "error", "error": f"Caricamento XTTS fallito: {e}"})
        return 1

    _emit({"status": "ready", "device": device})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            text = req.get("text", "")
            out = Path(req["out"])
            ref = req["ref"]
            lang = req.get("lang", "it")
            out.parent.mkdir(parents=True, exist_ok=True)

            real_stdout = sys.stdout
            sys.stdout = sys.stderr
            try:
                tts.tts_to_file(
                    text=text, file_path=str(out), speaker_wav=ref,
                    language=lang, split_sentences=False,
                )
            finally:
                sys.stdout = real_stdout

            _emit({"ok": True})
        except Exception as e:
            _emit({"ok": False, "error": str(e)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

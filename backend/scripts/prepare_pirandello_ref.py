"""
Converte l'MP3 storico in WAV mono per XTTS (clonazione gratuita, locale).

Uso:
  py -3.11 backend/scripts/prepare_pirandello_ref.py
  py -3.11 backend/scripts/prepare_pirandello_ref.py --input "percorso/registrazione.mp3"
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = BACKEND_ROOT / "voices" / "pirandello_ref.wav"


def find_source_audio() -> Path | None:
    preferred = PROJECT_ROOT / "audio_pirandello.wav"
    if preferred.is_file():
        return preferred
    for pattern in ("*.wav", "*.mp3"):
        for p in sorted(PROJECT_ROOT.glob(pattern)):
            if p.name.lower() != "pirandello_ref.wav":
                return p
    for pattern in ("*.mp3", "*.wav"):
        for p in (BACKEND_ROOT / "assets" / "audio").glob(pattern):
            return p
    return None


def convert_with_ffmpeg(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-ac",
        "1",
        "-ar",
        "22050",
        "-af",
        "highpass=f=80,lowpass=f=8000,loudnorm=I=-16:TP=-1.5:LRA=11",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        help="MP3/WAV sorgente (default: audio_pirandello.wav o primo audio in root)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    src = args.input or find_source_audio()
    if not src or not src.is_file():
        print(
            "Nessun file audio trovato. Metti audio_pirandello.wav nella root "
            "oppure passa --input percorso/file",
            file=sys.stderr,
        )
        return 1

    if not shutil.which("ffmpeg"):
        print("ffmpeg non trovato nel PATH. Installalo (es. winget install ffmpeg).", file=sys.stderr)
        return 1

    print(f"Sorgente: {src}")
    print(f"Output:   {args.output}")
    convert_with_ffmpeg(src, args.output)
    print("OK — usa questo file come riferimento voce (TTS_REFERENCE_WAV).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

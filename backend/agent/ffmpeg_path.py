from __future__ import annotations

import os
from pathlib import Path


def ensure_ffmpeg_on_path() -> None:
    """Aggiunge il path delle DLL FFmpeg shared a PATH e DLL directory."""
    base = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages"
    candidates = list(base.glob("Gyan.FFmpeg.Shared*/ffmpeg-*-full_build-shared/bin"))
    if candidates:
        bin_dir = str(candidates[0])
        if bin_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(bin_dir)
        except AttributeError:
            pass

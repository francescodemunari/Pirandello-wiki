# Voce Pirandello (gratuita, locale — XTTS v2)

Nessun abbonamento: la voce si clona dal file audio storico con [Coqui XTTS v2](https://github.com/coqui-ai/TTS).

## Setup (una volta)

1. Metti `audio_pirandello.wav` (o un MP3) nella **root** del progetto. `start_backend.bat` lo converte automaticamente in `pirandello_ref.wav` al primo avvio.
2. Installa **ffmpeg** (`winget install Gyan.FFmpeg`).
3. Genera il riferimento voce:

   ```powershell
   py -3.11 -m pip install -r backend/requirements-tts.txt
   py -3.11 backend/scripts/prepare_pirandello_ref.py
   ```

   Crea `backend/voices/pirandello_ref.wav` (mono, ripulito).

4. Riavvia il backend con `start_backend.bat`.

**Download interrotto?** Esegui `clear_xtts_cache.bat` poi riavvia (cancella cache corrotta in `%LOCALAPPDATA%\tts\`).

**Log backend:** `backend/logs/backend.log` (tutto ciò che vedi in console + dettagli debug).

Alla prima sintesi XTTS scarica il modello (~1,8 GB). Serve **Python 3.11** per il motore TTS (il bat lo installa automaticamente).

## Variabili `.env` (opzionali)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `TTS_REFERENCE_WAV` | `backend/voices/pirandello_ref.wav` | Clip di riferimento (~6–47 s) |
| `TTS_LANG` | `it` | Lingua sintesi |
| `TTS_USE_GPU` | `auto` | `cuda` / `cpu` / `auto` |
| `TTS_PRELOAD` | `0` | `1` = precarica in background all’avvio |
| `COQUI_TOS_AGREED` | `1` (in bat) | Obbligatorio: evita blocco su prompt licenza |
| `TTS_PYTHON` | `py -3.11` | Se il backend usa Python 3.12+ |

## Qualità

- Meglio un segmento **pulito** (poco rumore) anche se corto (~10 s).
- Su **CPU** la sintesi è lenta; con **GPU NVIDIA** è molto più rapida.
- Licenza modello: [Coqui CPML](https://coqui.ai/cpml) (uso ricerca/educativo in genere ok).

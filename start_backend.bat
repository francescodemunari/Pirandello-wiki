@echo off
cd /d "%~dp0"
set COQUI_TOS_AGREED=1
echo Installing backend dependencies...
cd backend
pip install -r requirements.txt >nul 2>&1
echo Installing TTS (XTTS) on Python 3.11...
py -3.11 -m pip install -r requirements-tts.txt >nul 2>&1
cd ..
if not exist "backend\voices\pirandello_ref.wav" (
  if exist "audio_pirandello.wav" (
    echo Preparing voice reference from audio_pirandello.wav...
    py -3.11 backend\scripts\prepare_pirandello_ref.py --input audio_pirandello.wav
  )
)
echo Starting Pirandello Chatbot Backend...
echo Health: http://localhost:8000/health
echo TTS: XTTS v2 — reference: backend\voices\pirandello_ref.wav
python backend/main.py
pause

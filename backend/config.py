import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- General ---
PORT = int(os.getenv("PORT", "8000"))
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = Path(__file__).resolve().parent
WIKI_PATH = (PROJECT_ROOT / os.getenv("WIKI_PATH", "wiki")).resolve()
RAW_PATH = PROJECT_ROOT / "raw"

# --- Legacy LM Studio (fallback) ---
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "")

# --- Active provider ---
ACTIVE_PROVIDER = os.getenv("ACTIVE_PROVIDER", "lm_studio")

# --- Provider configurations ---
PROVIDERS_CONFIG = {}

# LM Studio
PROVIDERS_CONFIG["lm_studio"] = {
    "display_name": "LM Studio",
    "api_url": os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
    "model": os.getenv("LM_STUDIO_MODEL", ""),
    "api_key": "",
}
# Ollama
PROVIDERS_CONFIG["ollama"] = {
    "display_name": "Ollama",
    "api_url": os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
    "model": os.getenv("OLLAMA_MODEL", "llama3.2"),
    "api_key": "",
}
# llama.cpp
PROVIDERS_CONFIG["llamacpp"] = {
    "display_name": "llama.cpp",
    "api_url": os.getenv("LLAMACPP_URL", "http://localhost:8080/v1"),
    "model": os.getenv("LLAMACPP_MODEL", ""),
    "api_key": "",
}
# OpenAI
PROVIDERS_CONFIG["openai"] = {
    "display_name": "OpenAI",
    "api_url": "https://api.openai.com/v1",
    "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
    "api_key": os.getenv("OPENAI_API_KEY", ""),
}
# OpenRouter
PROVIDERS_CONFIG["openrouter"] = {
    "display_name": "OpenRouter",
    "api_url": "https://openrouter.ai/api/v1",
    "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o"),
    "api_key": os.getenv("OPENROUTER_API_KEY", ""),
}
# Anthropic
PROVIDERS_CONFIG["anthropic"] = {
    "display_name": "Anthropic",
    "api_url": "https://api.anthropic.com/v1",
    "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
}
# Google
PROVIDERS_CONFIG["google"] = {
    "display_name": "Google Gemini",
    "api_url": os.getenv("GOOGLE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
    "model": os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
    "api_key": os.getenv("GOOGLE_API_KEY", ""),
}

# Load custom provider overrides from env JSON (optional)
_custom_providers_raw = os.getenv("CUSTOM_PROVIDERS", "")
if _custom_providers_raw:
    try:
        custom = json.loads(_custom_providers_raw)
        for name, cfg in custom.items():
            PROVIDERS_CONFIG[name] = cfg
    except json.JSONDecodeError:
        pass

# File per persistenza configurazioni runtime dei provider
PROVIDERS_STATE_FILE = BACKEND_ROOT / "providers_state.json"

# Mappa nome provider → variabile d'ambiente per API key
PROVIDER_ENV_KEYS = {
    "lm_studio": None,
    "ollama": None,
    "llamacpp": None,
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

# Per-provider settings overrides
PROVIDER_SETTINGS = {
    name: {
        "temperature": float(os.getenv(f"{name.upper()}_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv(f"{name.upper()}_MAX_TOKENS", "4096")),
        "enabled": os.getenv(f"{name.upper()}_ENABLED", "true").lower() in ("1", "true", "yes"),
    }
    for name in list(PROVIDERS_CONFIG.keys())
}

# --- TTS (XTTS v2) ---
TTS_REFERENCE_WAV = os.getenv(
    "TTS_REFERENCE_WAV",
    str(BACKEND_ROOT / "voices" / "pirandello_ref.wav"),
)
TTS_LANG = os.getenv("TTS_LANG", "it")
TTS_USE_GPU = os.getenv("TTS_USE_GPU", "auto").lower()
TTS_PRELOAD = os.getenv("TTS_PRELOAD", "1").lower() in ("1", "true", "yes")
TTS_WORKER_TIMEOUT = int(os.getenv("TTS_WORKER_TIMEOUT", "900"))
TTS_PYTHON = os.getenv("TTS_PYTHON", "py -3.11")

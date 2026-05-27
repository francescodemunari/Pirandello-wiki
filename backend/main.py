import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.logging_setup import setup_logging

_log_path = setup_logging()

import uvicorn
from backend.config import PORT, WIKI_PATH, TTS_PRELOAD
from backend.agent import provider_manager
from backend.memory.chat_history import init_db
from backend.memory.user_memory import sync_memory_to_disk
from backend.memory.vector import index_wiki
from backend.web.server import socket_app
import asyncio

async def startup():
    provider_info = provider_manager.get_provider_info()
    active_name = provider_info["active"]
    active_cfg = provider_info["providers"].get(active_name, {})
    print(f"  Pirandello Chatbot + Wiki Manager")
    print(f"  Provider: {active_cfg.get('display_name', active_name)}")
    print(f"  Modello:  {active_cfg.get('model', 'predefinito')}")
    print(f"  Wiki:   {WIKI_PATH}")
    print(f"  Porta:  {PORT}")
    print(f"  Server: http://localhost:{PORT}")
    print(f"  Health: http://localhost:{PORT}/health")
    print(f"  Log:    {_log_path}")
    print()
    await init_db()
    sync_memory_to_disk()
    index_wiki()
    if TTS_PRELOAD:
        print("  TTS: precaricamento XTTS in background (server già raggiungibile)...")

        async def _bg_preload():
            from backend.agent.tts import preload_tts_engine
            await asyncio.to_thread(preload_tts_engine)

        asyncio.create_task(_bg_preload())

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(startup())
    uvicorn.run(
        socket_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        ws_ping_interval=25,
        ws_ping_timeout=120,
    )

if __name__ == "__main__":
    main()

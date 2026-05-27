import socketio
import base64
import uuid
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

logger = logging.getLogger(__name__)

from backend.config import RAW_PATH, WIKI_PATH
from backend.agent.core import chat_with_pirandello
from backend.agent.wiki_agent import wiki_agent_loop
from backend.agent import provider_manager
from backend.memory import chat_history as db

from fastapi.responses import FileResponse
from pathlib import Path

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=120,
)
app = FastAPI(title="Pirandello Chatbot + Wiki Manager")

BACKEND_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BACKEND_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize provider manager
provider_manager.init_providers()


@app.get("/outputs/{filename}")
async def serve_output_audio(filename: str):
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Not found")
    path = OUTPUT_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    suffix = path.suffix.lower()
    media = "audio/wav" if suffix == ".wav" else "audio/mpeg"
    return FileResponse(
        path,
        media_type=media,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_store = {}

@sio.event
async def connect(sid, environ, auth=None):
    logger.info(
        "Socket connect sid=%s query=%s",
        sid,
        environ.get("QUERY_STRING", ""),
    )
    query_params = environ.get("QUERY_STRING", "")
    params = {}
    for part in query_params.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    session_id = params.get("session_id", str(uuid.uuid4()))
    session_store[sid] = {"session_id": session_id}
    await sio.emit("session_ready", {"session_id": session_id}, to=sid)

@sio.event
async def disconnect(sid):
    logger.info("Socket disconnect sid=%s", sid)
    session_store.pop(sid, None)

@sio.event
async def chat_message(sid, data):
    session_data = session_store.get(sid, {})
    session_id = data.get("session_id") or session_data.get("session_id", "default")
    
    if sid in session_store:
        session_store[sid]["session_id"] = session_id

    message = data.get("message", "")
    mode = data.get("mode", "pirandello")
    # Optional provider override per message
    provider_override = data.get("provider") or None
    
    if not message.strip():
        return

    history = await db.get_history(session_id, limit=6)

    generator = None
    if mode == "pirandello":
        generator = chat_with_pirandello(message, history, session_id, provider=provider_override)
    elif mode == "wiki":
        generator = wiki_agent_loop(message, history, provider=provider_override)

    if generator:
        import asyncio
        from backend.memory.summary import update_session_summary

        try:
            await db.save_message(session_id, "user", message, mode=mode)
            if mode == "pirandello":
                from backend.memory.user_memory import ingest_message_facts
                n = ingest_message_facts(message)
                if n:
                    await sio.emit("memory_updated", {"count": n}, to=sid)
        except Exception as e:
            logger.error("Errore salvataggio messaggio utente: %s", e)

        autovoice = bool(data.get("autovoice")) and mode == "pirandello"
        if autovoice:
            await sio.emit("assistant_preparing", {"session_id": session_id}, to=sid)

        full_text = ""
        try:
            async for chunk in generator:
                if chunk["type"] == "token":
                    full_text += chunk["content"]
                    if not autovoice:
                        await sio.emit(
                            "token",
                            {"token": chunk["content"], "session_id": session_id},
                            to=sid,
                        )
        except Exception as e:
            logger.error("Errore generazione risposta: %s", e, exc_info=True)
            err_type = type(e).__name__
            err_msg = str(e) or "Errore sconosciuto"
            err = f"⚠️ Errore ({err_type}): {err_msg}"
            full_text = err
            if not autovoice:
                await sio.emit("token", {"token": err, "session_id": session_id}, to=sid)

        try:
            if full_text.strip():
                await db.save_message(session_id, "assistant", full_text)
        except Exception as e:
            logger.error("Errore salvataggio risposta assistant: %s", e)

        asyncio.create_task(update_session_summary(session_id))

        async def _maybe_title():
            from backend.memory.chat_history import count_session_messages
            from backend.memory.session_titles import update_session_title

            n = await count_session_messages(session_id)
            if n == 2:
                new_title = await update_session_title(session_id)
                if new_title:
                    await sio.emit(
                        "session_updated",
                        {"id": session_id, "title": new_title},
                        to=sid,
                    )

        asyncio.create_task(_maybe_title())

        if autovoice:
            audio_url = None
            tts_error = None
            if full_text.strip():
                try:
                    from backend.agent.tts import generate_tts
                    audio_url = await generate_tts(full_text, session_id)
                except Exception as e:
                    tts_error = str(e)
                    logger.error("Autovoice TTS error: %s", e)
            await sio.emit(
                "assistant_ready",
                {
                    "session_id": session_id,
                    "text": full_text,
                    "audio_url": audio_url,
                    "tts_error": tts_error,
                },
                to=sid,
            )
            await sio.emit("done", {"session_id": session_id, "gated": True}, to=sid)
        else:
            await sio.emit("done", {"session_id": session_id}, to=sid)

@sio.on("get_sessions")
async def on_get_sessions(sid, data):
    data = data or {}
    session_mode = data.get("mode")
    search_q = data.get("q") or data.get("query")
    sessions = await db.get_sessions(mode=session_mode, query=search_q)
    await sio.emit(
        "sessions_list",
        {"sessions": sessions, "mode": session_mode, "q": search_q},
        to=sid,
    )

@sio.on("create_session")
async def on_create_session(sid, data):
    data = data or {}
    new_id = data.get("session_id") or str(uuid.uuid4())
    from backend.memory.session_titles import provisional_title

    raw_title = data.get("title") or ""
    title = provisional_title(raw_title) if raw_title else "Nuova conversazione"
    session_mode = data.get("mode") or "pirandello"
    await db.create_session(new_id, title, mode=session_mode)
    
    if sid in session_store:
        session_store[sid]["session_id"] = new_id
        
    await sio.emit(
        "session_created",
        {"id": new_id, "title": title, "mode": session_mode},
        to=sid,
    )

@sio.on("delete_session")
async def on_delete_session(sid, data):
    session_id = data.get("session_id")
    if session_id:
        await db.delete_session(session_id)
        await sio.emit("session_deleted", {"session_id": session_id}, to=sid)

@sio.on("get_session_messages")
async def on_get_session_messages(sid, data):
    session_id = data.get("session_id")
    if session_id:
        if sid in session_store:
            session_store[sid]["session_id"] = session_id
        history = await db.get_history(session_id, limit=100)
        await sio.emit("chat_history", {"messages": history, "session_id": session_id}, to=sid)

@sio.on("chat_history")
async def on_chat_history(sid, data):
    session_id = session_store.get(sid, {}).get("session_id", "default")
    history = await db.get_history(session_id, limit=100)
    await sio.emit("chat_history", {"messages": history, "session_id": session_id}, to=sid)

@sio.on("clear_history")
async def on_clear_history(sid, data):
    session_id = session_store.get(sid, {}).get("session_id", "default")
    await db.clear_history(session_id)
    await sio.emit("history_cleared", {"session_id": session_id}, to=sid)

async def _perform_hard_reset() -> dict:
    from backend.memory.user_memory import clear_all_facts

    deleted_sessions = await db.clear_all_sessions()
    cleared_facts = clear_all_facts()
    return {
        "status": "success",
        "hard_reset": True,
        "deleted_sessions": deleted_sessions,
        "cleared_facts": cleared_facts,
    }

@sio.on("clear_all_data")
async def on_clear_all_data(sid, data):
    data = data or {}
    if data.get("hard_reset"):
        result = await _perform_hard_reset()
        await sio.emit("all_data_cleared", result, to=sid)
        return
    session_mode = data.get("mode")
    deleted = await db.clear_all_sessions(mode=session_mode)
    await sio.emit(
        "all_data_cleared",
        {"mode": session_mode, "deleted_sessions": deleted},
        to=sid,
    )


async def _clear_all_sessions_api(mode: str | None = None, hard_reset: bool = False):
    if hard_reset:
        return await _perform_hard_reset()
    deleted = await db.clear_all_sessions(mode=mode)
    return {"status": "success", "deleted_sessions": deleted, "mode": mode}

@sio.on("request_tts")
async def on_request_tts(sid, data):
    message = data.get("message") or data.get("message_content") or ""
    session_id = data.get("session_id") or session_store.get(sid, {}).get("session_id", "default")
    if not message.strip():
        return
    try:
        from backend.agent.tts import generate_tts
        url = await generate_tts(message, session_id)
        await sio.emit("tts_ready", {"url": url, "path": url, "session_id": session_id}, to=sid)
    except Exception as e:
        import logging
        logging.error(f"TTS Socket error: {e}")
        await sio.emit("tts_error", {"error": str(e), "session_id": session_id}, to=sid)

@sio.event
async def upload_file(sid, data):
    filename = data.get("filename", "untitled.txt")
    file_data = data.get("file", "")
    if not file_data:
        await sio.emit("upload_result", {"error": "Nessun file ricevuto"}, to=sid)
        return
    try:
        decoded = base64.b64decode(file_data)
        dest = RAW_PATH / "articles" / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(decoded)
        await sio.emit("upload_result", {
            "success": True,
            "path": f"raw/articles/{filename}",
            "filename": filename,
        }, to=sid)
    except Exception as e:
        await sio.emit("upload_result", {"error": str(e)}, to=sid)

# --- Provider REST API ---

@app.get("/api/providers")
async def api_get_providers():
    info = provider_manager.get_provider_info()
    return info


@app.post("/api/providers/activate")
async def api_activate_provider(name: str):
    ok = provider_manager.set_active_provider(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Provider '{name}' not found")
    return {"status": "success", "active": name}


@app.post("/api/providers/config")
async def api_update_provider_config(name: str, config: dict):
    ok = provider_manager.update_provider_config(name, config)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to update provider config")
    return {"status": "success", "provider": name}

# --- Sessions REST API ---

@app.get("/api/sessions")
async def api_get_sessions(mode: str | None = None, q: str | None = None):
    sessions = await db.get_sessions(mode=mode, query=q)
    return {"sessions": sessions, "mode": mode, "q": q}


@app.post("/api/sessions")
async def api_create_session(
    session_id: str | None = None,
    title: str = "Nuova Conversazione",
    mode: str = "pirandello",
):
    new_id = session_id or str(uuid.uuid4())
    await db.create_session(new_id, title, mode=mode)
    return {"id": new_id, "title": title, "mode": mode}


@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    await db.delete_session(session_id)
    return {"status": "success", "session_id": session_id}


@app.delete("/api/sessions")
async def api_clear_all_sessions(mode: str | None = None, hard_reset: bool = False):
    return await _clear_all_sessions_api(mode=mode, hard_reset=hard_reset)


@app.get("/api/sessions/{session_id}/messages")
async def api_get_session_messages(session_id: str):
    history = await db.get_history(session_id, limit=200)
    return {"messages": history, "session_id": session_id}


@app.get("/api/memories")
async def api_get_memories():
    from backend.memory.user_memory import get_all_facts
    return {"memories": get_all_facts()}


@app.delete("/api/memories")
async def api_delete_memory(category: str, key: str):
    from backend.memory.user_memory import delete_fact
    if delete_fact(category, key):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Fact not found")


@app.get("/health")
async def health():
    from backend.config import TTS_REFERENCE_WAV, TTS_LANG

    wiki_count = len(list(WIKI_PATH.glob("pages/**/*.md"))) if WIKI_PATH.exists() else 0
    ref_path = Path(TTS_REFERENCE_WAV)
    provider_info = provider_manager.get_provider_info()
    active_name = provider_info["active"]
    active_cfg = provider_info["providers"].get(active_name, {})

    return {
        "status": "ok",
        "model": active_cfg.get("model", ""),
        "active_provider": active_name,
        "providers": {
            name: {
                "display_name": p["display_name"],
                "model": p["model"],
                "category": p["category"],
                "enabled": p["enabled"],
            }
            for name, p in provider_info["providers"].items()
        },
        "wiki_pages": wiki_count,
        "wiki_path": str(WIKI_PATH),
        "tts": {
            "engine": "xtts-v2",
            "lang": TTS_LANG,
            "reference_wav": str(ref_path),
            "voice_ready": ref_path.is_file(),
        },
    }


@app.post("/upload")
async def upload_rest(file: UploadFile = File(...)):
    dest = RAW_PATH / "articles" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    return {"success": True, "path": f"raw/articles/{file.filename}", "filename": file.filename}

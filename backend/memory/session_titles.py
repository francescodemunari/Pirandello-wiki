"""Titoli chat: provvisorio dal primo messaggio, definitivo via LLM dopo la prima risposta."""
from loguru import logger

from backend.agent.provider_manager import chat_once, get_active_provider_name
from backend.memory.chat_history import (
    get_session_title,
    get_title_context_messages,
    update_session_title as db_update_session_title,
)


def provisional_title(first_message: str) -> str:
    text = " ".join((first_message or "").strip().split())
    if not text:
        return "Nuova conversazione"
    if len(text) > 42:
        return text[:42].rstrip() + "…"
    return text


async def update_session_title(session_id: str) -> str | None:
    """
    Dopo il primo scambio utente+assistente, genera un titolo breve e lo salva.
    Restituisce il nuovo titolo o None se non aggiornato.
    """
    try:
        msgs = await get_title_context_messages(session_id, limit=4)
        if len(msgs) < 2:
            return None

        context = "\n".join(
            f"{'Utente' if m['role'] == 'user' else 'Pirandello'}: {m['content'][:300]}"
            for m in msgs
        )

        prompt = f"""Sei un assistente che assegna titoli brevi a conversazioni.

Conversazione:
{context}

Genera un titolo di 3-6 parole in italiano che catturi l'essenza del dialogo.
Deve essere originale, descrittivo, non una ripetizione della domanda.
Solo il titolo, niente virgolette, niente prefissi, niente punti finali."""

        provider = get_active_provider_name()
        response = await chat_once(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=40,
            provider_name=provider,
        )
        raw = (response.get("content", "") or "").strip().strip('"\'')
        if not raw:
            return None

        title = " ".join(raw.split())
        if len(title) > 60:
            title = title[:57].rstrip() + "…"

        current = await get_session_title(session_id)
        if current and current == title:
            return None

        await db_update_session_title(session_id, title)
        logger.info("Titolo sessione {} → {}", session_id, title)
        return title
    except Exception as e:
        logger.error("Errore titolo sessione {}: {}", session_id, e)
        return None

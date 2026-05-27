import sqlite3
from pathlib import Path
from loguru import logger
from backend.memory.chat_history import DB_PATH, get_summary, save_summary
from backend.agent.llm_client import chat_once

async def update_session_summary(session_id: str):
    """
    Dynamically updates the session summary in the background.
    If the session history has more than 6 messages, it takes the messages
    preceding the last 6 and summarizes/consolidates them with any existing summary.
    """
    try:
        # Connect and fetch all messages in chronological order
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, role, content FROM conversations WHERE session_id = ? ORDER BY id ASC",
                (session_id,)
            ).fetchall()
        finally:
            conn.close()

        total_msgs = len(rows)
        # If we have 6 or fewer messages, there is no need to summarize
        if total_msgs <= 6:
            return

        # The messages that should be part of the summary are all except the last 6
        to_summarize = rows[:-6]
        max_id_to_summarize = to_summarize[-1]["id"]

        # Check if we already have a summary
        existing = await get_summary(session_id)
        prev_summary = ""
        last_msg_id = -1
        if existing:
            prev_summary, last_msg_id = existing

        # Filter only messages that haven't been summarized yet
        new_to_summarize = [r for r in to_summarize if r["id"] > last_msg_id]
        if not new_to_summarize:
            # Nothing new to summarize
            return

        logger.info(f"Summarizing {len(new_to_summarize)} new messages for session {session_id}...")

        # Format new messages for the LLM
        new_msgs_text = ""
        for r in new_to_summarize:
            role_label = "Utente" if r["role"] == "user" else "Pirandello"
            new_msgs_text += f"{role_label}: {r['content']}\n"

        # Build prompt for consolidation
        if prev_summary:
            prompt = f"""Sei un assistente editoriale per Luigi Pirandello. Il tuo compito è consolidare il riassunto di una conversazione in corso aggiungendovi i nuovi messaggi.
Mantieni il riassunto estremamente conciso (al massimo 2 o 3 brevi frasi), descrivendo in modo impersonale i temi chiave affrontati (es. l'utente si è presentato come Francesco, si è discusso del tema della maschera sociale e dell'opera Enrico IV).

Riassunto precedente:
"{prev_summary}"

Nuovi scambi da aggiungere al riassunto:
{new_msgs_text}

Genera il nuovo riassunto consolidato in italiano. Sii diretto e conciso, inizia direttamente con il riassunto senza commenti introduttivi."""
        else:
            prompt = f"""Sei un assistente editoriale per Luigi Pirandello. Il tuo compito è creare un brevissimo riassunto iniziale di questa prima parte di conversazione.
Mantieni il riassunto estremamente conciso (al massimo 2 o 3 brevi frasi), descrivendo in modo impersonale i temi chiave affrontati (es. l'utente si è presentato, si è discusso del relativismo).

Scambi da riassumere:
{new_msgs_text}

Genera il riassunto in italiano. Sii diretto e conciso, inizia direttamente con il riassunto senza commenti introduttivi."""

        # Call the local LLM for a fast summarization response
        response = await chat_once(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=256
        )

        new_summary = response.content.strip()
        
        # Save the updated summary
        await save_summary(session_id, new_summary, max_id_to_summarize)
        logger.info(f"Session {session_id} summary successfully updated (up to msg_id {max_id_to_summarize}): {new_summary}")

    except Exception as e:
        logger.error(f"Error updating session summary for {session_id}: {e}")

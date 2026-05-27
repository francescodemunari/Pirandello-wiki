"""
Memoria utente persistente — fatti su SQLite, sincronizzati su backend/memory/memory.md
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "chat_history.db"
MEMORY_MD_PATH = Path(__file__).resolve().parent / "memory.md"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_user_memory_table():
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                category   TEXT    NOT NULL,
                key        TEXT    NOT NULL UNIQUE,
                value      TEXT    NOT NULL,
                created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_fact(category: str, key: str, value: str) -> bool:
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO user_facts (category, key, value, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value      = excluded.value,
                category   = excluded.category,
                updated_at = datetime('now')
            """,
            (category, key, value),
        )
        conn.commit()
        sync_memory_to_disk()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_all_facts() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT category, key, value FROM user_facts ORDER BY category, key"
        ).fetchall()
        return [{"category": r["category"], "key": r["key"], "value": r["value"]} for r in rows]
    finally:
        conn.close()


def clear_all_facts() -> int:
    """Elimina tutti i fatti utente e aggiorna memory.md."""
    conn = _get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM user_facts").fetchone()[0]
        conn.execute("DELETE FROM user_facts")
        conn.commit()
        sync_memory_to_disk()
        return count
    finally:
        conn.close()


def delete_fact(category: str, key: str) -> bool:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "DELETE FROM user_facts WHERE category = ? AND key = ?",
            (category, key),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            sync_memory_to_disk()
        return deleted
    finally:
        conn.close()


def get_profile_summary() -> str:
    facts = get_all_facts()
    if not facts:
        return ""

    by_category: dict[str, list[str]] = {}
    for f in facts:
        by_category.setdefault(f["category"], []).append(f"{f['key']}: {f['value']}")

    lines = ["## Cosa ricordo dell'interlocutore:"]
    for cat, items in by_category.items():
        lines.append(f"**{cat.capitalize()}**")
        for item in items:
            lines.append(f"  - {item}")
    return "\n".join(lines)


_INTRO_PATTERNS = [
    (re.compile(r"\bmi\s+chiamo\s+([a-zàèéìòùA-ZÀÈÉÌÒÙ' -]{2,50})", re.I), "identita", "nome"),
    (re.compile(r"\bil\s+mio\s+nome\s+[eè]\s+([a-zàèéìòùA-ZÀÈÉÌÒÙ' -]{2,50})", re.I), "identita", "nome"),
    (re.compile(r"\bsono\s+([a-zàèéìòùA-ZÀÈÉÌÒÙ' -]{2,50})\b", re.I), "identita", "nome"),
    (
        re.compile(
            r"piacere\s+(?:di\s+conoscerti|conoscervi)[,!.]?\s*(?:sono\s+)?([a-zàèéìòùA-ZÀÈÉÌÒÙ' -]{2,50})",
            re.I,
        ),
        "identita",
        "nome",
    ),
]

_SKIP_NAME_WORDS = frozenset(
    {
        "uno", "una", "un", "il", "la", "lo", "gli", "le", "qui",
        "studente", "studentessa", "molto", "felice", "contento", "pirandello",
    }
)


def _clean_name(raw: str) -> str | None:
    name = raw.strip().strip(".,!?")
    if not name or len(name) < 2:
        return None
    first = name.split()[0].lower()
    if first in _SKIP_NAME_WORDS:
        return None
    return name.title() if name.islower() or name.isupper() else name.strip()


def extract_facts_from_message(text: str) -> list[tuple[str, str, str]]:
    """Estrae fatti stabili da messaggi di presentazione (fallback se il LLM non usa i tool)."""
    if not text or len(text.strip()) < 3:
        return []
    found: list[tuple[str, str, str]] = []
    seen_keys: set[str] = set()
    for pattern, category, key in _INTRO_PATTERNS:
        for match in pattern.finditer(text):
            value = _clean_name(match.group(1))
            if value and key not in seen_keys:
                found.append((category, key, value))
                seen_keys.add(key)
    return found


def ingest_message_facts(text: str) -> int:
    """Salva fatti estratti da un messaggio utente. Restituisce quanti fatti sono stati salvati."""
    saved = 0
    for category, key, value in extract_facts_from_message(text):
        if save_fact(category, key, value):
            saved += 1
    return saved


def sync_memory_to_disk() -> None:
    try:
        MEMORY_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
        summary = get_profile_summary()
        content = (
            "# Memoria conversazioni (Pirandello)\n\n"
            "File sincronizzato automaticamente dal database. "
            "Puoi leggerlo per ispezione; le modifiche manuali possono essere sovrascritte.\n\n"
            "---\n\n"
        )
        content += summary if summary else "*Nessun fatto registrato ancora.*\n"
        MEMORY_MD_PATH.write_text(content, encoding="utf-8")
    except Exception:
        pass

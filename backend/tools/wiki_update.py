from datetime import date
from backend.config import WIKI_PATH

async def wiki_update(path: str, content: str, update_log: bool = True) -> dict:
    fpath = (WIKI_PATH / path).resolve()
    if not str(fpath).startswith(str(WIKI_PATH.resolve())):
        raise ValueError("Accesso negato: percorso fuori dalla wiki")
    if not fpath.exists():
        raise FileNotFoundError(f"Pagina non trovata: {path}")

    existing = fpath.read_text(encoding="utf-8")

    if existing.startswith("---"):
        parts = existing.split("---", 2)
        if len(parts) >= 3:
            fm_lines = parts[1].split("\n")
            new_fm_lines = []
            for line in fm_lines:
                if line.strip().startswith("updated:"):
                    new_fm_lines.append(f"updated: {date.today().isoformat()}")
                else:
                    new_fm_lines.append(line)
            new_fm = "\n".join(new_fm_lines)
            full_content = f"---{new_fm}---\n\n{content}"
        else:
            full_content = content
    else:
        full_content = content

    fpath.write_text(full_content, encoding="utf-8")

    # Sync with ChromaDB vector store
    from backend.memory.vector import store_page_vector
    store_page_vector(path, full_content)

    if update_log:
        _update_log(f"update | {path}", [path])

    return {"success": True, "path": path}

def _update_log(action: str, pages: list[str]):
    from datetime import datetime
    log_file = WIKI_PATH / ".." / "log.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{now}] {action}\n"
    for p in pages:
        entry += f"  - `{p}`\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)

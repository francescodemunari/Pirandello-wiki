from datetime import date
from pathlib import Path
from backend.config import WIKI_PATH

VALID_CATEGORIES = {"entities", "concepts", "sources", "synthesis", "queries"}

async def wiki_create(path: str, title: str, category: str, content: str, tags: list[str] = None) -> dict:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Categoria non valida: {category}. Usa: {', '.join(VALID_CATEGORIES)}")

    today = date.today().isoformat()
    tags_str = f"\ntags: [{', '.join(tags)}]" if tags else ""
    
    category_to_type = {
        "sources": "source",
        "entities": "entity",
        "concepts": "concept",
        "synthesis": "synthesis",
        "queries": "query"
    }
    page_type = category_to_type.get(category, category)
    frontmatter = f"---\ntype: {page_type}\ncreated: {today}\nupdated: {today}{tags_str}\n---\n\n"
    full_content = frontmatter + content

    dest_dir = WIKI_PATH / "pages" / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{path}.md"

    if dest_file.exists():
        raise FileExistsError(f"Pagina già esistente: {path}.md in {category}")

    dest_file.write_text(full_content, encoding="utf-8")

    rel_path = f"wiki/pages/{category}/{path}.md"
    _update_index(category, title, rel_path)
    _update_log(f"create | {title}", [rel_path])

    # Sync with ChromaDB vector store
    from backend.memory.vector import store_page_vector
    store_page_vector(f"pages/{category}/{path}.md", full_content)

    return {"success": True, "path": f"pages/{category}/{path}.md"}

def _update_index(category: str, title: str, rel_path: str):
    index_file = WIKI_PATH / ".." / "index.md"
    if not index_file.exists():
        return

    content = index_file.read_text(encoding="utf-8")

    category_names = {
        "sources": "Sources (Opere processate)",
        "entities": "Entities (Personaggi e opere)",
        "concepts": "Concepts (Temi e concetti)",
        "synthesis": "Synthesis (Sintesi trasversali)",
        "queries": "Queries (Domande frequenti)",
    }
    section_header = f"## {category_names.get(category, category)}"

    new_line = f"- [{title}]({rel_path})"
    lines = content.split("\n")
    insert_pos = None
    section_found = False
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            section_found = True
            insert_pos = i + 1
        elif section_found and line.startswith("## ") and i > insert_pos:
            break
        elif section_found and line.strip() == "":
            if insert_pos is None or i > insert_pos:
                break

    if insert_pos is not None:
        indent = ""
        lines.insert(insert_pos, f"{indent}{new_line}")
        index_file.write_text("\n".join(lines), encoding="utf-8")

def _update_log(action: str, pages: list[str]):
    from datetime import datetime
    log_file = WIKI_PATH / ".." / "log.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{now}] {action}\n"
    for p in pages:
        entry += f"  - `{p}`\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)

from backend.config import WIKI_PATH

async def wiki_list(category: str = None) -> list[dict]:
    pages_dir = WIKI_PATH / "pages"
    if not pages_dir.exists():
        return []

    results = []
    if category:
        cat_dir = pages_dir / category
        if cat_dir.exists():
            for f in sorted(cat_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                title = _extract_title(content, f.stem)
                results.append({
                    "path": f"pages/{category}/{f.name}",
                    "title": title,
                    "category": category,
                })
    else:
        for cat_dir in sorted(pages_dir.iterdir()):
            if cat_dir.is_dir():
                for f in sorted(cat_dir.glob("*.md")):
                    content = f.read_text(encoding="utf-8")
                    title = _extract_title(content, f.stem)
                    results.append({
                        "path": f"pages/{cat_dir.name}/{f.name}",
                        "title": title,
                        "category": cat_dir.name,
                    })

    return results

def _extract_title(content: str, fallback: str) -> str:
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if line.strip().startswith("title:"):
                    return line.split(":", 1)[1].strip()
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return fallback

import re
from pathlib import Path
from backend.config import WIKI_PATH

STOP_WORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una",
    "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "che", "cosa", "come", "dove", "quando", "perché", "perche",
    "chi", "quale", "quanto", "non", "si", "mi", "ti", "ci", "vi", "ne",
    "è", "e", "sono", "ha", "hai", "hanno",
    "mio", "tuo", "suo", "nostro", "vostro",
    "questo", "quello", "questi", "quelli",
    "stessa", "stesso", "ogni", "molto", "poco", "troppo", "tanto",
    "altro", "altri", "altra", "altre",
}

def tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.split(r"[^\w]+", text)
    return [t for t in tokens if t not in STOP_WORDS and len(t) >= 3]

def extract_frontmatter(content: str) -> tuple[dict, str]:
    body = content
    fm = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2]
            for line in fm_text.strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    fm[key.strip()] = val.strip()
    return fm, body

def score_page(content: str, keywords: set[str]) -> int:
    if not content:
        return 0
    fm, body = extract_frontmatter(content)
    score = 0
    lower_body = body.lower()
    for kw in keywords:
        title = fm.get("title", "")
        tags = fm.get("tags", "")
        aliases = fm.get("aliases", "")
        frontmatter_text = (title + " " + tags + " " + aliases).lower()
        if kw in frontmatter_text:
            score += 3
        count = lower_body.count(kw)
        score += count
    return score

async def wiki_search(query: str, top_k: int = 5) -> list[dict]:
    keywords = tokenize(query)
    
    # 1. Run Semantic Search via ChromaDB
    from backend.memory.vector import search_semantic
    semantic_results = search_semantic(query, top_k=top_k * 2)
    
    pages_map = {}
    
    # Store semantic results in pages_map
    for r in semantic_results:
        path = r["path"]
        pages_map[path] = {
            "path": path,
            "title": r["title"],
            "category": r["category"],
            "preview": r["preview"],
            "keyword_score": 0.0,
            "semantic_score": float(r["score"])
        }
        
    # 2. Run Keyword Search
    pages_dir = WIKI_PATH / "pages"
    if pages_dir.exists():
        md_files = list(pages_dir.rglob("*.md"))
        for fpath in md_files:
            try:
                content = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            
            rel_path = fpath.relative_to(WIKI_PATH).as_posix()
            kw_score = 0.0
            if keywords:
                kw_score = float(score_page(content, set(keywords)))
                
            if kw_score > 0:
                if rel_path in pages_map:
                    pages_map[rel_path]["keyword_score"] = kw_score
                else:
                    fm, body = extract_frontmatter(content)
                    preview = body.strip()[:2000]
                    pages_map[rel_path] = {
                        "path": rel_path,
                        "title": fm.get("title", fpath.stem),
                        "category": fm.get("type", "unknown"),
                        "preview": preview,
                        "keyword_score": kw_score,
                        "semantic_score": 0.0
                    }

    # 3. Combine scores and compute hybrid rank
    merged_results = []
    for path, data in pages_map.items():
        hybrid_score = (data["keyword_score"] * 1.0) + (data["semantic_score"] * 1.5)
        if hybrid_score > 0:
            merged_results.append({
                "path": data["path"],
                "title": data["title"],
                "category": data["category"],
                "score": hybrid_score,
                "preview": data["preview"]
            })
            
    merged_results.sort(key=lambda x: x["score"], reverse=True)
    return merged_results[:top_k]

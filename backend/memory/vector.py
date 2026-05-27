import chromadb
from pathlib import Path
from loguru import logger
from backend.config import WIKI_PATH

# Lazy-loaded ChromaDB objects
_client: chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None

DB_DIR = Path(__file__).resolve().parent / "chromadb_store"

def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Helper to extract frontmatter and body from markdown content."""
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

def _get_collection() -> chromadb.Collection:
    """Initializes and returns the local ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(DB_DIR))
        # Use cosine similarity space
        _collection = _client.get_or_create_collection(
            name="pirandello_wiki",
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB initialized in {DB_DIR}. Total vectors: {_collection.count()}")
    return _collection

def store_page_vector(rel_path: str, content: str):
    """Saves or updates a single wiki page in ChromaDB vector store."""
    try:
        collection = _get_collection()
        fm, body = extract_frontmatter(content)
        title = fm.get("title", Path(rel_path).stem)
        category = fm.get("type", "unknown")
        
        # Use relative path as the stable unique ID
        doc_id = rel_path
        
        # Index document body + title for better retrieval
        index_text = f"Titolo: {title}\nCategoria: {category}\n\n{body.strip()}"
        
        metadata = {
            "title": title,
            "category": category,
            "path": rel_path
        }
        
        collection.upsert(
            ids=[doc_id],
            documents=[index_text],
            metadatas=[metadata]
        )
        logger.info(f"Vector indexed/updated for: {rel_path}")
    except Exception as e:
        logger.error(f"Error upserting vector for {rel_path}: {e}")

def delete_page_vector(rel_path: str):
    """Deletes a wiki page from ChromaDB vector store."""
    try:
        collection = _get_collection()
        collection.delete(ids=[rel_path])
        logger.info(f"Vector deleted for: {rel_path}")
    except Exception as e:
        logger.error(f"Error deleting vector for {rel_path}: {e}")

def search_semantic(query: str, top_k: int = 5) -> list[dict]:
    """
    Queries ChromaDB for semantically similar wiki pages.
    Returns a list of dicts with: path, title, category, score, preview.
    Note: Score is computed as (2.0 - distance) * 5, scaling to ~0-10.
    """
    try:
        collection = _get_collection()
        total = collection.count()
        if total == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, total)
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            # Cose similarity distance is between 0 (identical) and 2 (orthogonal/opposite).
            # Convert cosine distance to a similarity score between 0 and 10.
            score = (2.0 - dist) * 5.0
            
            # Preview is the first part of the document
            preview = doc
            if "\n\n" in doc:
                parts = doc.split("\n\n", 2)
                preview = parts[2] if len(parts) >= 3 else parts[-1]

            hits.append({
                "path": meta["path"],
                "title": meta["title"],
                "category": meta["category"],
                "score": score,
                "preview": preview[:2000]
            })
        return hits
    except Exception as e:
        logger.error(f"Error during semantic search: {e}")
        return []

def index_wiki():
    """
    Scans and indexes all markdown pages inside WIKI_PATH/pages into ChromaDB.
    Runs at server startup.
    """
    try:
        collection = _get_collection()
        pages_dir = WIKI_PATH / "pages"
        if not pages_dir.exists():
            logger.warning(f"Wiki directory {pages_dir} does not exist.")
            return

        md_files = list(pages_dir.rglob("*.md"))
        logger.info(f"Starting bulk indexing of {len(md_files)} wiki pages...")
        
        for fpath in md_files:
            try:
                rel_path = fpath.relative_to(WIKI_PATH).as_posix()
                content = fpath.read_text(encoding="utf-8")
                store_page_vector(rel_path, content)
            except Exception as fe:
                logger.error(f"Error indexing file {fpath}: {fe}")
                
        logger.info(f"Bulk indexing complete. Total vectors: {collection.count()}")
    except Exception as e:
        logger.error(f"Error during bulk wiki indexing: {e}")

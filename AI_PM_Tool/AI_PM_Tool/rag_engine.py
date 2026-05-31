#!/usr/bin/env python3
"""
RAG Engine — HTML indexer and semantic retriever for the AI PM Tool chatbot.

Pipeline:
  HTML files → BeautifulSoup (strip CSS/JS) → section chunker →
  ChromaDB default embeddings (ONNXMiniLM) → cosine similarity retrieval
"""
import re
import hashlib
from pathlib import Path


# ── Pages to index ────────────────────────────────────────────────────────────
# Navigation/hub pages (default.html, ai-learning.html, projects.html, new-project.html)
# are intentionally excluded — they contain no project content worth retrieving.

STATIC_PAGES = [
    "Week1_Learning_Summary.html",
    "Week2_Learning_Summary.html",
    "Week3_Learning_Summary.html",
    "Week4_Learning_Summary.html",
    "Week5_Learning_Summary.html",
    "Week6_Learning_Summary.html",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _page_type(rel: str) -> str:
    if "prd.html" in rel:
        return "PRD"
    if "status-tracker" in rel:
        return "Status Tracker"
    if re.search(r'Week\d+_Learning', rel):
        return "Learning Summary"
    return "Other"


def _project_name(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            return parts[idx + 1].replace("-", " ").title()
    m = re.search(r'Week(\d+)', rel)
    if m:
        return f"Week {m.group(1)} Learning"
    return "General"


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


# ── Core extractor ────────────────────────────────────────────────────────────

def extract_chunks(html_path: Path, rel_path: str) -> list[dict]:
    """
    Parse one HTML file and return a list of section chunks.
    Each chunk: { text, source, page_type, project, section }
    """
    from bs4 import BeautifulSoup

    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    # Strip non-content tags
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()

    page_type    = _page_type(rel_path)
    project_name = _project_name(rel_path)
    chunks: list[dict] = []

    headings = soup.find_all(["h1", "h2", "h3"])

    if not headings:
        # No headings: whole page as one chunk
        text = _clean(soup.get_text(" "))
        if len(text) > 80:
            chunks.append({
                "text": text[:2000],
                "source": rel_path,
                "page_type": page_type,
                "project": project_name,
                "section": "Overview",
            })
        return chunks

    for heading in headings:
        title = _clean(heading.get_text())
        if not title:
            continue

        parts: list[str] = []
        for sib in heading.next_siblings:
            if getattr(sib, "name", None) in ("h1", "h2", "h3"):
                break
            t = _clean(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
            if t:
                parts.append(t)

        body = " ".join(parts)
        text = _clean(f"{title}. {body}")

        if len(text) > 60:
            chunks.append({
                "text": text[:1800],       # cap per chunk so embeddings stay clean
                "source": rel_path,
                "page_type": page_type,
                "project": project_name,
                "section": title,
            })

    return chunks


# ── RAG Engine ────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    ChromaDB-backed RAG engine.
    Uses ChromaDB's built-in ONNX MiniLM embeddings — no external API needed.
    """

    COLLECTION = "project_pages"

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.db_path  = base_dir / "chromadb_store"
        self._col     = None

    # ── internal ──────────────────────────────────────────────────────────────

    def _collection(self):
        if self._col is not None:
            return self._col
        import chromadb
        client     = chromadb.PersistentClient(path=str(self.db_path))
        self._col  = client.get_or_create_collection(
            name     = self.COLLECTION,
            metadata = {"hnsw:space": "cosine"},
        )
        return self._col

    def _discover_pages(self) -> list[str]:
        """Return rel-paths of all indexable HTML files."""
        pages: list[str] = []

        # Static week summaries (only those that exist)
        for p in STATIC_PAGES:
            if (self.base_dir / p).exists():
                pages.append(p)

        # Dynamic: every projects/{slug}/prd.html + status-tracker.html
        proj_dir = self.base_dir / "projects"
        if proj_dir.exists():
            for slug_dir in sorted(proj_dir.iterdir()):
                if not slug_dir.is_dir():
                    continue
                for fname in ("prd.html", "status-tracker.html"):
                    candidate = slug_dir / fname
                    if candidate.exists():
                        rel = str(candidate.relative_to(self.base_dir)).replace("\\", "/")
                        pages.append(rel)

        return pages

    # ── public API ────────────────────────────────────────────────────────────

    def index_all(self, force: bool = False) -> dict:
        """
        Index all project HTML pages into ChromaDB.
        If force=False, skips re-indexing when chunks already exist.
        Returns: { chunks: int, files: int }
        """
        col   = self._collection()
        pages = self._discover_pages()

        if not force and col.count() > 0:
            return {"chunks": col.count(), "files": len(pages), "skipped": True}

        # Collect all chunks
        all_chunks: list[dict] = []
        indexed_files: list[str] = []

        for rel in pages:
            path = self.base_dir / rel
            if not path.exists():
                continue
            try:
                chunks = extract_chunks(path, rel)
                all_chunks.extend(chunks)
                indexed_files.append(rel)
            except Exception as e:
                print(f"  ⚠ Skipping {rel}: {e}")

        if not all_chunks:
            return {"chunks": 0, "files": 0}

        # Stable IDs — deterministic so upsert is idempotent
        ids = [
            hashlib.md5(f"{c['source']}::{c['section']}::{i}".encode()).hexdigest()
            for i, c in enumerate(all_chunks)
        ]

        # Wipe old entries then upsert fresh
        if col.count() > 0:
            col.delete(where={"source": {"$ne": "__sentinel__"}})

        col.upsert(
            ids       = ids,
            documents = [c["text"] for c in all_chunks],
            metadatas = [{
                "source":    c["source"],
                "page_type": c["page_type"],
                "project":   c["project"],
                "section":   c["section"],
            } for c in all_chunks],
        )

        return {"chunks": len(all_chunks), "files": len(indexed_files)}

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Semantic search: embed query, return top-k matching chunks.
        Auto-indexes on first call if collection is empty.
        """
        col = self._collection()

        if col.count() == 0:
            print("  RAG: collection empty — running index_all()")
            self.index_all(force=True)

        n = min(top_k, col.count())
        if n == 0:
            return []

        results = col.query(query_texts=[query], n_results=n)

        chunks: list[dict] = []
        for text, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":      text,
                "source":    meta.get("source", ""),
                "page_type": meta.get("page_type", ""),
                "project":   meta.get("project", ""),
                "section":   meta.get("section", ""),
                "score":     round(1 - float(dist), 3),   # cosine similarity
            })

        return chunks

    def status(self) -> dict:
        try:
            count = self._collection().count()
            pages = self._discover_pages()
            return {
                "indexed":     True,
                "chunk_count": count,
                "page_count":  len(pages),
            }
        except Exception as e:
            return {"indexed": False, "chunk_count": 0, "error": str(e)}

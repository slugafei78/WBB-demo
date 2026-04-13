"""Point-in-time text检索：本地 `data/{symbol}/raw/` 等目录下的快照（避免未来信息）。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    source_path: str


class EdgarSnapshotRetriever:
    """
    在 root / {symbol} / {asof_iso} / 下查找 .txt/.htm/.html。
    symbol 使用与 data/ 一致的 slug（小写，如 cola）。
    """

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else None

    def chunk_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def retrieve(self, symbol: str, asof_iso: str, max_chars: int = 12000) -> list[TextChunk]:
        if self.root is None or not self.root.exists():
            return []
        sym_dir = self.root / symbol.lower() / asof_iso
        if not sym_dir.is_dir():
            return []
        chunks: list[TextChunk] = []
        for path in sorted(sym_dir.glob("**/*")):
            if path.is_file() and path.suffix.lower() in {".txt", ".htm", ".html"}:
                text = path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
                cid = self.chunk_hash(text + str(path))
                chunks.append(TextChunk(chunk_id=cid, text=text, source_path=str(path)))
        return chunks

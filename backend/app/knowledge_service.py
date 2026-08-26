import json
import re
from dataclasses import dataclass
from pathlib import Path


class KnowledgeLibraryError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgePassage:
    source_id: str
    title: str
    locator: str
    excerpt: str
    score: float


class KnowledgeLibrary:
    """Small, document-first library; it deliberately does not build a taxon catalog."""

    TEXT_SUFFIXES = {".txt", ".md"}

    def __init__(self, root: Path) -> None:
        self.root = root
        self._text_cache: dict[Path, tuple[int, int, str]] = {}

    def ensure_directories(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def summary(self) -> dict:
        files = self._source_files()
        return {
            "source_count": len(files),
            "supported_extensions": [".md", ".txt", ".pdf"],
            "directory": str(self.root),
        }

    def search(self, query: str, limit: int = 6) -> list[KnowledgePassage]:
        terms = self._terms(query)
        if not terms:
            return []
        matches: list[KnowledgePassage] = []
        for path in self._source_files():
            try:
                text = self._read_cached(path)
            except (KnowledgeLibraryError, OSError):
                # One damaged, incomplete, or temporarily locked document must not
                # make the whole local bookshelf unavailable.
                continue
            metadata = self._metadata(path)
            title = str(metadata.get("title") or path.stem)
            for index, chunk in enumerate(self._chunks(text), start=1):
                normalized = chunk.casefold()
                score = sum(
                    (5 if term == query.casefold().strip() else 1) * normalized.count(term)
                    for term in terms
                )
                if score:
                    matches.append(
                        KnowledgePassage(
                            source_id=path.name,
                            title=title,
                            locator=f"片段 {index}",
                            excerpt=chunk[:1800],
                            score=float(score),
                        )
                    )
        matches.sort(key=lambda item: (-item.score, item.title, item.locator))
        return matches[:limit]

    def _source_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(
            path
            for path in self.root.iterdir()
            if path.is_file() and path.suffix.casefold() in self.TEXT_SUFFIXES | {".pdf"}
        )

    @staticmethod
    def _terms(query: str) -> list[str]:
        normalized = query.casefold().strip()
        words = re.findall(r"[a-z][a-z-]{2,}|[\u3400-\u9fff]{2,}", normalized)
        terms = {normalized, *words}
        for word in words:
            if re.fullmatch(r"[\u3400-\u9fff]{3,}", word):
                terms.update(word[index : index + 2] for index in range(len(word) - 1))
        return sorted((term for term in terms if term), key=len, reverse=True)

    @staticmethod
    def _chunks(text: str, size: int = 2400, overlap: int = 300) -> list[str]:
        cleaned = re.sub(r"\r\n?", "\n", text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        if not cleaned:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(cleaned):
            end = min(start + size, len(cleaned))
            if end < len(cleaned):
                boundary = max(cleaned.rfind("\n\n", start, end), cleaned.rfind("。", start, end))
                if boundary > start + size // 2:
                    end = boundary + 1
            chunks.append(cleaned[start:end].strip())
            if end == len(cleaned):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _read(self, path: Path) -> str:
        if path.suffix.casefold() in self.TEXT_SUFFIXES:
            return path.read_text(encoding="utf-8", errors="replace")
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise KnowledgeLibraryError(
                "读取 PDF 需要安装 pypdf；TXT 和 Markdown 仍可使用。"
            ) from exc
        try:
            reader = PdfReader(path)
            return "\n\n".join(
                f"[PDF 第 {number} 页]\n{page.extract_text() or ''}"
                for number, page in enumerate(reader.pages, start=1)
            )
        except (OSError, ValueError) as exc:
            raise KnowledgeLibraryError(f"无法读取资料：{path.name}") from exc

    def _read_cached(self, path: Path) -> str:
        try:
            stat = path.stat()
        except OSError as exc:
            raise KnowledgeLibraryError(f"无法读取资料：{path.name}") from exc
        cached = self._text_cache.get(path)
        signature = (stat.st_mtime_ns, stat.st_size)
        if cached and cached[:2] == signature:
            return cached[2]
        text = self._read(path)
        self._text_cache[path] = (*signature, text)
        return text

    @staticmethod
    def _metadata(path: Path) -> dict:
        metadata_path = path.with_suffix(path.suffix + ".json")
        if not metadata_path.exists():
            return {}
        try:
            value = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_no: int
    content: str
    metadata: dict[str, object]


def chunk_by_paragraph(text: str, max_chars: int = 1200) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_no = 1
    for paragraph in [item.strip() for item in text.split("\n\n") if item.strip()]:
        start = 0
        while start < len(paragraph):
            content = paragraph[start : start + max_chars]
            chunks.append(TextChunk(chunk_no=chunk_no, content=content, metadata={}))
            chunk_no += 1
            start += max_chars
    return chunks

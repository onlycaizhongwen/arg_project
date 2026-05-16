from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


class DocumentParser:
    supported_extensions: tuple[str, ...] = ()

    def parse(self, file_path: str) -> ParsedDocument:
        raise NotImplementedError


def parse_document(file_path: str) -> ParsedDocument:
    path = Path(file_path)
    extension = path.suffix.lower()
    if extension in {".txt", ".md"}:
        return ParsedDocument(
            text=path.read_text(encoding="utf-8", errors="ignore"),
            metadata={"parser": "plain_text", "filename": path.name},
        )
    if extension == ".csv":
        frame = pd.read_csv(path)
        return ParsedDocument(
            text=frame.to_csv(index=False),
            metadata={"parser": "csv", "filename": path.name, "rows": len(frame)},
        )
    if extension == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return ParsedDocument(
            text="\n\n".join(pages),
            metadata={"parser": "pdf", "filename": path.name, "pages": len(reader.pages)},
        )
    raise ValueError(f"Unsupported document extension: {extension or '<none>'}")

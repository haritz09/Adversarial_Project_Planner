from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class SinkConfigError(RuntimeError):

    pass

@dataclass(frozen=True)
class Document:
    title: str
    markdown: str = ""
    children: tuple[Document, ...] = ()

@dataclass(frozen=True)
class ProjectDocument:
    title: str
    children: tuple[Document, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ExportResult:
    sink: str
    location: str
    urls: Mapping[str, str] = field(default_factory=dict)
    page_ids: Mapping[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sink": self.sink,
            "location": self.location,
            "urls": dict(self.urls),
            "page_ids": dict(self.page_ids),
        }

class ExportSink(Protocol):
    name: str

    def export(self, document: ProjectDocument, run_id: str = "") -> ExportResult:
        ...

def slugify(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    value = re.sub(r"^\s*\d+(\.\d+)*[.)\-:]?\s*", "", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "document"

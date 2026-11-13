"""Load source exports without deriving request facts from export metadata."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    raw_bytes: bytes
    source_sha256: str
    message: str
    metadata: dict


def read_export(path: str | Path) -> SourceDocument:
    """Preserve byte identity and decode the message used for extraction/evidence.

    Compatible exports may carry additional metadata or use new filenames.
    Neither changes which text supplies the request facts.
    """
    path = Path(path)
    raw = path.read_bytes()
    try:
        export = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name}: export must be UTF-8 JSON") from exc
    if not isinstance(export, dict) or not isinstance(export.get("message"), str):
        raise ValueError(f"{path.name}: export must be an object with a message string")
    return SourceDocument(
        document_id=path.name,
        raw_bytes=raw,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        message=export["message"],
        metadata={key: value for key, value in export.items() if key != "message"},
    )

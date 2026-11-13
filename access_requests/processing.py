"""Independent per-document extraction and validation before review routing."""

import json
import shlex

from .provider import ProviderFailure
from .validation import validate_extraction


def process_batch(documents, provider, router):
    results = []
    for document in documents:
        result = {
            "document_id": document.document_id, "source_sha256": document.source_sha256,
            "response_source": getattr(provider, "response_source", "mock"),
            "provider_config": provider.provenance() if hasattr(provider, "provenance") else {"provider": "mock"},
            "extraction": None, "error": None,
        }
        try:
            reply = provider.extract(document.document_id, document.message)
            if reply.get("refusal"):
                raise ProviderFailure("refusal", "Provider declined extraction")
            if reply.get("status") != "completed":
                raise ProviderFailure("completion", "Extraction response is incomplete")
            try:
                extraction = json.loads(reply["output_text"])
            except (KeyError, TypeError, ValueError):
                raise ProviderFailure("parse", "Extraction content is not valid JSON") from None
            try:
                validate_extraction(extraction, document.message)
            except ValueError as exc:
                raise ProviderFailure("schema", str(exc)) from None
            result.update(router(extraction))
            result["extraction"] = extraction
            result["response_source"] = reply["response_source"]
        except ProviderFailure as exc:
            retry = f"access-requests retry --document {shlex.quote(document.document_id)}"
            result.update(status="error", owner="IT Service Desk", next_action="retry-extraction",
                          error_kind=exc.kind, error=f"{document.document_id}: {exc}. Retry: {retry}")
            if exc.retry_after_seconds is not None:
                result["retry_after_seconds"] = exc.retry_after_seconds
        results.append(result)
    return results

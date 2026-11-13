"""Saved-response provider for reproducible intake without credentials or HTTP."""

from collections import deque
from copy import deepcopy
import json
from pathlib import Path
from threading import Lock
from time import sleep as default_sleep


class MockProvider:
    """Select replies by document, optionally consuming scripted outcomes.

    Scripts take precedence over reusable replies. Every attempted call is
    recorded, including errors and exhausted scripts. Delays happen outside
    the accounting lock so one delayed document does not block other calls.
    """

    def __init__(self, fixtures_dir, *, replies=None, scripts=None, sleep=default_sleep):
        self.fixtures_dir = Path(fixtures_dir).resolve()
        self.replies = dict(replies or {})
        self.scripts = {
            document_id: deque(deepcopy(events))
            for document_id, events in (scripts or {}).items()
        }
        self.calls = []
        self._sleep = sleep
        self._lock = Lock()

    def extract(self, document_id, message):
        """Return a fresh saved envelope with mock provenance, or raise a script error."""
        with self._lock:
            self.calls.append({"document_id": document_id, "message": message})
            if document_id in self.scripts:
                if not self.scripts[document_id]:
                    raise RuntimeError(f"Mock script exhausted for {document_id}")
                event = self.scripts[document_id].popleft()
            else:
                selection = self.replies[document_id]
                event = {"reply": selection} if isinstance(selection, str) else deepcopy(selection)

        delay = event.get("delay_seconds", 0)
        if delay:
            self._sleep(delay)
        if "error" in event:
            reason = event.get("message", f"Mock provider error: {event['error']}")
            if event["error"] == "interruption":
                raise InterruptedError(reason)
            if event["error"] in ("rate_limit", "timeout"):
                from .provider import ProviderFailure
                raise ProviderFailure(event["error"], "Simulated provider service failure",
                                      event.get("retry_after_seconds"))
            raise RuntimeError(reason)

        path = (self.fixtures_dir / event["reply"]).resolve()
        if not path.is_relative_to(self.fixtures_dir):
            raise ValueError("Mock response must be inside the fixture directory")
        reply = json.loads(path.read_text(encoding="utf-8"))
        if "request_id" in event:
            # Explicit saved-template parameterization for authored load examples;
            # this supplies no business logic or inferred facts to real extraction.
            import re
            identifier = event["request_id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9-]+", identifier):
                raise ValueError("Mock request_id substitution must be an identifier")
            reply["output_text"] = reply["output_text"].replace("{{request_id}}", identifier)
        reply["response_source"] = "mock"
        return reply

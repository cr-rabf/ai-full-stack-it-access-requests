"""Anthropic Messages HTTP adapter with explicit, credential-safe failures."""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ProviderConfig:
    endpoint: str = "https://api.anthropic.com/v1/messages"
    model: str = "claude-sonnet-5-5"
    max_tokens: int = 8192
    timeout: float = 60
    api_version: str = "2026-10-21"


class ProviderFailure(Exception):
    def __init__(self, kind, detail, retry_after_seconds=None):
        super().__init__(detail)
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds


def http_transport(*, method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return SimpleNamespace(status_code=response.code, headers=dict(response.headers),
                               body=response.read())


def environment_credential():
    return os.environ["API_KEY"]


class AnthropicProvider:
    def __init__(self, config=None, *, transport=http_transport,
                 credential_loader=environment_credential, prompt_path=None,
                 schema_path=None, policy_path=None):
        self.config = config or ProviderConfig()
        self.transport = transport
        self.credential_loader = credential_loader
        self.prompt_path = Path(prompt_path or ROOT / "access_requests/extraction_prompt.txt")
        self.schema_path = Path(schema_path or ROOT / "snapshot.schema.json")
        self.policy_path = Path(policy_path or ROOT / "materials/office-policy.md")
        self.response_source = getattr(transport, "response_source", f"anthropic/{self.config.model}")

    def provenance(self):
        return asdict(self.config)

    def _body(self, document_id, message):
        return {
            "model": self.config.model, "max_tokens": self.config.max_tokens, "stream": False,
            "system": self.prompt_path.read_text(encoding="utf-8"),
            "messages": [{"role": "user", "content": [{"type": "text", "text": json.dumps(
                {"document_id": document_id, "message": message})}]}],
            "output_config": {"format": {"type": "json_schema", "schema": json.loads(
                self.schema_path.read_text(encoding="utf-8"))}},
        }

    def request_evidence(self, document):
        # Construct redacted evidence without loading any credential.
        return {
            "method": "POST", "url": self.config.endpoint,
            "headers": {"Authorization": "[REDACTED]", "Content-Type": "application/json",
                        "anthropic-version": self.config.api_version},
            "body": self._body(document.document_id, document.message),
            "response_source": self.response_source,
            "response_handling": ["http-status", "refusal", "completion", "parse", "schema", "quotes", "routing"],
        }

    def extract(self, document_id, message):
        try:
            credential = self.credential_loader()
        except (KeyError, ValueError):
            raise ProviderFailure("configuration", "Set API_KEY before provider intake") from None
        if not credential:
            raise ProviderFailure("configuration", "Set API_KEY before provider intake")
        try:
            response = self.transport(
                method="POST", url=self.config.endpoint, timeout=self.config.timeout,
                headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json",
                         "anthropic-version": self.config.api_version},
                body=self._body(document_id, message),
            )
        except TimeoutError:
            raise ProviderFailure("timeout", "Provider timed out") from None
        except InterruptedError:
            raise ProviderFailure("interrupted", "Provider request interrupted") from None
        except (OSError, urllib.error.URLError):
            raise ProviderFailure("unavailable", "Provider connection unavailable") from None
        if response.status_code == 429:
            headers = {key.lower(): value for key, value in response.headers.items()}
            try:
                retry_after = max(0, float(headers.get("retry-after", 0)))
            except (ValueError, TypeError):
                retry_after = None
            raise ProviderFailure("rate_limit", "Provider rate limited the request", retry_after)
        if response.status_code != 200:
            raise ProviderFailure("unavailable", f"Provider HTTP status {response.status_code}")
        try:
            envelope = json.loads(response.body)
        except (ValueError, UnicodeDecodeError):
            raise ProviderFailure("parse", "Provider returned invalid response JSON") from None
        if not isinstance(envelope, dict):
            raise ProviderFailure("completion", "Provider response is not a message object")
        if envelope.get("stop_reason") == "refusal":
            raise ProviderFailure("refusal", "Provider declined extraction")
        if (envelope.get("type") != "message" or envelope.get("role") != "assistant"
                or envelope.get("stop_reason") != "end_turn"):
            raise ProviderFailure("completion", "Provider response did not complete normally")
        blocks = envelope.get("content")
        if (not isinstance(blocks, list) or not blocks
                or any(not isinstance(block, dict) or block.get("type") != "text"
                       or not isinstance(block.get("text"), str) for block in blocks)):
            raise ProviderFailure("completion", "Provider response has invalid content blocks")
        return {"status": "completed", "refusal": None,
                "output_text": "".join(block["text"] for block in blocks),
                "response_source": self.response_source}

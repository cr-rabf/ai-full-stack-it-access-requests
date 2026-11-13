# Supported provider contract

The selected HTTP contract is Anthropic Messages API, API version `2026-10-21`,
model `claude-sonnet-5-5`, endpoint `https://api.anthropic.com/v1/messages`.
Defaults are 8,192 maximum output tokens, non-streaming responses and a 60-second
timeout. `ProviderConfig` allows endpoint, model, token limit, timeout and API
version overrides. No temperature, top_p or top_k parameter is sent.
Credentials are loaded from `API_KEY` only for actual extraction. Authorization
uses Bearer authentication. Request evidence constructs redacted headers without
loading credentials. Raw HTTP error bodies and exception details are not logged.

The extraction prompt is `src/extraction_prompt.txt`. Messages are
JSON data in a user text block, separate from the system instructions. The exact
`snapshot.schema.json` is sent in `output_config.format` with type `json_schema`.
The adapter accepts only completed assistant messages with stop reason `end_turn`.
It accepts summarized, omitted and redacted thinking blocks alongside text, but
uses only text blocks, in response order, as the extraction JSON. Thinking content
is neither routed nor logged. Missing text, malformed blocks and unsupported block
types remain completion errors.
Refusal overrides any plausible text. Token exhaustion and other stop reasons are
completion errors; malformed JSON, invalid schema and non-source quotes are
rejected before routing. Each error preserves document identity and provides retry
guidance. HTTP 429 preserves Retry-After seconds; retry scheduling arrives in step 7.

Tests inject saved HTTP responses and a fake credential loader. Records from this
transport have `response_source=mock`, with attempted provider configuration
preserved separately. These tests establish request and handling behavior, not
live model accuracy or credential compatibility. No live request has been made.

Contract references checked 2026-11-13:

- [Messages API](https://platform.claude.com/docs/en/api/messages/create)
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Thinking response blocks](https://platform.claude.com/docs/en/build-with-claude/thinking)
- [Sonnet 5.5 model settings](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)

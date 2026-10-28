"""
Groq LLM access shared by every AI feature.

`_complete` makes one chat completion, on the default key and then the failsafe key, and returns
parsed JSON when a schema is given. It returns None when no key is set or every key fails, so each
caller has a rule-based fallback and nothing depends on the model being up.
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import logging

import httpx

from core.config import settings

logger = logging.getLogger("proofpath.llm")


ADVISORY = "Advisory only, final decisions rest with the competent authority."

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq accepts inline base64 images up to 4 MB
MAX_INLINE_IMAGE_BYTES = 4 * 1024 * 1024
# A different key cannot fix a malformed request (400/404/413/422), so only these move to the failsafe key
_RETRY_WITH_FAILSAFE = {401, 403, 429, 498, 500, 502, 503, 504}


def _usable(key: Optional[str]) -> bool:
    return bool(key) and not key.startswith(("mock_", "dummy_", "your_"))


def _keys() -> List[Tuple[str, str]]:
    """Default key first, failsafe second."""
    keys = []
    if _usable(settings.GROQ_API_KEY):
        keys.append(("default", settings.GROQ_API_KEY))
    if _usable(settings.GROQ_API_KEY_FAILSAFE):
        keys.append(("failsafe", settings.GROQ_API_KEY_FAILSAFE))
    return keys


def llm_enabled() -> bool:
    return bool(_keys())


def _schema_instruction(schema: Dict[str, Any]) -> str:
    return (
        "\n\nRespond with a single JSON object and nothing else. It must have exactly these keys, "
        "all present, matching this JSON Schema:\n" + json.dumps(schema)
    )


def _valid(result: Any, schema: Dict[str, Any]) -> bool:
    if not isinstance(result, dict) or not all(k in result for k in schema.get("required", [])):
        return False
    types = {"string": str, "boolean": bool, "integer": int, "number": (int, float)}
    for key, spec in schema.get("properties", {}).items():
        expected = types.get(spec.get("type"))
        value = result.get(key)
        if expected and not isinstance(value, expected):
            return False
        if expected in (int, (int, float)) and isinstance(value, bool):
            return False
        if "enum" in spec and value not in spec["enum"]:
            return False
    return True


def _complete(
    system: str,
    content: Union[str, List[Dict[str, Any]]],
    schema: Optional[Dict[str, Any]] = None,
    max_tokens: int = 4000,
    vision: bool = False,
    temperature: float = 0.2,
) -> Optional[Union[str, Dict[str, Any]]]:
    """
    One Groq chat completion, on the default key and then the failsafe key if the default
    fails (auth, rate limit, outage). Returns parsed JSON when a schema is given, otherwise text.
    Returns None when no key is configured or every key fails, so callers fall back to templates.
    """
    keys = _keys()
    if not keys:
        return None
    payload: Dict[str, Any] = {
        "model": settings.GROQ_VISION_MODEL if vision else settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system + (_schema_instruction(schema) if schema else "")},
            {"role": "user", "content": content},
        ],
        "max_completion_tokens": max_tokens,
        "temperature": temperature,
    }
    if schema:
        payload["response_format"] = {"type": "json_object"}

    for name, key in keys:
        try:
            resp = httpx.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=60.0)
        except httpx.HTTPError as e:
            logger.error(f"Groq connection error on {name} key: {e}")
            continue
        if resp.status_code != 200:
            logger.error(f"Groq API error {resp.status_code} on {name} key: {resp.text[:300]}")
            if resp.status_code in _RETRY_WITH_FAILSAFE:
                continue
            return None
        choice = (resp.json().get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            logger.warning(f"Groq output truncated on {name} key")
            return None
        text = ((choice.get("message") or {}).get("content") or "").strip()
        if name != "default":
            logger.warning("Groq call served by the failsafe key")
        if not schema:
            return text or None
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.error("Groq returned invalid JSON")
            return None
        if not _valid(result, schema):
            logger.error("Groq JSON did not match the schema")
            return None
        return result
    return None

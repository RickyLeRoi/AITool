# core/local_llm_client.py
"""OpenAI-compatible chat client (stdlib urllib, no new dependency).

Points at LOCAL_LLM_BASE_URL / LOCAL_LLM_MODEL so the backend can be swapped
later (Ollama, llama-server, or an OpenRouter-like proxy) without touching
the server code that calls this module.
"""
import json
import os
import urllib.error
import urllib.request

from _shared import cap, load_dotenv

# 20260926 ++ RG #dotenv_config: fills LOCAL_LLM_* from .env if not already
# set in the real environment (see .env.example).
load_dotenv()

# 20260926 ** RG #env_only_config: no hardcoded fallbacks - .env.example is
# the single place defaults live now. Unset means None/empty, not a guess.
DEFAULT_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL")
DEFAULT_MODEL = os.environ.get("LOCAL_LLM_MODEL")
DEFAULT_API_KEY = os.environ.get("LOCAL_LLM_API_KEY")


def _auth_headers() -> dict:
    if DEFAULT_API_KEY:
        return {"Authorization": f"Bearer {DEFAULT_API_KEY}"}
    return {}


def _not_configured() -> str:
    missing = [name for name, value in (
        ("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL),
        ("LOCAL_LLM_MODEL", DEFAULT_MODEL),
    ) if not value]
    if not missing:
        return ""
    return (
        f"[local-llm not configured] Missing: {', '.join(missing)}. "
        "Copy .env.example to .env and fill it in (see CLAUDE.md)."
    )


def _send(req: urllib.request.Request, timeout: int):
    """Perform the request. Returns (True, raw_bytes) on success or
    (False, labeled_error_message) on failure — callers never see a raised
    exception for a normal "backend not there/not happy" outcome."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.read()
    except urllib.error.HTTPError as exc:
        # 20260926 ** RG #onfeather_remote_auth: 401/403 means the backend was
        # reached but rejected us for missing/wrong credentials, not "offline".
        if exc.code in (401, 403):
            return False, (
                f"[local-llm unauthorized] {DEFAULT_BASE_URL} rejected the request "
                f"(HTTP {exc.code}). Set LOCAL_LLM_API_KEY to a valid key for this backend."
            )
        return False, f"[local-llm error] HTTP {exc.code} from {DEFAULT_BASE_URL}: {exc.reason}"
    except (urllib.error.URLError, ConnectionError) as exc:
        return False, (
            f"[local-llm unavailable] Could not reach {DEFAULT_BASE_URL} ({exc}). "
            "Set LOCAL_LLM_BASE_URL/LOCAL_LLM_MODEL to a running backend "
            "(Ollama, llama-server, or an OpenRouter-like proxy)."
        )
    except Exception as exc:
        return False, f"[local-llm error] {exc}"


def chat(prompt: str, system: str = "", max_chars: int = 3000, timeout: int = 120) -> str:
    """Send one prompt to the configured local/free-tier model. Always labels
    the result as an unverified local draft — never treat it as final."""
    error = _not_configured()
    if error:
        return error

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({"model": DEFAULT_MODEL, "messages": messages}).encode("utf-8")
    headers = {"Content-Type": "application/json", **_auth_headers()}
    req = urllib.request.Request(
        f"{DEFAULT_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    ok, result = _send(req, timeout)
    if not ok:
        return result

    try:
        data = json.loads(result.decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError):
        return f"[local-llm unexpected response shape] {cap(result.decode('utf-8', errors='replace'), 500)}"

    return cap(f"[local-model draft, verify before use]\n{text}", max_chars)


def status(timeout: int = 15) -> str:
    """Query the backend's quota/health endpoint (GET /status) - an
    OnFeather-free extension, not part of the OpenAI API. Other backends
    (plain Ollama, llama-server) likely don't implement it and will report
    [local-llm error] 404, which is expected there."""
    error = _not_configured()
    if error:
        return error

    req = urllib.request.Request(
        f"{DEFAULT_BASE_URL.rstrip('/')}/status",
        headers=_auth_headers(),
        method="GET",
    )
    ok, result = _send(req, timeout)
    if not ok:
        return result

    raw = result.decode("utf-8", errors="replace")
    try:
        pretty = json.dumps(json.loads(raw), indent=2)
    except json.JSONDecodeError:
        pretty = raw

    return cap(pretty, 3000)

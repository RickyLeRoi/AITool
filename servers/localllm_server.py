# servers/localllm_server.py
"""MCP server delegating low-stakes generation to a local/free-tier model.

Not wired to a real backend by default — LOCAL_LLM_BASE_URL defaults to a
local Ollama address that may not be running. Every tool here is meant for
low-stakes drafts (summaries, translations, classification), never for
anything that needs verified accuracy.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))

import local_llm_client
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("localllm")


@mcp.tool()
def local_summarize(text: str) -> str:
    """Summarize text with the local/free-tier model. Low-stakes only — verify
    before relying on it, this is a cheaper/offline draft, not a final answer."""
    return local_llm_client.chat(
        text, system="Summarize the following text concisely, in the same language it is written in."
    )


@mcp.tool()
def local_translate(text: str, target_language: str) -> str:
    """Translate text with the local/free-tier model."""
    return local_llm_client.chat(text, system=f"Translate the following text to {target_language}. Output only the translation.")


@mcp.tool()
def local_classify(text: str, categories: str) -> str:
    """Classify text into one of the given comma-separated categories."""
    return local_llm_client.chat(
        text, system=f"Classify the following text into exactly one of these categories: {categories}. Output only the category name."
    )


@mcp.tool()
def local_draft(prompt: str) -> str:
    """Generate a rough first draft (email, comment, boilerplate text) with the
    local/free-tier model. Always review before sending/using."""
    return local_llm_client.chat(prompt)


@mcp.tool()
def local_status() -> str:
    """Check the local/free-tier backend's quota and provider health (GET
    /status). Useful to tell "out of quota" apart from "actually down" before
    assuming the other local_* tools are broken. Not every backend implements
    this endpoint - expect an error on plain Ollama/llama-server."""
    return local_llm_client.status()


if __name__ == "__main__":
    mcp.run()

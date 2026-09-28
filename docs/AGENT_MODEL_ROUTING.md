# Agent model routing — what's actually possible today

Written while drafting the 10 enterprise agents, because it changes what
"agents for Haiku or Ollama" can mean in practice.

## The constraint

A Claude Code subagent's `model:` frontmatter field only accepts
Claude-family models: `haiku`, `sonnet`, `opus`, `fable`, or a specific
Claude model ID. **It cannot point at Ollama, llama.cpp, or an
OpenRouter-style endpoint.** The agent's own "brain" — the model that reads
its system prompt and does the actual reasoning — is always a Claude model.

So the 10 agents in `~/.claude/agents/` (ceo, cto, architect, dev, designer,
qa, test-engineer, frontend, backend, database) are, and can only ever be,
Claude Sonnet or Claude Haiku doing the reasoning. That part of "recreate
agents for Haiku" is already done — see each file's `model:` field
(haiku for judgement/communication-heavy roles: ceo, designer, qa;
sonnet for technical-depth roles: the other seven).

## Where Ollama / your OpenRouter-like project actually fits

Not as the agent's brain — as a **tool the agent calls** for a specific
sub-task it decides isn't worth spending Claude tokens on. That's what
`servers/localllm_server.py` is for: it exposes `local_summarize`,
`local_translate`, `local_classify`, `local_draft` as MCP tools. Any of the
10 agents can call one of those tools mid-task, the same way they call
`run_tests` or `map_repo`. The actual generation for that one call happens
on whatever backend `LOCAL_LLM_BASE_URL` points at.

**Resolved 2026-09-26**: the backend is OnFeather-free
([RickyLeRoi/OnFeather](https://github.com/RickyLeRoi/OnFeather/tree/main/onfeather-free))
running on the homelab, configured via `.env` (`LOCAL_LLM_MODEL=auto`, which
lets it route across whichever configured free-tier provider has quota
headroom; `"private"` forces local-only/Ollama). `LOCAL_LLM_API_KEY` is
required for this non-localhost instance. If `.env` isn't filled in, the
tools report "local-llm not configured"/"unavailable"/"unauthorized" per the
three distinct failure modes documented in the project CLAUDE.md, instead of
failing silently or raising.

## What this means for the agent roster

No agent file needs to change when the backend is decided — only
`LOCAL_LLM_BASE_URL`/`LOCAL_LLM_MODEL` (env vars on the `localllm` MCP
server registration). If a specific agent should be *pushed* toward using
the local model for a class of task (e.g. `designer` drafting placeholder
copy, `ceo` compressing a long status report), that's already noted in its
"Available local tools" section — always framed as an unverified draft, not
a replacement for the agent's own judgment.

## Deferred / needs RG
- None currently — backend decided and live (see above). If it ever changes
  (different homelab host, switching to plain Ollama, etc.), it's just the
  `.env` values — no code or agent-file changes needed.

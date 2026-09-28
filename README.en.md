# ClaudeLocalTools — Guide (for everyone)

*[Italiano](README.md) | English*

This guide is written for anyone, even without a developer background. If
you already know what Python, a JSON file, and an environment variable are,
feel free to skip straight to the chapters you need. If you don't, also
read the "In plain words" boxes.

> **In plain words**: this project is a small "toolbox" that runs on your
> computer. Inside it are tools that an AI assistant (Claude, Copilot,
> Gemini, etc.) can use to do practical things — run tests, read a log,
> look for forgotten passwords in code — without having to "read" the
> whole project by hand and waste time/tokens. The toolbox is called an
> **MCP server** (Model Context Protocol): it's just a program that listens
> and answers "ok, doing that" whenever an AI assistant asks it to.

---

## 1. What's inside

| Folder | What it contains |
|---|---|
| `core/` | The actual code for each function, testable on its own, without AI |
| `servers/` | 3 MCP "front desks" that expose `core/`'s functions to an AI assistant |
| `tests/` | Automated tests, one per function |
| `docs/` | Deep dives (e.g. why the agents' model can't be Ollama) |
| `.venv/` | This project's isolated Python install (doesn't touch the rest of the PC's Python) |
| `node_modules/` | Third-party, non-Node/Python MCP servers (e.g. Playwright), installed inside the project — see chapter 8 |
| `tools/` | External single-file programs (e.g. the Oracle database Toolbox) — see chapter 8 |
| `.env` / `.env.example` | Configuration variables (chapter 7) — `.env` is the real one with your values, `.env.example` is the empty template |

This project runs unchanged on Windows, macOS and Linux: the `.venv/`,
`node_modules/` and `tools/` folders above are all "rebuildable" with one
command (chapters 2 and 8) and end up holding the right program for
whichever OS you regenerate them on.

There are **3 custom-built Python servers** (`devtools`, `insights`,
`localllm`), a couple of **vendored third-party MCP servers** (chapter 8),
and **10 "agents"** (AI personas with a specific role, like `qa` or
`database`), all explained in the next chapters.

---

## 2. Prerequisites (one-time setup)

> This project is meant to run on Windows, on a Mac, and on an Ubuntu
> server unchanged — only the commands you type differ slightly from one
> system to another. From here on, wherever it matters, you'll find the
> macOS/Linux command and the Windows one stacked underneath — use the one
> for the machine you're on.

You need Python installed inside the project's `.venv/` folder, with the
required libraries. If you need to redo this from scratch (e.g. project
moved, or a new PC):

```bash
# macOS / Linux
cd ~/path/to/ClaudeLocalTools
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
```powershell
# Windows
cd c:\path\to\ClaudeLocalTools
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

Nothing else to install: no pytest, no random packages. Just the `mcp`
library (pinned below version 2, because v2 renamed things inside it and
would break everything — see `CLAUDE.md`).

---

## 3. The tools, one by one

### `devtools` server — code/test/build stuff

| Tool | What it does, in one sentence |
|---|---|
| `run_tests` | Runs the test command you give it (e.g. `pytest`) and returns a short summary: how many pass, which fail and why — instead of dumping 500 lines of output on you |
| `run_build` | Same as above but for a build/compile step: lists only errors and warnings, deduplicated |
| `map_repo` | Draws a map of the project: files, folders, and each file's main functions/classes |
| `digest_log` | Takes a long log file and tells you which lines repeat the most (useful for finding the error that's spamming the log) |
| `diff_summary` | Looks at not-yet-committed git changes and tells you what changed, in summary |

### `insights` server — analysis and reporting

| Tool | What it does, in one sentence |
|---|---|
| `fetch` | Downloads a web page and gives you its "clean" text, without HTML tags |
| `scan_secrets` | Scans the code for passwords/keys/tokens accidentally left "in the clear" |
| `scan_todos` | Collects every `TODO`, `FIXME`, `HACK` comment scattered across the project |
| `list_dependencies` | Lists the libraries the project depends on (from `package.json`, `requirements.txt`, `.csproj`) |
| `dump_schema` | Opens a database (or a `.sql` file) and lists its tables and columns |
| `status_report` | An executive summary of the project: files, recent commits, pending changes, and optionally whether tests/build pass |

### `localllm` server — delegates simple tasks to a local/free model

> **In plain words**: these tools do NOT use Claude/Copilot/Gemini to
> answer. They call a different model (e.g. one running on your homelab,
> like Ollama) for low-risk tasks, so you don't "spend" tokens on the main
> assistant for trivial work.

| Tool | What it does, in one sentence |
|---|---|
| `local_summarize` | Summarizes a text |
| `local_translate` | Translates a text into another language |
| `local_classify` | Classifies a text into one of the categories you give it |
| `local_draft` | Writes a rough first draft (email, comment, boilerplate text) for you to review by hand |
| `local_status` | Shows remaining quota for each backend provider (useful to tell "out of quota" from "actually down") — only works on backends that expose this endpoint, like OnFeather-free |

The code **no longer has any value hardcoded inside it** (no address, no
default model): everything comes only from `.env` (chapter 7). Without a
filled-in `.env`, these 5 tools reply `[local-llm not configured]`, telling
you exactly which variable is missing, instead of guessing a random
address. Once you've filled in `.env` with the address of your
[OnFeather-free](https://github.com/RickyLeRoi/OnFeather/tree/main/onfeather-free)
(or another OpenAI-compatible backend), you'll recognize three different
responses:
- `[local-llm not configured]` → `LOCAL_LLM_BASE_URL` and/or
  `LOCAL_LLM_MODEL` are missing from `.env`
- `[local-llm unavailable]` → the server just isn't responding (off, wrong
  address/port, firewall)
- `[local-llm unauthorized]` → the server responds but rejects the request
  because the key (`LOCAL_LLM_API_KEY`) is missing/wrong — this variable is
  the exception: empty/unset is a valid state ("no key"), not "not
  configured"

---

## 4. The 10 "agents" — AI assistants with a specific role

An agent is an AI assistant that's been given: a role, a limited list of
tools it can use, and a "brain" (model) suited to the task. Using them
instead of the generic chat saves time because they already know what to
look for and with which tool.

| Agent | Brain (model) | When to use it |
|---|---|---|
| `ceo` | Haiku (fast/cheap) | Project status from a business angle, priorities, a summary for non-technical readers |
| `cto` | Sonnet (more capable) | Technical decisions with business impact, technical risk, build-vs-buy |
| `architect` | Sonnet | Designing a new component, evaluating a structural refactor, defining boundaries between modules |
| `dev` | Sonnet | A small, self-contained feature/fix that isn't clearly frontend-only, backend-only, or database-only |
| `designer` | Haiku | Design critique, accessibility review, UX copy — doesn't write code |
| `qa` | Haiku | Manual test planning, bug triage, pre-release checklist — doesn't write automated tests |
| `test-engineer` | Sonnet | Writing/fixing/extending automated tests, figuring out why a suite is flaky |
| `frontend` | Sonnet | UI components, client-side state, styling, accessibility implemented in code |
| `backend` | Sonnet | API endpoints, business logic, integrations, server-side data |
| `database` | Sonnet | Database schema, migrations, query performance, indexes |

**Why Haiku for some and Sonnet for others?** Haiku is faster and cheaper,
suited to roles that mostly need to *communicate/judge* (ceo, designer,
qa). Sonnet reasons more, suited to roles that need to *write/design code*
technically. Neither can be swapped for a local model (Ollama, etc.) — a
Claude Code agent must always have a "brain" from the Claude family. Tasks
meant for a local model go through the `localllm` server (chapter 3), which
any agent can still call like any other tool. See `docs/AGENT_MODEL_ROUTING.md`
for more detail.

---

## 5. How to run the tests

### All at once

```bash
# macOS / Linux
.venv/bin/python -m unittest discover -s tests -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### A single test file

```bash
# macOS / Linux
.venv/bin/python -m unittest tests.test_todo_scanner -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest tests.test_todo_scanner -v
```

### A single test inside a file

```bash
# macOS / Linux
.venv/bin/python -m unittest tests.test_todo_scanner.TestTodoScanner.test_groups_by_marker_type -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest tests.test_todo_scanner.TestTodoScanner.test_groups_by_marker_type -v
```

(Pattern: `tests.<file_name_without_.py>.<ClassName>.<method_name>`)

### What each test file checks (72 tests total)

| Test file | What it verifies |
|---|---|
| `test_build_digest.py` | That build errors/warnings are extracted and deduplicated correctly |
| `test_deps_digest.py` | That dependencies are read correctly from `package.json`/`requirements.txt`/`.csproj` |
| `test_diff_digest.py` | That the `git diff` summary is correct |
| `test_fetch_url.py` | That downloading+cleaning a web page works |
| `test_find_secrets.py` | That detection of credentials left "in the clear" works and avoids obvious false alarms |
| `test_local_llm_client.py` | Client for the local model: no hardcoded defaults in the code (missing variables → `[local-llm not configured]`, never a network attempt), `Authorization` header sent only when the key is configured, distinguishing "not configured"/"unreachable"/"unauthorized", and `local_status()` — all with fake network calls, no real request ever leaves the PC |
| `test_log_digest.py` | That the count of most-frequent log lines is correct |
| `test_oracle_config_sync.py` | That `${VAR}` placeholder substitution in the Oracle template works, that missing values with no default raise a clear error, and above all that an `.env` change shows up immediately on the next regeneration (the core of the "hot reload" mechanism) |
| `test_project_status.py` | That the project summary report assembles the other functions correctly |
| `test_repo_map.py` | That the repository map (files/functions) is correct |
| `test_schema_digest.py` | Reading a schema from a `.sqlite` file and from a `.sql` file |
| `test_shared.py` | The common helper functions (output truncation, line deduplication, running commands) and the two `.env` functions (`parse_dotenv`, `load_dotenv`) |
| `test_test_digest.py` | That the test summary (passed/failed) is extracted correctly, without mixing up lower-/upper-case lines |
| `test_todo_scanner.py` | That TODO/FIXME/HACK/XXX are grouped correctly |

### Running a script on its own, without going through any AI assistant

```bash
# macOS / Linux
.venv/bin/python core/test_digest.py "pytest" .
.venv/bin/python core/repo_map.py .
```
```powershell
# Windows
.venv\Scripts\python.exe core\test_digest.py "pytest" .
.venv\Scripts\python.exe core\repo_map.py .
```

---

## 6. Making these servers available to an AI assistant

> **In plain words**: every MCP-compatible AI assistant has a config file
> (or a command) where you tell it: "to talk to server X, run this
> program." The "recipe" is always the same:
>
> - **command**: this project's Python →
>   `.venv/bin/python` (macOS/Linux) or `.venv\Scripts\python.exe` (Windows)
> - **argument**: the server file you want to use, e.g. →
>   `servers/devtools_server.py`
>
> Only *where* you write this recipe changes (and the path style, `/` vs
> `\`), depending on the assistant and the OS.

### 6.1 Claude Code (this very tool, CLI or VS Code extension)

Already done for this project on this PC (the servers show as
"Connected"). To redo it from scratch, on another PC or another OS:

```bash
# macOS / Linux
claude mcp add --scope user devtools  -- /path/to/ClaudeLocalTools/.venv/bin/python /path/to/ClaudeLocalTools/servers/devtools_server.py
claude mcp add --scope user insights  -- /path/to/ClaudeLocalTools/.venv/bin/python /path/to/ClaudeLocalTools/servers/insights_server.py
claude mcp add --scope user localllm  -- /path/to/ClaudeLocalTools/.venv/bin/python /path/to/ClaudeLocalTools/servers/localllm_server.py
```
```powershell
# Windows
claude mcp add --scope user devtools  -- C:\path\to\ClaudeLocalTools\.venv\Scripts\python.exe C:\path\to\ClaudeLocalTools\servers\devtools_server.py
claude mcp add --scope user insights  -- C:\path\to\ClaudeLocalTools\.venv\Scripts\python.exe C:\path\to\ClaudeLocalTools\servers\insights_server.py
claude mcp add --scope user localllm  -- C:\path\to\ClaudeLocalTools\.venv\Scripts\python.exe C:\path\to\ClaudeLocalTools\servers\localllm_server.py
```

On some Windows setups the `claude` command isn't on PATH and needs to be
called with the full path (e.g.
`%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<version>\resources\native-binary\claude.exe`)
— on Mac or Ubuntu, just try `claude` from a terminal first: it's very
likely already reachable without a full path there.

To check everything is connected (same on every OS):

```
claude mcp list
```

Registered servers live in a file called `.claude.json` in your user
folder (`%USERPROFILE%\.claude.json` on Windows, `~/.claude.json` on
macOS/Linux), under the `mcpServers` key. You can also edit it by hand with
a text editor (with Claude Code closed), if you prefer.

### 6.2 VS Code with GitHub Copilot Chat (Agent mode)

Copilot Chat in VS Code reads an `mcp.json` file shaped like this (on
macOS/Linux, paths use `/` and have no drive letter):

```json
{
  "servers": {
    "devtools": {
      "type": "stdio",
      "command": "/path/to/ClaudeLocalTools/.venv/bin/python",
      "args": ["/path/to/ClaudeLocalTools/servers/devtools_server.py"]
    }
  }
}
```

On Windows, same structure but with doubled backslashes (required in
JSON):

```json
{
  "servers": {
    "devtools": {
      "type": "stdio",
      "command": "C:\\path\\to\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\ClaudeLocalTools\\servers\\devtools_server.py"]
    },
    "insights": {
      "type": "stdio",
      "command": "C:\\path\\to\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\ClaudeLocalTools\\servers\\insights_server.py"]
    },
    "localllm": {
      "type": "stdio",
      "command": "C:\\path\\to\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\ClaudeLocalTools\\servers\\localllm_server.py"]
    }
  }
}
```

(repeat the `devtools` block for `insights` and `localllm` in the
macOS/Linux version too, only changing the `.py` file name)

- For a **single project**: save this content to `.vscode/mcp.json`
  (Windows: `.vscode\mcp.json`) inside the project folder where you want to
  use it.
- For **every project**: open the Command Palette (`Ctrl+Shift+P`) and
  search "MCP: Open User Configuration" — VS Code opens the user-level MCP
  file, paste the same content there.
- **Important**: MCP tools only work in Copilot chat's **Agent** mode, not
  in "Ask" mode. Check the mode selector at the top of the chat.

### 6.3 GitHub Copilot CLI

Reads its configuration from `.mcp.json` in the project folder, or from
`~/.copilot/mcp-config.json` for every project. The exact shape can change
between tool versions: the official guide is here →
[Adding MCP servers for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers).
The command/argument "recipe" from the box above still applies.

### 6.4 Gemini CLI (Google)

Same idea, different file: `~/.gemini/settings.json` on macOS/Linux,
`%USERPROFILE%\.gemini\settings.json` on Windows (or
`.gemini/settings.json` inside the project), `mcpServers` key:

```json
{
  "mcpServers": {
    "devtools": {
      "command": "/path/to/ClaudeLocalTools/.venv/bin/python",
      "args": ["/path/to/ClaudeLocalTools/servers/devtools_server.py"]
    }
  }
}
```

On Windows:

```json
{
  "mcpServers": {
    "devtools": {
      "command": "C:\\path\\to\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\ClaudeLocalTools\\servers\\devtools_server.py"]
    }
  }
}
```

Repeat the block for `insights` and `localllm`. Restart Gemini CLI after
saving.

### 6.5 ChatGPT (an important limitation, worth knowing before you try)

ChatGPT **cannot connect directly to a server running on your PC**. Its
"Developer mode" (Settings → Apps & Connectors) only accepts MCP servers
reachable over the internet (HTTP/SSE), not a local script like these —
short of using a separate OpenAI product to "tunnel" to a local machine,
and even then only on Pro/Plus/Business/Enterprise/Education plans. For
this project, today, **ChatGPT isn't a practical client** without extra
networking work that goes beyond the scope of these tools. If you really
need it, let's talk and consider a tunnel, but it's not a "checkbox to
tick."

### 6.6 Claude Desktop (the app, not the VS Code extension)

Same file as Claude Code (`~/.claude.json`), or, for the separate Desktop
app, its `claude_desktop_config.json` with the exact same shape shown in
6.2 but with the `mcpServers` key instead of `servers`. If you only use the
VS Code extension (as on this PC), you don't need this: it's already
configured.

---

## 7. Configuring environment variables (e.g. the local model)

> As of 2026-09-26 the code **no longer contains any default value**: if a
> variable below isn't set anywhere, the tool that needs it tells you
> clearly (`[local-llm not configured]`) instead of guessing a random
> address. `.env.example` is the only place these "example" values remain
> written.

This project reads three variables, all for the `localllm` server
(chapter 3) — the other two servers don't read any variable:

- `LOCAL_LLM_BASE_URL` — backend address. **Required**, no default in the
  code. `.env.example` proposes `127.0.0.1` (loopback) as a neutral
  placeholder — replace it with the real address of your
  [OnFeather-free](https://github.com/RickyLeRoi/OnFeather/tree/main/onfeather-free)
  (or another OpenAI-compatible backend).
- `LOCAL_LLM_MODEL` — the model name to use on that backend. **Required**,
  no default in the code. `.env.example` proposes `auto`, one of
  OnFeather-free's special names that lets it pick whichever provider has
  the most headroom; there's also `private` to stay strictly local. A
  literal name like `llama3.1:8b` gets rejected by every configured remote
  provider — it only works if you actually have a local Ollama with that
  model pulled.
- `LOCAL_LLM_API_KEY` — this one is **genuinely optional**: empty/unset is
  a valid state ("no key"), different from "not configured". **Required
  only** with a non-localhost OnFeather-free instance: without this key the
  server responds but rejects the request (`[local-llm unauthorized]`).
  Corresponds to `ONFEATHER_API_KEY` configured server-side.

> ⚠️ **Never write the real key inside `CLAUDE.md`, `README.md`, `PLAN.md`,
> or any file that ends up in the project/repository.** It only belongs in
> an environment variable or your AI assistant's local config file (which
> isn't meant to be shared). This project's own `scan_secrets` tool exists
> specifically to catch credentials accidentally left in code.

You have 4 ways to set these variables, in order of convenience:

### A) A `.env` file in the project — the simplest

Copy `.env.example` (in the project folder) into a new file called `.env`,
in the same folder, and write the real values there:

```
LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1
LOCAL_LLM_MODEL=auto
LOCAL_LLM_API_KEY=<your-key>
```

`.env` is read automatically on every startup (by `core/_shared.py`,
function `load_dotenv()`) — nothing else needs restarting besides the MCP
server process itself. It is **local to this project** and never ends up
in git (it's in `.gitignore`); `.env.example` is the template with no real
values, meant to be shared/versioned. If a variable is already set
elsewhere (methods B/C/D below), that one always wins — `.env` only fills
in what's missing.

### B) In the registration command (Claude Code)

```bash
# macOS / Linux
claude mcp remove localllm
claude mcp add --scope user localllm -e LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1 -e LOCAL_LLM_MODEL=auto -e LOCAL_LLM_API_KEY=<your-key> -- /path/to/ClaudeLocalTools/.venv/bin/python /path/to/ClaudeLocalTools/servers/localllm_server.py
```
```powershell
# Windows
claude mcp remove localllm
claude mcp add --scope user localllm -e LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1 -e LOCAL_LLM_MODEL=auto -e LOCAL_LLM_API_KEY=<your-key> -- C:\path\to\ClaudeLocalTools\.venv\Scripts\python.exe C:\path\to\ClaudeLocalTools\servers\localllm_server.py
```

(remove-then-add because `claude mcp add` doesn't update an existing
server — it's the only clean way with the CLI)

### C) By hand, in the config file

Open `~/.claude.json` (macOS/Linux) or `%USERPROFILE%\.claude.json`
(Windows, Notepad is fine) with a text editor, find the `mcpServers` →
`localllm` → `env` section and write:

```json
"env": {
  "LOCAL_LLM_BASE_URL": "http://127.0.0.1:4141/v1",
  "LOCAL_LLM_MODEL": "auto",
  "LOCAL_LLM_API_KEY": "<your-key>"
}
```

Save and restart Claude Code (or the VS Code window). For VS Code/Copilot
or Gemini CLI, make the same change in their respective
`mcp.json`/`settings.json` (chapter 6), always inside an
`"env": { ... }` block next to `command`/`args`. This file stays local to
your PC regardless, it's not a project file.

### D) Operating-system environment variable (not recommended, but it exists)

```bash
# macOS / Linux - add these lines to ~/.zshrc or ~/.bashrc, then reopen the terminal
export LOCAL_LLM_BASE_URL="http://127.0.0.1:4141/v1"
export LOCAL_LLM_MODEL="auto"
export LOCAL_LLM_API_KEY="<your-key>"
```
```powershell
# Windows
setx LOCAL_LLM_BASE_URL "http://127.0.0.1:4141/v1"
setx LOCAL_LLM_MODEL "auto"
setx LOCAL_LLM_API_KEY "<your-key>"
```

Applies to *every* program on the PC, not just this project, and needs the
terminal/VS Code reopened to be picked up. Only use it if you have a
reason to want it global; otherwise prefer method A, B or C, which stay
scoped to this project only.

### How to actually verify it's connected

Simply ask the AI assistant to use `local_summarize` on any text. Four
possible responses:

- `[local-llm not configured] Missing: ...` → `LOCAL_LLM_BASE_URL` and/or
  `LOCAL_LLM_MODEL` are missing from `.env` — names exactly which one
- `[local-llm unavailable] Could not reach ...` → the address isn't
  reachable (server off, wrong IP/port, firewall)
- `[local-llm unauthorized] ... rejected the request (HTTP 401)` → the
  server responds but the key (`LOCAL_LLM_API_KEY`) is missing or wrong
- A summary prefixed with `[local-model draft, verify before use]` → it
  works — but it's still labeled as a draft to check, not a final answer

---

## 8. Other "vendored" MCP servers in the project

Besides the 3 custom-built Python servers, this project also hosts
ready-made third-party MCP servers — we didn't write them, we just
installed them **inside the project folder** instead of somewhere global
on the PC, so that if you move/re-download the project (e.g. from a git
repo) one command brings them all back, exactly like `.venv` for Python.

| Server | What it does | Needs a key/account? |
|---|---|---|
| **Playwright** (Microsoft, official) | Browser automation: opens pages, clicks, fills forms, takes screenshots — useful for end-to-end testing or AI-guided web navigation | No, runs locally, free |
| **MCP Toolbox for Databases** (Google, open source) | Lets the AI talk to a real Oracle database: lists tables, describes columns, runs queries — read-only by default | No external key, but needs a connection string + user/password for your Oracle database |

To get Playwright back after re-downloading the project:

```bash
# macOS / Linux
cd /path/to/ClaudeLocalTools
npm install
claude mcp add --scope user playwright -- /path/to/ClaudeLocalTools/node_modules/.bin/playwright-mcp
```
```powershell
# Windows
cd c:\path\to\ClaudeLocalTools
npm install
claude mcp add --scope user playwright -- c:\path\to\ClaudeLocalTools\node_modules\.bin\playwright-mcp.cmd
```

(needs Node.js: on macOS/Linux the system one, or one managed via
nvm/Homebrew, works fine; on Windows either a portable copy or your own
regular install, as long as `npm` is on PATH)

`node_modules/` doesn't end up in the repository (too heavy, and it
rebuilds with `npm install` anyway); `package.json` and
`package-lock.json` do — they're what guarantees the exact same version
reappears, on any OS.

### MCP Toolbox for Databases (Oracle) — connected, verified, and now "hot-reloadable" too

Live-tested on 2026-09-26: it actually queried the database and returned
real tables, not just "the program starts". The `oracledb` preset exposes
7 tools: `list_tables`, `execute_sql`, `list_active_sessions`,
`get_query_plan`, `list_top_sql_by_resource`, `list_tablespace_usage`,
`list_invalid_objects` — read-only by default.

**New as of 2026-09-26: the connection now lives in `.env`, like
everything else, and updates without restarting anything.** Previously the
connection string was only passed to the program at startup (like
`localllm`) — but here the "program" is a separate external executable
(`toolbox`), not our Python: changing `.env` alone would never reach it
once it had started. The fix:

1. `tools/oracledb.template.yaml` — Google's official file (downloaded
   verbatim from their repository, not hand-rewritten) with the 7 tools
   already set up, and placeholders like `${ORACLE_CONNECTION_STRING}`
   instead of real values.
2. `core/oracle_config_sync.py` — reads `.env`, replaces the placeholders
   with real values, and writes the result to `tools.yaml` (the file the
   program actually reads).
3. The `toolbox` program **notices on its own** when `tools.yaml` changes
   and reloads **without restarting** — verified live: it was launched,
   `tools.yaml` was regenerated, and within ~3 seconds its log showed
   "reloaded" without the process stopping for even a moment.

So, from now on, to change database or credentials: **edit `.env`, rerun
the sync script, done** — no `claude mcp` command needed again.

```bash
# macOS / Linux — once, after every .env change
.venv/bin/python core/oracle_config_sync.py
```
```powershell
# Windows — once, after every .env change
.venv\Scripts\python.exe core\oracle_config_sync.py
```

Or, if you'd rather not think about it: leave this command running in a
terminal and it'll do everything automatically every time you save `.env`
(stop it with Ctrl+C when you no longer need it):

```bash
.venv/bin/python core/oracle_config_sync.py --watch
```

The program (`tools/toolbox`, ~280 MB) lives inside the project but is
gitignored (too heavy). To get it back after a re-download:

```bash
# macOS (Intel) - for Apple Silicon use darwin/arm64 instead of darwin/amd64
curl -L -o tools/toolbox "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/darwin/amd64/toolbox"
chmod +x tools/toolbox

# Linux (Ubuntu server)
curl -L -o tools/toolbox "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/linux/amd64/toolbox"
chmod +x tools/toolbox
```
```powershell
# Windows
curl -L -o tools\toolbox.exe "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/windows/amd64/toolbox.exe"
```

Credentials live **only in `.env`** (gitignored) and, as a reflection of
that, in the `tools.yaml` generated by the script (also gitignored) — never
in a file that ends up in the repository. Registration (identical on every
OS, only the program's file extension changes — and done **once**, not
every time you change database):

```bash
# macOS / Linux
claude mcp add --scope user oracledb -- /path/to/ClaudeLocalTools/tools/toolbox --config /path/to/ClaudeLocalTools/tools.yaml --stdio
```
```powershell
# Windows
claude mcp add --scope user oracledb -- c:\path\to\ClaudeLocalTools\tools\toolbox.exe --config c:\path\to\ClaudeLocalTools\tools.yaml --stdio
```

If you have a .NET-style connection string
(`Data Source=(DESCRIPTION=...);USER ID=x;PASSWORD=y`), it needs unpacking
first: `ORACLE_CONNECTION_STRING` in `.env` only wants the
`HOST:PORT/SERVICE_NAME` part, username and password go into the two
separate variables — hand it over as-is and it'll get unpacked for you.

`tools.custom-example.yaml` (in the project) is an advanced reference for
if you ever need custom queries beyond the preset's ready-made ones — no
need to touch it for now. Careful: it's different from the real
`tools.yaml`, which is auto-regenerated by the script and should never be
edited by hand (it would just get overwritten).

---

## 9. Where to look for more

- `CLAUDE.md` (same folder) — compact technical reference for
  developers
- `docs/AGENT_MODEL_ROUTING.md` — why an agent can't have Ollama as its
  "brain", and how local-model routing actually works instead

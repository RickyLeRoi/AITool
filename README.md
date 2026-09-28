# ClaudeLocalTools — Guida (per tutti)

*Italiano | [English](README.en.md)*

Questa guida è scritta per chiunque, anche senza background da sviluppatore.
Se sai già cosa sono Python, un file JSON e una variabile d'ambiente, salta
pure ai capitoli che ti servono. Se non lo sai, leggi anche i riquadri
"In parole povere".

> **In parole povere**: questo progetto è una piccola "cassetta degli
> attrezzi" che gira sul tuo computer. Dentro ci sono attrezzi (li chiamiamo
> "tool") che un assistente AI (Claude, Copilot, Gemini, ecc.) può usare per
> fare cose pratiche — lanciare i test, leggere un log, cercare password
> dimenticate nel codice — senza dover "leggere" a mano tutto il progetto e
> sprecare tempo/token. La cassetta si chiama **MCP server** (Model Context
> Protocol): è solo un programma che sta in ascolto e risponde "ok, faccio
> questa cosa" quando un assistente AI glielo chiede.

---

## 1. Cosa c'è dentro

| Cartella | Cosa contiene |
|---|---|
| `core/` | Il codice vero e proprio di ogni funzione, testabile anche da solo, senza AI |
| `servers/` | 3 "sportelli" MCP che espongono le funzioni di `core/` a un assistente AI |
| `tests/` | I test automatici, uno per ogni funzione |
| `docs/` | Approfondimenti (es. perché il modello degli agenti non può essere Ollama) |
| `.venv/` | L'installazione Python isolata di questo progetto (non tocca il Python del resto del PC) |
| `node_modules/` | Server MCP di terze parti non-Node/Python (es. Playwright), installati dentro al progetto — vedi capitolo 8 |
| `tools/` | Programmi esterni scaricati come singolo file (es. il Toolbox per database Oracle) — vedi capitolo 8 |
| `.env` / `.env.example` | Le variabili di configurazione (capitolo 7) — `.env` è quello vero con i tuoi valori, `.env.example` è il modello vuoto |

Questo progetto gira senza modifiche su Windows, macOS e Linux: le cartelle
`.venv/`, `node_modules/` e `tools/` qui sopra sono tutte "ricostruibili"
con un comando (capitoli 2 e 8) e contengono il programma giusto per il
sistema operativo su cui li rigeneri.

Ci sono **3 server Python fatti su misura** (`devtools`, `insights`,
`localllm`), qualche **server MCP di terze parti** vendorizzato nel
progetto (capitolo 8), e **10 "agenti"** (personaggi AI con un ruolo
preciso, tipo `qa` o `database`), spiegati nei prossimi capitoli.

---

## 2. Prerequisiti (fatto una volta sola)

> Questo progetto è pensato per girare su Windows, su un Mac e su un
> server Ubuntu senza modifiche — solo i comandi da digitare cambiano un
> po' da un sistema all'altro. Da qui in poi, dove serve, trovi il comando
> per macOS/Linux e quello per Windows uno sotto l'altro: usa quello del
> computer su cui ti trovi.

Serve Python installato nella cartella `.venv/` del progetto, con le
librerie richieste. Se devi rifarlo da zero (es. progetto spostato o PC
nuovo):

```bash
# macOS / Linux
cd ~/percorso/del/progetto/ClaudeLocalTools
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
```powershell
# Windows
cd c:\Tools\Workspace\Auth\Projects\ClaudeLocalTools
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

Non serve installare altro: niente pytest, niente pacchetti a caso. Solo
la libreria `mcp` (bloccata sotto la versione 2, perché la 2 ha rinominato
delle cose al suo interno e romperebbe tutto — vedi `CLAUDE.md`).

---

## 3. I tool, spiegati uno per uno

### Server `devtools` — cose che riguardano codice/test/build

| Tool | Cosa fa, in una frase |
|---|---|
| `run_tests` | Lancia il comando di test che gli dai (es. `pytest`) e ti restituisce un riassunto corto: quanti passano, quali falliscono e perché — invece di scaricarti addosso 500 righe di output |
| `run_build` | Come sopra ma per una build/compilazione: elenca solo errori e warning, senza duplicati |
| `map_repo` | Disegna la mappa del progetto: file, cartelle, e le funzioni/classi principali di ogni file |
| `digest_log` | Prende un file di log lungo e ti dice quali righe si ripetono di più (utile per trovare l'errore che spamma il log) |
| `diff_summary` | Guarda le modifiche non ancora committate in git e ti dice cosa è cambiato, in sintesi |

### Server `insights` — analisi e report

| Tool | Cosa fa, in una frase |
|---|---|
| `fetch` | Scarica una pagina web e te ne dà il testo "pulito", senza tag HTML |
| `scan_secrets` | Cerca nel codice password/chiavi/token scritti per sbaglio "in chiaro" |
| `scan_todos` | Raccoglie tutti i commenti tipo `TODO`, `FIXME`, `HACK` sparsi nel progetto |
| `list_dependencies` | Elenca le librerie da cui dipende il progetto (da `package.json`, `requirements.txt`, `.csproj`) |
| `dump_schema` | Apre un database (o un file `.sql`) e ti elenca tabelle e colonne |
| `status_report` | Un riassunto esecutivo del progetto: file, commit recenti, modifiche in sospeso, ed eventualmente se test/build passano |

### Server `localllm` — delega compiti semplici a un modello locale/gratuito

> **In parole povere**: questi tool NON usano Claude/Copilot/Gemini per
> rispondere. Chiamano un altro modello (es. uno che gira sul tuo homelab,
> tipo Ollama) per compiti a basso rischio, così non "spendi" token
> sull'assistente principale per un lavoro banale.

| Tool | Cosa fa, in una frase |
|---|---|
| `local_summarize` | Riassume un testo |
| `local_translate` | Traduce un testo in un'altra lingua |
| `local_classify` | Classifica un testo in una delle categorie che gli dai |
| `local_draft` | Scrive una prima bozza grezza (email, commento, testo standard) da rivedere a mano |
| `local_status` | Mostra la quota residua per ogni provider del backend (utile per capire se un errore è "quota finita" o "davvero giù") — funziona solo su backend che espongono questo endpoint, come OnFeather-free |

Il codice **non ha più nessun valore scritto al suo interno** (niente
indirizzo, niente modello di default): tutto viene solo da `.env` (capitolo
7). Senza un `.env` compilato, questi 5 tool rispondono
`[local-llm not configured]` dicendoti esattamente quale variabile manca,
invece di provare a indovinare o usare un indirizzo a caso. Una volta
compilato `.env` con l'indirizzo del tuo
[OnFeather-free](https://github.com/RickyLeRoi/OnFeather/tree/main/onfeather-free)
(o di un altro backend OpenAI-compatible), riconosci tre risposte diverse:
- `[local-llm not configured]` → manca `LOCAL_LLM_BASE_URL` e/o
  `LOCAL_LLM_MODEL` in `.env`
- `[local-llm unavailable]` → il server non risponde proprio (spento,
  indirizzo/porta sbagliati, firewall)
- `[local-llm unauthorized]` → il server risponde ma rifiuta la richiesta
  perché manca/è sbagliata la chiave (`LOCAL_LLM_API_KEY`) — questa
  variabile fa eccezione: vuota/assente è uno stato valido ("nessuna
  chiave"), non "non configurato"

---

## 4. I 10 "agenti" — assistenti AI con un ruolo preciso

Un agente è un assistente AI a cui è stato dato: un ruolo, un elenco
limitato di tool che può usare, e un "cervello" (modello) adatto al compito.
Usarli invece del chat generico ti fa risparmiare tempo perché sanno già
cosa cercare e con che tool.

| Agente | Cervello (modello) | Quando usarlo |
|---|---|---|
| `ceo` | Haiku (veloce/economico) | Stato del progetto in ottica business, priorità, riassunto per chi non è tecnico |
| `cto` | Sonnet (più capace) | Decisioni tecniche con impatto business, rischio tecnico, build-vs-buy |
| `architect` | Sonnet | Progettare un nuovo componente, valutare un refactor strutturale, definire i confini tra moduli |
| `dev` | Sonnet | Una feature/fix piccola e autosufficiente che non è chiaramente solo frontend, solo backend o solo database |
| `designer` | Haiku | Critica di design, revisione accessibilità, testi UX — non scrive codice |
| `qa` | Haiku | Piano di test manuale, triage di bug, checklist prima di rilasciare — non scrive test automatici |
| `test-engineer` | Sonnet | Scrivere/riparare/estendere test automatici, capire perché una suite è instabile |
| `frontend` | Sonnet | Componenti UI, stato lato client, stile, accessibilità implementata nel codice |
| `backend` | Sonnet | Endpoint API, logica di business, integrazioni, dati lato server |
| `database` | Sonnet | Schema del database, migrazioni, performance delle query, indici |

**Perché Haiku per alcuni e Sonnet per altri?** Haiku è più veloce ed
economico, adatto a chi deve soprattutto *comunicare/valutare* (ceo,
designer, qa). Sonnet ragiona di più, adatto a chi deve *scrivere/progettare
codice* in modo tecnico. Nessuno dei due può essere sostituito con un
modello locale (Ollama, ecc.) — un agente Claude Code deve sempre avere un
"cervello" della famiglia Claude. I compiti per un modello locale passano
dal server `localllm` (capitolo 3), che un agente può comunque chiamare
come un tool qualsiasi. Approfondimento in `docs/AGENT_MODEL_ROUTING.md`.

---

## 5. Come lanciare i test

### Tutti insieme

```bash
# macOS / Linux
.venv/bin/python -m unittest discover -s tests -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Un solo file di test

```bash
# macOS / Linux
.venv/bin/python -m unittest tests.test_todo_scanner -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest tests.test_todo_scanner -v
```

### Un solo test dentro un file

```bash
# macOS / Linux
.venv/bin/python -m unittest tests.test_todo_scanner.TestTodoScanner.test_groups_by_marker_type -v
```
```powershell
# Windows
.venv\Scripts\python.exe -m unittest tests.test_todo_scanner.TestTodoScanner.test_groups_by_marker_type -v
```

(Schema: `tests.<nome_file_senza_.py>.<NomeClasse>.<nome_metodo>`)

### Cosa testa ogni file (72 test in totale)

| File di test | Cosa verifica |
|---|---|
| `test_build_digest.py` | Che gli errori/warning di build vengano estratti e deduplicati bene |
| `test_deps_digest.py` | Che le dipendenze vengano lette correttamente da `package.json`/`requirements.txt`/`.csproj` |
| `test_diff_digest.py` | Che il riassunto del `git diff` sia corretto |
| `test_fetch_url.py` | Che il download+pulizia di una pagina web funzioni |
| `test_find_secrets.py` | Che il rilevamento di credenziali "in chiaro" funzioni ed eviti falsi allarmi ovvi |
| `test_local_llm_client.py` | Client verso il modello locale: nessun default nel codice (variabili mancanti → `[local-llm not configured]`, mai un tentativo di rete), header `Authorization` inviato solo se la chiave è configurata, distinzione tra "non configurato"/"irraggiungibile"/"non autorizzato", e `local_status()` — tutto con chiamate di rete finte, nessuna richiesta vera esce dal PC |
| `test_log_digest.py` | Che il conteggio delle righe di log più frequenti sia corretto |
| `test_oracle_config_sync.py` | Che la sostituzione dei segnaposto `${VAR}` nel template Oracle funzioni, che i valori mancanti senza default diano un errore chiaro, e soprattutto che una modifica a `.env` si veda subito nella rigenerazione successiva (il cuore del meccanismo "a caldo") |
| `test_project_status.py` | Che il report riassuntivo del progetto assembli bene le altre funzioni |
| `test_repo_map.py` | Che la mappa del repository (file/funzioni) sia corretta |
| `test_schema_digest.py` | Lettura schema da file `.sqlite` e da file `.sql` |
| `test_shared.py` | Le funzioni di supporto comuni (troncamento output, deduplica righe, esecuzione comandi) e le due funzioni per `.env` (`parse_dotenv`, `load_dotenv`) |
| `test_test_digest.py` | Che il riassunto dei test (passati/falliti) sia estratto bene, senza confondere righe minuscole/maiuscole |
| `test_todo_scanner.py` | Che TODO/FIXME/HACK/XXX vengano raggruppati bene |

### Lanciare uno script da solo, senza passare da nessun assistente AI

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

## 6. Come rendere questi server disponibili a un assistente AI

> **In parole povere**: ogni assistente AI compatibile con MCP ha un file
> di configurazione (o un comando) in cui gli dici: "per parlare con il
> server X, esegui questo programma". La "ricetta" è sempre la stessa:
>
> - **comando**: il Python di questo progetto →
>   `.venv/bin/python` (macOS/Linux) o `.venv\Scripts\python.exe` (Windows)
> - **argomento**: il file del server che vuoi usare, es. →
>   `servers/devtools_server.py`
>
> Cambia solo *dove* scrivi questa ricetta (e lo stile dei percorsi, `/` vs
> `\`), a seconda dell'assistente e del sistema operativo.

### 6.1 Claude Code (questo stesso strumento, CLI o estensione VS Code)

Già fatto per questo progetto su questo PC (i server risultano
"Connected"). Per rifarlo da capo, su un altro PC o su un altro OS:

```bash
# macOS / Linux
claude mcp add --scope user devtools  -- /percorso/ClaudeLocalTools/.venv/bin/python /percorso/ClaudeLocalTools/servers/devtools_server.py
claude mcp add --scope user insights  -- /percorso/ClaudeLocalTools/.venv/bin/python /percorso/ClaudeLocalTools/servers/insights_server.py
claude mcp add --scope user localllm  -- /percorso/ClaudeLocalTools/.venv/bin/python /percorso/ClaudeLocalTools/servers/localllm_server.py
```
```powershell
# Windows
claude mcp add --scope user devtools  -- C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\.venv\Scripts\python.exe C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\servers\devtools_server.py
claude mcp add --scope user insights  -- C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\.venv\Scripts\python.exe C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\servers\insights_server.py
claude mcp add --scope user localllm  -- C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\.venv\Scripts\python.exe C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\servers\localllm_server.py
```

Su **questo PC Windows** il comando `claude` non è nel PATH, va chiamato
con il percorso completo:
`%USERPROFILE%\.vscode\extensions\anthropic.claude-code-<versione>\resources\native-binary\claude.exe`
— sul Mac o sull'Ubuntu, prova prima semplicemente `claude` da un
terminale: è molto probabile che lì sia già raggiungibile senza percorso
completo.

Per controllare che sia tutto collegato (uguale su tutti gli OS):

```
claude mcp list
```

I server registrati vivono in un file chiamato `.claude.json` nella tua
cartella utente (`%USERPROFILE%\.claude.json` su Windows, `~/.claude.json`
su macOS/Linux), dentro la chiave `mcpServers`. Puoi anche modificarlo a
mano con un editor di testo (con Claude Code chiuso), se preferisci.

### 6.2 VS Code con GitHub Copilot Chat (modalità Agent)

Copilot Chat in VS Code legge un file `mcp.json` con questa forma
(su macOS/Linux i percorsi usano `/` e non hanno lettera di unità):

```json
{
  "servers": {
    "devtools": {
      "type": "stdio",
      "command": "/percorso/ClaudeLocalTools/.venv/bin/python",
      "args": ["/percorso/ClaudeLocalTools/servers/devtools_server.py"]
    }
  }
}
```

Su Windows, stessa struttura ma con backslash raddoppiati (obbligatorio in JSON):

```json
{
  "servers": {
    "devtools": {
      "type": "stdio",
      "command": "C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\servers\\devtools_server.py"]
    },
    "insights": {
      "type": "stdio",
      "command": "C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\servers\\insights_server.py"]
    },
    "localllm": {
      "type": "stdio",
      "command": "C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\servers\\localllm_server.py"]
    }
  }
}
```

(ripeti il blocco `devtools` anche per `insights` e `localllm` nella
versione macOS/Linux, cambiando solo il nome del file `.py`)

- Per un **singolo progetto**: salva questo contenuto in
  `.vscode/mcp.json` (Windows: `.vscode\mcp.json`) dentro la cartella del progetto in cui vuoi usarlo.
- Per **tutti i progetti**: apri la Command Palette (`Ctrl+Shift+P`) e
  cerca "MCP: Open User Configuration" — VS Code ti apre il file MCP a
  livello utente, ci incolli lo stesso contenuto.
- **Importante**: i tool MCP funzionano solo in modalità **Agent** della
  chat di Copilot, non in modalità "Ask". Controlla il selettore di
  modalità in alto nella chat.

### 6.3 GitHub Copilot CLI

Legge la configurazione da `.mcp.json` nella cartella del progetto, oppure
da `~/.copilot/mcp-config.json` per tutti i progetti. La forma esatta può
cambiare da una versione all'altra dello strumento: la guida ufficiale è
qui → [Adding MCP servers for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers).
La "ricetta" comando/argomento del riquadro sopra resta comunque valida.

### 6.4 Gemini CLI (Google)

Stesso principio, file diverso: `~/.gemini/settings.json` su macOS/Linux,
`%USERPROFILE%\.gemini\settings.json` su Windows (oppure `.gemini/settings.json`
dentro al progetto), chiave `mcpServers`:

```json
{
  "mcpServers": {
    "devtools": {
      "command": "/percorso/ClaudeLocalTools/.venv/bin/python",
      "args": ["/percorso/ClaudeLocalTools/servers/devtools_server.py"]
    }
  }
}
```

Su Windows:

```json
{
  "mcpServers": {
    "devtools": {
      "command": "C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Tools\\Workspace\\Auth\\Projects\\ClaudeLocalTools\\servers\\devtools_server.py"]
    }
  }
}
```

Ripeti il blocco per `insights` e `localllm`. Dopo aver salvato, riavvia
Gemini CLI.

### 6.5 ChatGPT (limite importante, da sapere prima di provarci)

ChatGPT **non può collegarsi direttamente a un server che gira sul tuo
PC**. Il suo "Developer mode" (Impostazioni → Apps & Connectors) accetta
solo server MCP raggiungibili da internet (HTTP/SSE), non uno script
locale come questi — a meno di usare un prodotto separato di OpenAI per
fare da "tunnel" verso una macchina locale, e comunque solo sui piani
Pro/Plus/Business/Enterprise/Education. Per questo progetto, oggi, **ChatGPT
non è un client praticabile** senza un lavoro di rete aggiuntivo che va
oltre lo scopo di questi tool. Se ti serve davvero, fammelo sapere e
valutiamo un tunnel, ma non è un "flag da spuntare".

### 6.6 Claude Desktop (l'app, non l'estensione VS Code)

Stesso file di Claude Code (`~/.claude.json`) oppure, per l'app Desktop
separata, il suo `claude_desktop_config.json` con la stessa identica forma
mostrata al punto 6.2 ma con chiave `mcpServers` invece di `servers`. Se
usi solo l'estensione VS Code (come in questo PC), non ti serve: è già
configurato.

---

## 7. Configurare le variabili d'ambiente (es. il modello locale)

> Dal 26/09/2026 il codice **non contiene più nessun valore di default**:
> se una variabile qui sotto non è impostata da nessuna parte, il tool che
> ne ha bisogno te lo dice chiaramente (`[local-llm not configured]`)
> invece di indovinare un indirizzo a caso. `.env.example` è l'unico posto
> dove questi valori "di esempio" restano scritti.

Le variabili che questo progetto legge sono tre, tutte per il server
`localllm` (capitolo 3) — gli altri due server non leggono nessuna
variabile:

- `LOCAL_LLM_BASE_URL` — indirizzo del backend. **Obbligatoria**, nessun
  default nel codice. `.env.example` propone `127.0.0.1` (loopback) come
  segnaposto neutro — va sostituito con l'indirizzo vero del tuo
  [OnFeather-free](https://github.com/RickyLeRoi/OnFeather/tree/main/onfeather-free)
  (o altro backend OpenAI-compatible).
- `LOCAL_LLM_MODEL` — nome del modello da usare su quel backend.
  **Obbligatoria**, nessun default nel codice. `.env.example` propone
  `auto`, uno dei nomi speciali di OnFeather-free che fa scegliere a lui il
  provider con più margine; c'è anche `private` per restare rigorosamente
  locale. Un nome letterale come `llama3.1:8b` viene rifiutato da tutti i
  provider remoti configurati — va bene solo se hai davvero un Ollama
  locale con quel modello scaricato.
- `LOCAL_LLM_API_KEY` — questa invece è **davvero opzionale**: vuota/assente
  è uno stato valido ("nessuna chiave"), diverso da "non configurato".
  **Obbligatoria solo** con OnFeather-free non in localhost: senza questa
  chiave il server risponde ma rifiuta la richiesta
  (`[local-llm unauthorized]`). Corrisponde alla `ONFEATHER_API_KEY`
  configurata lato server.

> ⚠️ **Non scrivere mai la chiave vera dentro `CLAUDE.md`, `README.md`, `PLAN.md`
> o qualsiasi file che finisce nel progetto/nel repository.** Va messa solo
> come variabile d'ambiente o nel file di configurazione locale del tuo
> assistente AI (che non è pensato per essere condiviso). Il tool
> `scan_secrets` di questo stesso progetto esiste apposta per beccare
> credenziali lasciate per sbaglio nel codice.

Hai 4 modi per impostare queste variabili, in ordine di praticità:

### A) File `.env` nel progetto — il più semplice

Copia `.env.example` (nella cartella del progetto) in un nuovo file
chiamato `.env`, nella stessa cartella, e scrivi lì i valori veri:

```
LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1
LOCAL_LLM_MODEL=auto
LOCAL_LLM_API_KEY=<la-tua-chiave>
```

`.env` viene letto automaticamente a ogni avvio (da `core/_shared.py`,
funzione `load_dotenv()`) — non serve riavviare nient'altro oltre al
processo del server MCP. È **locale a questo progetto** e non finisce mai
in git (è nel `.gitignore`); `.env.example` invece è il template senza
valori veri, pensato per essere condiviso/versionato. Se una variabile è già
impostata altrove (metodi B/C/D qui sotto), quella vince sempre — `.env`
riempie solo quello che manca.

### B) Nel comando di registrazione (Claude Code)

```bash
# macOS / Linux
claude mcp remove localllm
claude mcp add --scope user localllm -e LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1 -e LOCAL_LLM_MODEL=auto -e LOCAL_LLM_API_KEY=<la-tua-chiave> -- /percorso/ClaudeLocalTools/.venv/bin/python /percorso/ClaudeLocalTools/servers/localllm_server.py
```
```powershell
# Windows
claude mcp remove localllm
claude mcp add --scope user localllm -e LOCAL_LLM_BASE_URL=http://127.0.0.1:4141/v1 -e LOCAL_LLM_MODEL=auto -e LOCAL_LLM_API_KEY=<la-tua-chiave> -- C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\.venv\Scripts\python.exe C:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\servers\localllm_server.py
```

(si rimuove e si riaggiunge perché `claude mcp add` non aggiorna un server
già esistente — è l'unico modo pulito con la CLI)

### C) A mano, nel file di configurazione

Apri `~/.claude.json` (macOS/Linux) o `%USERPROFILE%\.claude.json`
(Windows, Blocco Note va bene) con un editor di testo, trova la sezione
`mcpServers` → `localllm` → `env` e scrivi:

```json
"env": {
  "LOCAL_LLM_BASE_URL": "http://127.0.0.1:4141/v1",
  "LOCAL_LLM_MODEL": "auto",
  "LOCAL_LLM_API_KEY": "<la-tua-chiave>"
}
```

Salva e riavvia Claude Code (o la finestra di VS Code). Per VS
Code/Copilot o Gemini CLI, la stessa modifica va fatta nel loro
`mcp.json`/`settings.json` rispettivi (capitolo 6), sempre dentro un blocco
`"env": { ... }` accanto a `command`/`args`. Questo file resta comunque
locale sul tuo PC, non è un file di progetto.

### D) Variabile d'ambiente del sistema operativo (sconsigliato, ma esiste)

```bash
# macOS / Linux - aggiungi queste righe a ~/.zshrc o ~/.bashrc, poi riapri il terminale
export LOCAL_LLM_BASE_URL="http://127.0.0.1:4141/v1"
export LOCAL_LLM_MODEL="auto"
export LOCAL_LLM_API_KEY="<la-tua-chiave>"
```
```powershell
# Windows
setx LOCAL_LLM_BASE_URL "http://127.0.0.1:4141/v1"
setx LOCAL_LLM_MODEL "auto"
setx LOCAL_LLM_API_KEY "<la-tua-chiave>"
```

Vale per *tutti* i programmi del PC, non solo per questo progetto, e serve
riaprire il terminale/VS Code perché venga letta. Usalo solo se hai un
motivo per volerla globale; altrimenti preferisci il metodo A, B o C, che
restano legati a questo progetto soltanto.

### Come verificare che sia collegato davvero

Chiedi semplicemente all'assistente AI di usare `local_summarize` su un
testo qualsiasi. Quattro risposte possibili:

- `[local-llm not configured] Missing: ...` → manca `LOCAL_LLM_BASE_URL`
  e/o `LOCAL_LLM_MODEL` in `.env` — nomina esattamente quale
- `[local-llm unavailable] Could not reach ...` → l'indirizzo non è
  raggiungibile (server spento, IP/porta sbagliati, firewall)
- `[local-llm unauthorized] ... rejected the request (HTTP 401)` → il
  server risponde ma la chiave (`LOCAL_LLM_API_KEY`) manca o è sbagliata
- Un riassunto preceduto da `[local-model draft, verify before use]` →
  funziona — ma è comunque etichettato come bozza da controllare, non una
  risposta definitiva

---

## 8. Altri server MCP "vendorizzati" nel progetto

Oltre ai 3 server Python fatti su misura, questo progetto ospita anche
server MCP di terze parti già pronti — non li abbiamo scritti noi, li
abbiamo solo installati **dentro alla cartella del progetto** invece che in
un posto globale del PC, così se sposti/riscarichi il progetto (es. da un
repo git) basta un comando per riaverli tutti, esattamente come `.venv` per
Python.

| Server | Cosa fa | Serve una chiave/account? |
|---|---|---|
| **Playwright** (Microsoft, ufficiale) | Automazione browser: apre pagine, clicca, compila form, fa screenshot — utile per test end-to-end o navigazione web guidata dall'AI | No, gira in locale, gratis |
| **MCP Toolbox for Databases** (Google, open source) | Fa parlare l'AI con un database Oracle vero: elenca tabelle, descrive colonne, esegue query — di norma in sola lettura | No chiave esterna, ma serve una stringa di connessione + utente/password del tuo database Oracle |

Per riavere Playwright dopo aver riscaricato il progetto:

```bash
# macOS / Linux
cd /percorso/ClaudeLocalTools
npm install
claude mcp add --scope user playwright -- /percorso/ClaudeLocalTools/node_modules/.bin/playwright-mcp
```
```powershell
# Windows
cd c:\Tools\Workspace\Auth\Projects\ClaudeLocalTools
npm install
claude mcp add --scope user playwright -- c:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\node_modules\.bin\playwright-mcp.cmd
```

(serve Node.js: su macOS/Linux quello di sistema o gestito con
nvm/Homebrew va benissimo; su Windows quello portable già presente in
`C:\Tools\Workspace\bin\node\`, oppure una tua installazione normale se
`npm` è già nel PATH)

`node_modules/` non finisce nel repository (troppo pesante, e comunque
si ricrea con `npm install`); `package.json` e `package-lock.json` sì, sono
loro a garantire che riappaia la stessa identica versione — su qualsiasi OS.

### MCP Toolbox for Databases (Oracle) — collegato, verificato, e ora anche "a caldo"

Attivo e testato dal vivo il 2026-09-26: ha davvero interrogato il database
e restituito tabelle reali, non solo "il programma si avvia". Il preset
`oracledb` espone 7 tool: `list_tables`, `execute_sql`,
`list_active_sessions`, `get_query_plan`, `list_top_sql_by_resource`,
`list_tablespace_usage`, `list_invalid_objects` — in sola lettura di
default.

**Novità del 26/09/2026: la connessione ora vive in `.env`, come tutto il
resto, e si aggiorna senza riavviare nulla.** Prima la stringa di
connessione veniva passata al programma solo all'avvio (come per
`localllm`) — ma qui il "programma" è un eseguibile esterno separato
(`toolbox`), non il nostro Python: cambiare `.env` da solo non lo avrebbe
mai raggiunto una volta partito. La soluzione:

1. `tools/oracledb.template.yaml` — il file ufficiale di Google (scaricato
   parola per parola dal loro repository, non riscritto a mano) con i 7
   tool già pronti, e dei segnaposto tipo `${ORACLE_CONNECTION_STRING}` al
   posto dei valori veri.
2. `core/oracle_config_sync.py` — legge `.env`, sostituisce i segnaposto
   con i valori veri, e scrive il risultato in `tools.yaml` (il file che il
   programma legge davvero).
3. Il programma `toolbox` **si accorge da solo** quando `tools.yaml`
   cambia e si ricarica **senza riavviarsi** — l'ho verificato dal vivo:
   l'ho lanciato, ho rigenerato `tools.yaml`, e nel giro di ~3 secondi il
   suo log ha mostrato "ricaricato" senza che il processo si fermasse un
   istante.

Quindi, per cambiare database o credenziali d'ora in poi: **modifichi
`.env`, rilanci lo script di sync, e basta** — nessun comando `claude mcp`
da rifare.

```bash
# macOS / Linux — una volta, dopo ogni modifica a .env
.venv/bin/python core/oracle_config_sync.py
```
```powershell
# Windows — una volta, dopo ogni modifica a .env
.venv\Scripts\python.exe core\oracle_config_sync.py
```

Oppure, se preferisci non doverci pensare: lascia questo comando aperto in
un terminale e farà tutto da solo ogni volta che salvi `.env` (fermalo con
Ctrl+C quando non ti serve più):

```bash
.venv/bin/python core/oracle_config_sync.py --watch
```

Il programma (`tools/toolbox`, ~280 MB) è dentro al progetto ma
gitignorato (troppo pesante). Per riaverlo dopo un riscarico:

```bash
# macOS (Intel) - per Apple Silicon usa darwin/arm64 al posto di darwin/amd64
curl -L -o tools/toolbox "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/darwin/amd64/toolbox"
chmod +x tools/toolbox

# Linux (server Ubuntu)
curl -L -o tools/toolbox "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/linux/amd64/toolbox"
chmod +x tools/toolbox
```
```powershell
# Windows
curl -L -o tools\toolbox.exe "https://storage.googleapis.com/mcp-toolbox-for-databases/v1.13.1/windows/amd64/toolbox.exe"
```

Le credenziali vivono **solo in `.env`** (gitignorato) e, di riflesso, nel
`tools.yaml` generato dallo script (gitignorato anche lui) — mai in un file
che finisce nel repository. Registrazione (identica su tutti gli OS, cambia
solo l'estensione del programma — e da fare **una volta sola**, non ogni
volta che cambi database):

```bash
# macOS / Linux
claude mcp add --scope user oracledb -- /percorso/ClaudeLocalTools/tools/toolbox --config /percorso/ClaudeLocalTools/tools.yaml --stdio
```
```powershell
# Windows
claude mcp add --scope user oracledb -- c:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\tools\toolbox.exe --config c:\Tools\Workspace\Auth\Projects\ClaudeLocalTools\tools.yaml --stdio
```

Se hai una stringa di connessione in stile .NET (`Data Source=(DESCRIPTION=
...);USER ID=x;PASSWORD=y`), va spacchettata prima: `ORACLE_CONNECTION_STRING`
in `.env` vuole solo la parte `HOST:PORTA/SERVICE_NAME`, utente e password
vanno nelle due variabili separate — dammela così com'è e la spacchetto io.

`tools.custom-example.yaml` (nel progetto) è un riferimento avanzato se un
giorno ti servono query personalizzate oltre a quelle già pronte del
preset — per ora non serve toccarlo. Attenzione: è diverso dal `tools.yaml`
vero e proprio, che viene rigenerato automaticamente dallo script e non va
mai modificato a mano (verrebbe sovrascritto).

---

## 9. Dove guardare per approfondire

- `AGENT.md` (stessa cartella) — riferimento tecnico compatto per chi
  sviluppa
- `docs/AGENT_MODEL_ROUTING.md` — perché un agente non può avere Ollama
  come "cervello" e come gira invece il discorso del modello locale

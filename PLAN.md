# C5 – Agent Tools: Homework Plan

**Course:** EECE 503P/798S Agentic Systems · **Assignment:** Building and Demonstrating an MCP Toolkit with FastMCP and the OpenAI Agents SDK
**Plan date:** 2026-10-21 · Everything marked ✅ *verified* below was tested on this machine or checked against the primary source today. Nothing in this plan is assumed from memory.

---

## Build status (2026-10-22)

**Done:** server, host, tests (31 offline + 2 live, all passing), smoke and demo scripts, README, `docs/summary.md` (383 words), `docs/reflection.md` and `docs/demo_script.md`.

**Still to do (you):**
1. Add `OPENAI_API_KEY` to `.env` and dry-run `scripts/demo.py`.
2. Record and upload the video.
3. Push to GitHub.
4. Review the summary and reflection, and make them your own.

**Changes made while building:**
- *Atlantis* is a real town in South Africa, so the unknown-city example is now **Xyzzyville**.
- After a real Open-Meteo timeout, the Data tool retries a timeout or 5xx response once.
- The project is now an installable package (hatchling), so `fastmcp list` and `fastmcp call trip_mcp/server.py` work.
- The host tests live in `tests/test_host.py`, not `test_host_wiring.py`. They include an agent round trip that uses a scripted stand-in for the LLM, so no API key is needed.
- `httpx2` is declared explicitly in `pyproject.toml`.

---

## 0. Verified facts that shape the plan

| Topic | Finding | How verified |
|---|---|---|
| Latest FastMCP | **4.1.3** (released 2026-10-20). The 3.4.x line is still patched. | PyPI JSON API |
| Latest OpenAI Agents SDK | **openai-agents 0.24.0** (2026-10-15). Requires `mcp>=1.19,<3`. | PyPI JSON API |
| MCP Python SDK | **mcp 2.3.0**. FastMCP 4 requires `mcp>=2.2,<3`, so the two SDKs are compatible. | PyPI metadata |
| Current MCP spec | **2026-07-28**: stateless, with `server/discover` replacing the old handshake. *Sampling*, *roots* and *logging* client features are **deprecated**, so avoid `ctx.sample()` and log to **stderr**. | modelcontextprotocol.io/docs/learn/architecture |
| Both SDKs together | ✅ Installed side by side on Python 3.12 (uv). A FastMCP 4.1.3 server over **stdio** was listed and called from the Agents SDK's `MCPServerStdio`. | Scratch probe |
| Tool → tool calls | ✅ Inside a tool, `await mcp.call_tool("other_tool", {...})` runs the other **registered** tool through the server pipeline, including argument validation, and returns `.structured_content`. Decorated functions also remain plain callables. | Scratch probe |
| Error propagation | ✅ `raise ToolError("msg")` reaches the agent as `isError=True` with the exact message. Inside the orchestrator, an inner tool's `ToolError` is re-raised as `ToolError`. Bad arguments arrive as `fastmcp.exceptions.ValidationError`, so **catch both**. | Scratch probe |
| Typed I/O | ✅ `Annotated[int, Field(ge=1, le=7)]` enforces constraints (`days=99` is rejected). Pydantic return models generate an `outputSchema`. `annotations={"readOnlyHint": True, ...}` reach the client. | Scratch probe |
| Resources | ✅ `@mcp.resource("trips://saved")` and the template `trips://{trip_id}` work. The Agents SDK client exposes `list_resources()` and `read_resource()`. | Scratch probe |
| Field names | MCP SDK v2 renamed fields to snake_case (`is_error`, `structured_content`, `output_schema`). The camelCase names still work but print deprecation warnings, so use snake_case. | Probe warnings |
| Agent's default model | `gpt-5.6-luna`, which can be overridden with the `OPENAI_DEFAULT_MODEL` env var. **`OPENAI_API_KEY` is currently NOT set on this machine.** | SDK source and env check |
| Host/Client/Server in the article | The HF post (https://huggingface.co/blog/Kseniase/mcp) is now a **teaser**. The full text is at **https://www.turingpost.com/p/mcp**. The architecture section explains Host/Client/Server mainly through **diagrams credited to modelcontextprotocol.io**, so the summary should cite the official architecture page for the precise definitions. | Read both pages |
| Weather API | **Open-Meteo**: no API key, educational use allowed, CC-BY 4.0 attribution required, 10k calls/day. ✅ An unknown city returns no `results` key. ✅ A date beyond the ~16-day window returns `{"error":true,"reason":"…out of allowed range…"}`. | curl tests and terms page |
| Local tooling | Python 3.10, 3.11 and 3.12, uv 0.12.1, git 2.47, gh 2.100, Node 24 (for MCP Inspector). No ffmpeg (not needed). | Shell |

---

## 1. Requirements traceability (every requirement in the PDF)

| ID | Requirement (PDF) | Where it is satisfied |
|---|---|---|
| R1 | Read the HF MCP article | §5.1 reading notes (full text on Turing Post) |
| R2 | Explore ≥1 existing MCP server | §5.2 Fetch server (primary), Filesystem server (contrast) |
| R3 | Summary 300–400 words: key MCP concepts incl. **Host/Client/Server relationship** | `docs/summary.md` and `.pdf` |
| R4 | Summary: critique of the server's design with class principles (single-purpose? documented? bundled?) | `docs/summary.md` paragraph 2 |
| R5 | Choose a theme | §2: Weather & Trip Planner |
| R6 | **Exactly three tools**: one Data, one Action, one Orchestration | §3 |
| R7 | Orchestration coordinates the other two (sequence/combine) | `plan_trip` calls both through `mcp.call_tool` |
| R8–R10 | Each tool: clear description, typed args, typed/documented output | Pydantic models, `Annotated[..., Field(description=...)]`, docstrings |
| R11 | Each tool single-purpose (the "and" test) | §3 boundary notes |
| R12 | Each tool handles ≥1 predictable failure with a clear error | §3 failure table, raised as `ToolError` |
| R13 | FastMCP server: `@mcp.tool`, plus `@mcp.resource` for pure lookups | `trip_mcp/server.py` (3 tools and 2 resources) |
| R14 | OpenAI Agents SDK agent as Host/Client routing to the right tool | `host/agent.py` (`Agent` + `MCPServerStdio`) |
| R15 | Unit tests / interactive scripts for every tool, including failures | `tests/` and `scripts/` |
| R16 | Screencast 5–7 min | §7 script, target 6:00–6:30 |
| R17 | Video names which tool is Data / Action / Orchestration | §7, 0:00–0:50 |
| R18 | Video shows full round trip agent → MCP client → MCP server → back | §7: hook logs, server stderr logs and OpenAI trace view |
| R19 | Video covers challenges and how they were overcome | §7, 4:45–5:45 |
| R20 | Submission includes repo link and video link | §8 checklist |
| R21 | Written Summary (PDF or Markdown) | `docs/summary.md` exported to PDF |
| R22 | Source: FastMCP server module | `trip_mcp/server.py` |
| R23 | Source: Agents SDK host/client code | `host/agent.py` |
| R24 | README with configuration and setup | `README.md` |
| R25 | Tests or example scripts including the failure case | `tests/test_tools.py`, `scripts/smoke_client.py` |
| R26 | Video hosted (e.g., YouTube unlisted) | Uploaded by you (needs your account) |
| R27 | Reflection, 1–2 paragraphs: tool boundaries, whether 3 was the right number, next steps | `docs/reflection.md` |
| P | "Latest versions" of SDKs | Pin `fastmcp==4.1.3` and `openai-agents==0.24.0` (re-check PyPI on the day you submit) |

---

## 2. Theme: **Weather & Trip Planner** (recommended)

**Why this theme:**
- It is one of the PDF's suggested themes.
- It calls a real external API (Open-Meteo) that needs no key, so failure cases happen naturally (unknown city, date outside the forecast window, network down).
- The three categories map onto it cleanly. The PDF's own example orchestration tool is `plan_trip`.

Beirut makes a natural demo city.

*Alternative if you prefer: a campus/library assistant using the Open Library search API (`search_catalog`, `add_to_reading_list`, `build_reading_list`). The same architecture applies. Only the domain modules change.*

---

## 3. Tool design: exactly three tools, plus two resources

| | **Data tool** | **Action tool** | **Orchestration tool** |
|---|---|---|---|
| Name | `get_weather_forecast` | `save_trip` | `plan_trip` |
| Purpose (one sentence, no "and") | Look up the daily forecast for a city over a date range. | Persist one trip to the user's trip list. | Produce a saved, weather-aware trip plan by coordinating the two other tools. |
| Args (typed) | `city: str` (2–100 chars), `start_date: date` (default today), `days: int` (1–7, default 3) | `city: str`, `start_date: date`, `end_date: date`, `notes: str` (≤2000 chars, default "") | `city: str`, `start_date: date`, `days: int` (1–7) |
| Output (typed) | `Forecast{city, country, latitude, longitude, timezone, days: list[DayForecast{date, condition, temp_max_c, temp_min_c, precip_prob_pct}], source}` | `SavedTrip{id, city, start_date, end_date, notes, created_at}` | `TripPlan{trip: SavedTrip, forecast: Forecast, packing_list: list[str], summary: str, steps: list[str]}` |
| MCP annotations | `readOnlyHint=True, idempotentHint=True, openWorldHint=True` | `readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False` | `readOnlyHint=False, destructiveHint=False, openWorldHint=True` |
| Side effects | None | Writes `data/trips.json` (atomic write: temp file, then `os.replace`) | Only through `save_trip` |
| **Predictable failures → clear `ToolError`** | (a) Unknown city: *"No city named 'Xyzzyville' was found. Check the spelling or add the country."* (b) Date outside the forecast window: the error states the allowed range. (c) Timeout or 5xx: *"Weather service unavailable (timed out after 10 s). Try again later."* (d) `days=99` is rejected by schema validation. | (a) `end_date < start_date` (b) Duplicate trip (same city and dates): *"Already saved as trip-0002"* (c) Corrupt or unwritable store: never silently overwrites it | (a) Step 1 fails: *"plan_trip stopped at step 1 (get_weather_forecast): <reason>. Nothing was saved."*, so there is **no partial side effect** (b) Step 2 fails: *"Forecast retrieved, but saving failed: <reason>."* |

**Resources** (`@mcp.resource`, pure data lookups, **not tools**, so "exactly three tools" still holds):
- `trips://saved`: all saved trips as JSON.
- `trips://{trip_id}`: one trip. An unknown id produces a clear error.

The Agents SDK does not hand resources to the LLM automatically. The host CLI reads them directly with a `/trips` command, which shows the resource round trip in the video.

**Orchestration mechanics** (✅ verified pattern):
```python
@mcp.tool(annotations={...})
async def plan_trip(city: str, start_date: date, days: int = 3) -> TripPlan:
    try:
        fc = await mcp.call_tool("get_weather_forecast", {"city": city, "start_date": start_date.isoformat(), "days": days})
    except (ToolError, ValidationError) as e:
        raise ToolError(f"plan_trip stopped at step 1 (get_weather_forecast): {e}. Nothing was saved.")
    forecast = Forecast.model_validate(fc.structured_content)
    packing = build_packing_list(forecast)          # pure, deterministic rules
    saved = await mcp.call_tool("save_trip", {...})  # step 2, wrapped the same way
    ...
```
Calling the **registered** tools instead of duplicating their logic means the orchestrator gets the same validation and error behaviour as the agent does.

**Boundary decisions** (these go into the reflection and the video's "challenges" segment):
- Geocoding stays *inside* the data tool. "City → forecast" is one purpose from the caller's point of view. Exposing a separate geocoding tool would break the "exactly three tools" rule, and it would push coordinate handling onto the LLM.
- Packing-list rules live in a pure helper (`planning.py`) used only by the orchestrator. The PDF allows the orchestrator to "combine results", and this keeps both the data and action tools single-purpose.
- The action tool takes explicit data and never fetches weather itself. That separation is what makes the orchestration tool necessary.

---

## 4. Project structure

```
Mohammed_Farhat_C5/
├── README.md                 # setup, config, run, test, architecture diagram, attribution
├── pyproject.toml            # uv project; Python 3.12; fastmcp==4.1.3, openai-agents==0.24.0; dev: pytest, pytest-asyncio
├── uv.lock
├── .env.example              # OPENAI_API_KEY=, OPENAI_DEFAULT_MODEL=, TRIPS_FILE=data/trips.json
├── .gitignore                # .env, .venv/, data/trips.json, __pycache__/, the course PDF
├── trip_mcp/                 # ── MCP SERVER (FastMCP) ──
│   ├── __init__.py
│   ├── server.py             # FastMCP("trip-planner"): 3 @mcp.tool + 2 @mcp.resource; stdio entry point
│   ├── models.py             # Pydantic models: Forecast, DayForecast, SavedTrip, TripPlan
│   ├── weather.py            # Open-Meteo geocode + forecast (httpx2.AsyncClient, 10 s timeout), WMO code → text
│   ├── storage.py            # JSON trip store: load/validate, duplicate check, atomic write, TRIPS_FILE env
│   └── planning.py           # pure: build_packing_list(forecast), summarize(forecast)
├── host/                     # ── MCP HOST + CLIENT (OpenAI Agents SDK) ──
│   └── agent.py              # Agent + MCPServerStdio + RunHooks logging + chat loop (/tools, /trips, /quit)
├── scripts/
│   ├── smoke_client.py       # no-LLM interactive check: list tools, call each tool + each failure
│   └── demo.py               # scripted demo queries for a reliable recording
├── tests/
│   ├── conftest.py           # tmp TRIPS_FILE, fake weather backend (monkeypatch)
│   ├── test_tools.py         # in-memory fastmcp.Client(mcp) tests, offline
│   ├── test_host_wiring.py   # MCPServerStdio list/call against the real subprocess (no LLM, no key)
│   └── test_live_api.py      # @pytest.mark.live: real Open-Meteo call (opt-in)
└── docs/
    ├── summary.md / summary.pdf     # Part 1 (300–400 words)
    ├── reflection.md                # 1–2 paragraphs
    └── demo_script.md               # screencast script and checklist
```

---

## 5. Part 1: Reading, exploration and written summary

### 5.1 Article: what to cover (verified against the full text)
- **Problem:** LLMs are isolated from data. Per-source custom integrations are "brittle and hard to scale".
- **MCP:** an open standard from Anthropic (Nov 2024) that turns the **N×M** integration problem into **N+M**. It is model-agnostic and is compared to standards such as USB, HTTP and ODBC.
- **Dynamic discovery:** agents detect servers and their capabilities without hard-coded integrations. Servers expose **tools, resources and prompt templates**.
- **Comparisons:**
  - Custom APIs need one integration each.
  - OpenAI plugins (2023) were proprietary, one-way and stateless.
  - LangChain standardises the *developer-facing* tool interface, while MCP standardises the *model-facing* side.
  - RAG supplies context passively.
  - A2A connects agents to agents, whereas MCP connects a model to tools (the article calls MCP the agent's "hands").
- **Limitations:** operational overhead, tool usability (quality depends on descriptions, which ties directly to the class principles), maturity and breaking changes, compatibility, overkill for one or two APIs, and security/permissions.
- **Host/Client/Server** (take precise wording from modelcontextprotocol.io, the source of the article's diagrams):
  - The **Host** is the AI application (Claude Desktop, an IDE, *our Python agent app*). It coordinates and manages clients.
  - The Host creates **one MCP Client per server**. Each client keeps a **dedicated connection** and fetches context for the host.
  - An **MCP Server** is a program that provides context (tools, resources, prompts).
  - Messages are JSON-RPC 2.0 over **stdio** (local) or **Streamable HTTP** (remote).
  - **Mapped to this project:** the Python agent app is the Host, `MCPServerStdio` is the Client, and the FastMCP process is the Server.

### 5.2 Server critique: Fetch server (primary), Filesystem server (contrast)
Verified against `modelcontextprotocol/servers` main branch, Oct 2026.
- **Fetch**:
  - It exposes **one tool**, `fetch`, plus a prompt.
  - Its schema is strict: `url`, `max_length` (default 5000), `start_index`, `raw`.
  - Its annotations are read-only, idempotent and open-world.
  - Its errors are predictable: robots.txt refusal, HTTP ≥400, connection failure and blocked private IPs all become `ToolError`, which reaches the model as `isError`.
  - **Critique:** its own description fails the "and" test ("Fetches a URL … *and optionally extracts* its contents as markdown"). One tool bundles retrieval, robots.txt policy, HTML→Markdown conversion and pagination, and the `raw` flag is a mode switch that effectively makes it two tools.
  - **Fair counterpoint:** bundling keeps the model's tool surface tiny and saves round trips. Pagination with `start_index` is good token hygiene.
- **Filesystem** (contrast):
  - It has 13 fine-grained tools (`read_text_file`, `write_file`, `edit_file`, `move_file`, `search_files`…), each single-purpose.
  - It sets correct `readOnlyHint` / `destructiveHint` annotations, and access is sandboxed to allowed directories.
  - Minor overlap: `read_multiple_files` duplicates `read_text_file` for batching efficiency.
- **Before writing, do your own exploration:** open the source on GitHub, and optionally run `npx @modelcontextprotocol/inspector uvx mcp-server-fetch` to see `tools/list` live. The PDF asks *you* to explore it.

### 5.3 Writing
- Budget: about 180 words on the article and Host/Client/Server, and about 170 words on the critique. Stay within **300–400 words**, counted without the title and references.
- Cite both the HF URL and the Turing Post full text, plus modelcontextprotocol.io and the GitHub server sources.
- Export: `docs/summary.md`, then PDF (Pandoc, or print from VS Code's Markdown preview).

---

## 6. Part 2: Implementation steps

1. **Scaffold** with `uv init` on Python 3.12. Add `fastmcp==4.1.3` and `openai-agents==0.24.0`, plus dev dependencies `pytest` and `pytest-asyncio`. Also add `.gitignore`, `.env.example` and `git init`. (`httpx2` comes in transitively from both SDKs, so it needs no extra dependency.)
2. **Models** (`models.py`): Pydantic models with `Field(description=…)` on every field. They become the tools' output schemas.
3. **Domain modules** (no MCP imports, unit-testable):
   - `weather.py`: `geocode(city)` and `fetch_daily(lat, lon, start, days)`. Validate the date window locally before calling the API. Map WMO codes to text. Turn every HTTP or timeout failure into a typed exception carrying a clear message.
   - `storage.py`: `TripStore(path)` with `add()`, `list()` and `get()`. It detects duplicates and corrupt files and writes atomically.
   - `planning.py`: `build_packing_list(forecast)` and `summarize(forecast)`, built from deterministic rules: rain ≥50 % → umbrella; max ≥28 °C → sunscreen and water; min ≤12 °C → jacket.
4. **Server** (`server.py`):
   - `mcp = FastMCP("trip-planner", instructions=…)`.
   - The three `@mcp.tool` functions use descriptive docstrings, `Annotated` arguments and annotations. Domain exceptions are translated to `ToolError`.
   - Add the two `@mcp.resource` functions.
   - Log each call to **stderr** (e.g. `[server] get_weather_forecast(city='Beirut', days=3)`). The stdio client inherits stderr, so these lines appear in the demo terminal.
   - Entry point: `python -m trip_mcp.server` runs over stdio. Optionally add `--http` (`mcp.run(transport="http", port=8000)`) to show client and server in two terminals.
5. **Host/Client** (`host/agent.py`):
   - Create `MCPServerStdio(name="trip-planner", params={"command": sys.executable, "args": ["-m", "trip_mcp.server"], "env": {...}}, cache_tools_list=True)` and attach it with `Agent(name="Trip Planner", instructions=ROUTING_RULES, mcp_servers=[server])`.
   - **Routing rules:**
     - Weather questions → `get_weather_forecast` only.
     - "Save this trip" with explicit details → `save_trip`.
     - "Plan a trip" → `plan_trip`. Never call the data and action tools manually for a full plan.
     - Report tool errors honestly and never invent forecast data.
   - **`RunHooks`** print `→ [host→client] calling plan_trip {args}` and `← [client←server] result …`, using `context.tool_arguments` when available.
   - **Chat loop:**
     - Keep the conversation history with `result.to_input_list()`.
     - `/tools` lists tools via `server.list_tools()`.
     - `/trips` reads the `trips://saved` resource via `server.read_resource()`.
   - Tracing is on by default. With an OpenAI key, each run appears at platform.openai.com/traces with MCP list-tools and tool-call spans, which gives a second view of the round trip for the video.
6. **Tests:**
   - `tests/test_tools.py` uses `async with fastmcp.Client(mcp)`, in memory and with the network mocked. It covers:
     - exactly 3 tools, with the expected names and annotations;
     - each tool's happy path;
     - **each tool's failure case** (unknown city, out-of-range date, `days=99`, timeout; `end<start`, duplicate, corrupt store; orchestration step-1 failure **leaves no file written**);
     - both resources.
   - `test_host_wiring.py` checks the Agents SDK client against the real subprocess with no LLM.
   - `test_live_api.py` is marked live and opt-in.
   - Command: `uv run pytest -v`.
7. **Interactive check:**
   - `scripts/smoke_client.py` calls every tool and failure path through the SDK client and prints the results. No API key is needed.
   - Optionally use the MCP Inspector (`npx @modelcontextprotocol/inspector`) or the `fastmcp dev` / `fastmcp list` / `fastmcp call` CLI commands.
8. **README:**
   - Overview and an architecture diagram (Host → Client → Server → Open-Meteo / trips.json).
   - The tool table, marking which tool is Data, which is Action and which is Orchestration.
   - Setup: `uv sync` and `.env`. Run: `uv run python -m host.agent`. Test: `uv run pytest`.
   - Example prompts, failure-case examples, the versions used, and Open-Meteo CC-BY 4.0 attribution.
9. **GitHub:** create the repo (public, or private with the grader added) and push. `gh` is installed. I would only push after you confirm.

---

## 7. Part 3: Screencast (target 6:00–6:30, hard limits 5–7 min)

| Time | Segment | Content |
|---|---|---|
| 0:00–0:50 | Intro | Theme. **Name each tool's category aloud**: Data = `get_weather_forecast`, Action = `save_trip`, Orchestration = `plan_trip`. Show the README diagram: our agent app (Host) → `MCPServerStdio` (Client) → FastMCP (Server). |
| 0:50–1:45 | Code tour | `server.py`: decorators, descriptions, typed `Field`s, annotations, `ToolError`. `plan_trip` calling the other two via `mcp.call_tool`. `agent.py`: `MCPServerStdio` + `Agent(mcp_servers=…)`. |
| 1:45–4:00 | Live demo | Q1 "What's the weather in Beirut for the next 3 days?" → Data tool.<br>Q2 "Save a trip to Byblos from Oct 30 to Nov 1, note: visit the castle" → Action tool.<br>Q3 "Plan a 3-day trip to Paris starting this Friday" → Orchestration; the server log shows it calling both tools.<br>`/trips` → resource read.<br>Each step shows the host-hook lines and server stderr lines (the round trip). Briefly show the OpenAI trace view. |
| 4:00–4:45 | Failures | "Plan a 2-day trip to Xyzzyville starting next Saturday" → clear error, and `/trips` confirms nothing was saved. Repeat Q2 → duplicate error. Run `uv run pytest -v` to show the failure tests passing. |
| 4:45–5:45 | Challenges | Keeping tools single-purpose (the geocoding-inside-the-data-tool decision). Orchestrating through the registered tools instead of duplicating logic. Avoiding partial side effects. LLM routing via descriptions and instructions. Version churn (FastMCP 4, the 2026-07-28 spec, snake_case renames). |
| 5:45–6:30 | Wrap-up | Repo link on screen, next steps. |

**Recording:** use OBS Studio or the Windows Snipping Tool screen recorder. Set the terminal font to 16pt or larger, and use `scripts/demo.py` or pre-typed prompts to keep the timing reliable. Do a dry run first, because LLM answers vary. **Upload as YouTube unlisted** (your account).

---

## 8. Reflection (`docs/reflection.md`, 1–2 paragraphs): points to cover
- **Where the lines were drawn:** the data tool is read-only and the action tool takes no external input. Only the orchestrator crosses the boundary, so each tool passes the "and" test and has its own annotations and failure modes.
- **Was three the right number?** It is enough for the core flow. The pressure points were geocoding, which could become its own data tool or a resource, and listing or deleting trips, which is handled for now by a read-only resource. In a real product, a delete action would be a separate, `destructiveHint=True` tool behind approval (the Agents SDK's `require_approval`).
- **Next steps:**
  - Streamable HTTP deployment with auth.
  - Multi-city or route planning.
  - Calendar (.ics) export as a second action tool.
  - Caching forecasts.
  - An evaluation set of prompts to measure routing accuracy.

---

## 9. Submission checklist
- [ ] `docs/summary.pdf` (or `.md`): 300–400 words, Host/Client/Server explained, server critique included
- [ ] GitHub repo link containing the server, host, README, tests and scripts
- [ ] `uv run pytest -v` passes, including the failure tests
- [ ] Video 5–7 min, uploaded unlisted, link tested in a private window
- [ ] `docs/reflection.md`: 1–2 paragraphs
- [ ] Submission text includes the repo URL and video URL

## 10. Open decisions and risks
1. **OpenAI API key:** required for the live agent and the trace dashboard. Cost per demo run is small. Without a key, the SDK supports other providers through its LiteLLM / any-llm extensions (disable tracing in that case). Tests and smoke scripts need **no** key.
2. **Theme:** the plan uses Weather & Trip Planner. Swap now if you prefer another.
3. **Repo visibility and name:** public, or private with the grader added?
4. **Version drift:** pin versions. If PyPI moves before submission, re-run the tests before upgrading.

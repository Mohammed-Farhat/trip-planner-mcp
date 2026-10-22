# Screencast script (target 6:00–6:30; the required length is 5–7 minutes)

## Before recording
- [ ] `.env` contains `OPENAI_API_KEY`. `uv run python -m host.agent "hello"` answers.
- [ ] `uv run pytest -v` is all green (31 passed).
- [ ] Terminal font is 16 pt or larger, the window is maximised, and notifications are off.
- [ ] Two windows are ready: the terminal and an editor open on `trip_mcp/server.py` and `host/agent.py`.
- [ ] You are logged in at https://platform.openai.com/traces to show one trace.
- [ ] Do one full dry run of `uv run python scripts/demo.py`. LLM wording varies between runs, so know what to expect.
- [ ] The recorder is ready: OBS Studio, or the Windows Snipping Tool's "Record" mode, with your microphone on.

## Timeline

| Time | Show | Say (key points) |
|---|---|---|
| 0:00–0:50 | The README architecture diagram | **Intro:**<br>• A Weather & Trip Planner MCP toolkit with three tools: **Data:** `get_weather_forecast`, **Action:** `save_trip`, **Orchestration:** `plan_trip`.<br>• The host is my Agents SDK program, the client is `MCPServerStdio`, and the server is FastMCP. |
| 0:50–1:45 | `trip_mcp/server.py` | **Code tour:**<br>• The `@mcp.tool` decorators, typed `Annotated` arguments with descriptions, and Pydantic outputs.<br>• Annotations (`readOnlyHint` and so on) and `ToolError` messages.<br>• `plan_trip` calling the other two tools with `mcp.call_tool`.<br>• The `@mcp.resource` lookups. |
| 1:45–2:05 | `host/agent.py` | `MCPServerStdio` launches the server, `Agent(mcp_servers=[server])` attaches it, and `RunHooks` print each hop. |
| 2:05–4:00 | Terminal: `uv run python scripts/demo.py` | **Steps 1–5:** `/tools`; the Data, Action and Orchestration prompts; then `/trips`.<br>• On each step, point at the three kinds of line: `host -> MCP client -> server` (request), `[server] …` (executed in the server process), `server -> MCP client -> host` (result). This is the full round trip.<br>• On the `plan_trip` step, point out that the server log shows `plan_trip`, then `get_weather_forecast`, then `save_trip`. |
| 4:00–4:20 | Browser: one trace link | The OpenAI trace shows the MCP `list_tools` call, the tool call, and the model turns. |
| 4:20–5:00 | Terminal: steps 6–8 | **Failures:**<br>• Xyzzyville → a clear "No city named…" error, "Nothing was saved", and `/trips` shows no new trip.<br>• Duplicate Byblos save → "already saved as trip-0001". |
| 5:00–5:15 | `uv run pytest -v` | The 31 tests include every tool's failure case and an agent round trip with a scripted model, which needs no API key. |
| 5:15–6:05 | Talking over the code | **Challenges:**<br>• Keeping tools single-purpose: geocoding stays inside the Data tool, and the "City, Country" qualifier resolves ambiguity.<br>• Orchestrating through the *registered* tools, so failures chain and nothing is half-saved.<br>• Real-world failures: Atlantis is a real town, so the test city is fictional; one Open-Meteo timeout led to a single retry.<br>• Version churn: FastMCP 4 and the 2026-07-28 MCP spec deprecated sampling and logging, which is why the server logs to stderr. |
| 6:05–6:30 | The README | Repo link, and next steps: `list_trips`/`delete_trip`, HTTP deployment, routing. |

## After recording
1. Trim the dead air and check that the length is between 5:00 and 7:00.
2. Upload to YouTube as **Unlisted** and test the link in a private window.
3. Paste the link into the README's deliverables table and into the submission.

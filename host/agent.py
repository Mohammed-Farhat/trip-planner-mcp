"""MCP host: an OpenAI Agents SDK agent that reaches the trip-planner server through an MCP client.

    Host   = this program: owns the conversation and the LLM, decides which tool to call
    Client = agents.mcp.MCPServerStdio: one dedicated stdio connection to the server
    Server = trip_mcp/server.py, launched by the client as a subprocess

Usage:
    uv run python -m host.agent                          # interactive chat
    uv run python -m host.agent "Weather in Beirut?"     # one question, then exit
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
from pathlib import Path

from agents import Agent, RunHooks, Runner, gen_trace_id, trace
from agents.mcp import MCPServerStdio
from dotenv import load_dotenv
from mcp.client.stdio import get_default_environment
from rich.console import Console
from rich.markup import escape

ROOT = Path(__file__).resolve().parent.parent
console = Console(highlight=False)

HELP = "Commands: /tools (list MCP tools), /trips (read the trips://saved resource), /reset, /quit"


def build_server() -> MCPServerStdio:
    """The MCP client. It launches the server with `python -m trip_mcp.server` and talks to it over stdio."""
    env = {**get_default_environment(), "PYTHONIOENCODING": "utf-8"}
    if os.environ.get("TRIPS_FILE"):
        env["TRIPS_FILE"] = os.environ["TRIPS_FILE"]
    return MCPServerStdio(
        name="trip-planner",
        params={"command": sys.executable, "args": ["-m", "trip_mcp.server"], "cwd": str(ROOT), "env": env},
        cache_tools_list=True,
        client_session_timeout_seconds=60,
    )


def instructions(today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    return f"""You are a trip-planning assistant. Today is {today:%A, %Y-%m-%d}.
You act only through the trip-planner MCP tools:
- get_weather_forecast (DATA, read-only): any question about the weather. It never saves anything.
- save_trip (ACTION): only when the user asks to save a trip and gives the city and dates (notes optional).
- plan_trip (ORCHESTRATION): when the user asks you to plan a trip. It fetches the forecast and saves the
  trip by itself, so do not call get_weather_forecast or save_trip first for a full plan.
Rules:
- Convert relative dates ("this Saturday", "next week") to YYYY-MM-DD using today's date.
- If a tool returns an error, tell the user plainly what went wrong and what they could change.
  Never invent weather data, and never say a trip was saved unless a tool confirmed it with a trip id.
- Keep answers short: a few bullet points, temperatures in °C."""


def build_agent(server: MCPServerStdio, model: str | None = None) -> Agent:
    kwargs = {"model": model} if model else {}
    return Agent(name="Trip Planner", instructions=instructions(), mcp_servers=[server], **kwargs)


def _preview(output: object, limit: int = 180) -> str:
    """Short one-line view of what a tool sent back to the model."""
    if isinstance(output, dict) and "text" in output:
        output = output["text"]
    elif isinstance(output, list):
        output = " ".join(str(o.get("text", o)) if isinstance(o, dict) else str(o) for o in output)
    text = " ".join(str(output).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class RoundTripLog(RunHooks):
    """Prints each hop of a tool call so the full round trip is visible in the terminal."""

    async def on_tool_start(self, context, agent, tool):
        args = getattr(context, "tool_arguments", None) or ""
        console.print(f"  [cyan]host -> MCP client -> server[/]  {escape(tool.name)}({escape(str(args))})")

    async def on_tool_end(self, context, agent, tool, result):
        console.print(f"  [cyan]server -> MCP client -> host[/]  {escape(tool.name)}: {escape(_preview(result))}")


async def run_turn(agent: Agent, history: list, text: str, hooks: RunHooks | None = None) -> list:
    """Send one user message through the agent; returns the updated conversation history."""
    trace_id = gen_trace_id()
    with trace("Trip Planner", trace_id=trace_id):
        result = await Runner.run(
            agent, [*history, {"role": "user", "content": text}], hooks=hooks or RoundTripLog(), max_turns=8
        )
    console.print(f"[bold green]agent>[/] {escape(str(result.final_output))}")
    console.print(f"  [dim]trace: https://platform.openai.com/traces/trace?trace_id={trace_id}[/]")
    return result.to_input_list()


async def show_tools(server: MCPServerStdio) -> None:
    for t in await server.list_tools():
        ann = t.annotations
        kind = "read-only" if ann and ann.read_only_hint else "changes state"
        console.print(f"  [bold]{t.name}[/] ({kind}): {escape((t.description or '').splitlines()[0])}")


async def show_trips(server: MCPServerStdio) -> None:
    result = await server.read_resource("trips://saved")
    trips = json.loads(result.contents[0].text)
    if not trips:
        console.print("  (no saved trips)")
    for t in trips:
        console.print(f"  {t['id']}  {escape(t['city'])}  {t['start_date']} -> {t['end_date']}")


async def chat(server: MCPServerStdio, agent: Agent) -> None:
    console.print(f"[bold]Trip Planner[/] (MCP server: {server.name}). {HELP}")
    history: list = []
    while True:
        try:
            text = (await asyncio.to_thread(console.input, "[bold]you>[/] ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        try:
            if text == "/tools":
                await show_tools(server)
            elif text == "/trips":
                await show_trips(server)
            elif text == "/reset":
                history = []
                console.print("  (conversation cleared)")
            elif text.startswith("/"):
                console.print(f"  Unknown command. {HELP}")
            else:
                history = await run_turn(agent, history, text)
        except Exception as e:  # keep the chat alive on API/network errors
            console.print(f"[red]error:[/] {escape(f'{type(e).__name__}: {e}')}")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Trip Planner agent (MCP host)")
    parser.add_argument("question", nargs="*", help="ask one question and exit")
    parser.add_argument("--model", help="model name (default: the Agents SDK default or $OPENAI_DEFAULT_MODEL)")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY is not set.[/] Copy .env.example to .env and add your key.")
        return 2

    async with build_server() as server:
        agent = build_agent(server, args.model)
        if args.question:
            await run_turn(agent, [], " ".join(args.question))
        else:
            await chat(server, agent)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Scripted demo for the screencast: a fixed sequence of prompts through the real agent.

Needs OPENAI_API_KEY in .env. Starts from an empty demo trip store (data/demo_trips.json) so the
duplicate-save failure behaves the same on every run.

    uv run python scripts/demo.py              # waits for Enter before each step
    uv run python scripts/demo.py --no-pause
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from rich.markup import escape  # noqa: E402

from host.agent import build_agent, build_server, console, run_turn, show_tools, show_trips  # noqa: E402

DEMO_TRIPS = ROOT / "data" / "demo_trips.json"

STEPS = [
    ("List the server's tools", "/tools"),
    ("Data tool", "What's the weather in Beirut for the next 3 days?"),
    ("Action tool", "Save a trip to Byblos for this Saturday and Sunday. Note: visit the old souk and the citadel."),
    ("Orchestration tool", "Plan a 3-day trip to Paris, France starting next Monday."),
    ("Read the trips://saved resource", "/trips"),
    ("Failure: unknown city", "Plan a weekend trip to Xyzzyville."),
    ("Failure: duplicate save", "Save the Byblos trip for this Saturday and Sunday again."),
    ("Nothing extra was saved", "/trips"),
]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-pause", action="store_true")
    parser.add_argument("--model")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY is not set.[/] Copy .env.example to .env and add your key.")
        return 2
    DEMO_TRIPS.unlink(missing_ok=True)
    os.environ["TRIPS_FILE"] = str(DEMO_TRIPS)

    async with build_server() as server:
        agent = build_agent(server, args.model)
        history: list = []
        for i, (title, prompt) in enumerate(STEPS, 1):
            console.rule(f"[bold]{i}. {title}")
            if not args.no_pause:
                await asyncio.to_thread(input, "(Enter to run) ")
            console.print(f"[bold]you>[/] {escape(prompt)}")
            if prompt == "/tools":
                await show_tools(server)
            elif prompt == "/trips":
                await show_trips(server)
            else:
                history = await run_turn(agent, history, prompt)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

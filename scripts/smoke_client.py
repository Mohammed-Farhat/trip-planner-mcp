"""Exercise every tool, and each tool's failure case, through the same MCP client the agent uses.

No LLM and no API key needed; the weather calls do need internet. Uses a throwaway trip store, so
data/trips.json is never touched.

    uv run python scripts/smoke_client.py
"""

import asyncio
import datetime as dt
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.markup import escape  # noqa: E402

from host.agent import _preview, build_server, console, show_tools, show_trips  # noqa: E402


async def check(server, tool: str, args: dict, expect: str) -> bool:
    res = await server.call_tool(tool, args)
    got = "error" if res.is_error else "ok"
    text = res.content[0].text if res.content else ""
    mark = "[green]PASS[/]" if got == expect else "[red]FAIL[/]"
    console.print(f"{mark} {tool}({escape(json.dumps(args))})  expected {expect}, got {got}")
    console.print(f"     {escape(_preview(text, 200))}")
    return got == expect


async def main() -> int:
    today = dt.date.today()
    sat = today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7)
    sun = sat + dt.timedelta(days=1)
    cases = [
        ("get_weather_forecast", {"city": "Beirut", "days": 3}, "ok"),
        ("get_weather_forecast", {"city": "Xyzzyville"}, "error"),  # unknown city
        ("get_weather_forecast", {"city": "Beirut", "start_date": str(today + dt.timedelta(days=40))}, "error"),
        ("get_weather_forecast", {"city": "Beirut", "days": 99}, "error"),  # schema validation
        ("save_trip", {"city": "Byblos", "start_date": str(sat), "end_date": str(sun), "notes": "Citadel"}, "ok"),
        ("save_trip", {"city": "Byblos", "start_date": str(sat), "end_date": str(sun)}, "error"),  # duplicate
        ("save_trip", {"city": "Byblos", "start_date": str(sun), "end_date": str(sat)}, "error"),  # end < start
        ("plan_trip", {"city": "Paris, France", "start_date": str(sat), "days": 3}, "ok"),
        ("plan_trip", {"city": "Xyzzyville", "start_date": str(sat)}, "error"),  # step 1 fails, nothing saved
    ]

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["TRIPS_FILE"] = str(Path(tmp) / "trips.json")
        async with build_server() as server:
            console.rule("tools/list")
            await show_tools(server)
            console.rule("tools/call")
            results = [await check(server, *case) for case in cases]
            console.rule("resources/read trips://saved  (expect Byblos + Paris only)")
            await show_trips(server)

    passed = sum(results)
    console.print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

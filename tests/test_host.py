"""The host side: the Agents SDK's MCP client talking to the real server subprocess over stdio.

These tests need no API key. The full agent round trip uses ScriptedModel, a stand-in for the LLM that
always calls one given tool and then answers with that tool's output. The tool calls here avoid the
network, because the fake Open-Meteo does not reach into the subprocess.
"""

import datetime as dt
import json

from agents import Agent, Runner, set_tracing_disabled
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from conftest import SOON
from host.agent import build_server, instructions

set_tracing_disabled(True)


async def test_stdio_client_lists_and_calls_tools(trips_file):
    async with build_server() as server:
        assert {t.name for t in await server.list_tools()} == {"get_weather_forecast", "save_trip", "plan_trip"}

        ok = await server.call_tool("save_trip", {"city": "Byblos", "start_date": str(SOON), "end_date": str(SOON)})
        assert not ok.is_error and ok.structured_content["id"] == "trip-0001"

        bad = await server.call_tool("save_trip", {"city": "Byblos", "start_date": str(SOON), "end_date": "2020-01-01"})
        assert bad.is_error and "is before start_date" in bad.content[0].text

        past = str(dt.date.today() - dt.timedelta(days=3))
        failed = await server.call_tool("plan_trip", {"city": "Beirut", "start_date": past})
        assert failed.is_error and "Nothing was saved" in failed.content[0].text

        saved = json.loads((await server.read_resource("trips://saved")).contents[0].text)
        assert [t["id"] for t in saved] == ["trip-0001"]


class ScriptedModel(Model):
    def __init__(self, tool_name: str, arguments: dict):
        self.tool_name = tool_name
        self.arguments = arguments
        self.offered_tools: list[str] = []

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs,
                           tracing, *, previous_response_id=None, conversation_id=None, prompt=None):
        self.offered_tools = [t.name for t in tools]
        outputs = [i for i in input if isinstance(i, dict) and i.get("type") == "function_call_output"]
        if not outputs:
            call = ResponseFunctionToolCall(id="fc_1", call_id="call_1", type="function_call", status="completed",
                                            name=self.tool_name, arguments=json.dumps(self.arguments))
            return ModelResponse(output=[call], usage=Usage(), response_id=None)
        output = outputs[-1]["output"]  # a string, or a list of {"type": "input_text", "text": ...} parts
        if isinstance(output, list):
            text = " ".join(part.get("text", "") for part in output if isinstance(part, dict))
        else:
            text = str(output)
        message = ResponseOutputMessage(id="msg_1", type="message", role="assistant", status="completed",
                                        content=[ResponseOutputText(type="output_text", text=text, annotations=[])])
        return ModelResponse(output=[message], usage=Usage(), response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError


async def run_agent(model: ScriptedModel) -> str:
    async with build_server() as server:
        agent = Agent(name="Trip Planner", instructions=instructions(), mcp_servers=[server], model=model)
        result = await Runner.run(agent, "test request")
    return str(result.final_output)


async def test_agent_round_trip_through_mcp(trips_file):
    model = ScriptedModel("save_trip", {"city": "Byblos", "start_date": str(SOON), "end_date": str(SOON)})
    answer = await run_agent(model)

    assert set(model.offered_tools) == {"get_weather_forecast", "save_trip", "plan_trip"}
    assert '"id":"trip-0001"' in answer  # the server's result came back to the agent
    assert json.loads(trips_file.read_text(encoding="utf-8"))[0]["city"] == "Byblos"


async def test_agent_sees_the_tool_error_text(trips_file):
    model = ScriptedModel("save_trip", {"city": "Byblos", "start_date": str(SOON), "end_date": "2020-01-01"})
    answer = await run_agent(model)

    assert "is before start_date" in answer
    assert not trips_file.exists()


def test_instructions_name_every_tool_and_todays_date():
    text = instructions(dt.date(2026, 10, 22))
    assert "Today is Thursday, 2026-10-22" in text
    for name in ("get_weather_forecast", "save_trip", "plan_trip"):
        assert name in text
